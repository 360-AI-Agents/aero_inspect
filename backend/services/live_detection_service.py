from datetime import datetime
from sqlalchemy.orm import Session

from backend.models.camera import Camera
from backend.models.inspection import Inspection
from backend.models.worker import Worker
from backend.models.worker_violation import WorkerViolation
from backend.schemas.live_detection import LiveDetectionPayload
from backend.schemas.violation import ViolationCreate
from backend.repositories.violation_repository import ViolationRepository
from backend.repositories.inspection_repository import InspectionRepository
from backend.services.detection_service import DetectionService
from backend.core.logger import logger


SEVERITY_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}


def _map_severity(raw: str) -> str:
    return SEVERITY_MAP.get(raw.lower(), "medium")


def _map_category(finding_text: str) -> str:
    text = finding_text.lower()
    if "helmet" in text:
        return "helmet"
    if "vest" in text:
        return "vest"
    if "mask" in text:
        return "unsafe_behaviour"
    if "restricted" in text or "zone" in text:
        return "restricted_zone"
    if "fall" in text or "harness" in text:
        return "fall_protection"
    if "equipment" in text or "machine" in text:
        return "heavy_equipment"
    if "scaffold" in text:
        return "scaffolding"
    if "debris" in text:
        return "debris"
    return "unsafe_behaviour"


def _parse_dt(raw: str):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _is_within_shift(worker: Worker, check_time: datetime) -> bool:
    """
    Returns True if check_time falls within the worker's registered shift,
    False if outside shift or on their weekly off day.
    If the worker has no shift data set, we can't judge — default to True
    (don't falsely flag someone we have no schedule for).
    """
    if not worker.shift_start or not worker.shift_end:
        return True

    weekday_name = check_time.strftime("%A")
    if worker.weekly_off_day and worker.weekly_off_day == weekday_name:
        return False

    try:
        shift_start_time = datetime.strptime(worker.shift_start, "%H:%M").time()
        shift_end_time = datetime.strptime(worker.shift_end, "%H:%M").time()
        current_time = check_time.time()

        if shift_start_time <= shift_end_time:
            return shift_start_time <= current_time <= shift_end_time
        else:
            return current_time >= shift_start_time or current_time <= shift_end_time
    except ValueError:
        return True


class LiveDetectionService:

    @staticmethod
    def _get_or_create_camera(db: Session, camera_name: str, location: str) -> Camera:
        camera = (
            db.query(Camera)
            .filter(Camera.camera_name == camera_name, Camera.location == location)
            .first()
        )
        if camera:
            return camera

        camera = Camera(
            camera_name=camera_name,
            location=location,
            source_type="cctv",
            status="active",
        )
        db.add(camera)
        db.commit()
        db.refresh(camera)
        logger.info(f"Auto-registered new camera from live pipeline: {camera_name} @ {location}")
        return camera

    @staticmethod
    def _get_or_create_active_inspection(db: Session, camera: Camera) -> Inspection:
        existing = (
            db.query(Inspection)
            .filter(Inspection.camera_id == camera.id)
            .order_by(Inspection.created_at.desc())
            .first()
        )
        if existing:
            return existing

        new_inspection = Inspection(
            inspection_name=f"{camera.location} — Live Feed",
            camera_id=camera.id,
            inspection_status="pending",
        )
        db.add(new_inspection)
        db.commit()
        db.refresh(new_inspection)
        return new_inspection

    @staticmethod
    def _upsert_worker_violations(db: Session, inspection_id: int, payload: LiveDetectionPayload):
        for worker_data in payload.workers:
            existing = (
                db.query(WorkerViolation)
                .filter(
                    WorkerViolation.inspection_id == inspection_id,
                    WorkerViolation.worker_id == worker_data.worker_id,
                    WorkerViolation.status == "open",
                )
                .first()
            )

            matching_event = next((e for e in payload.events if e.worker_id == worker_data.worker_id), None)

            alert_type = "ppe_violation"
            linked_worker = (
                db.query(Worker)
                .filter(Worker.tracked_worker_id == worker_data.worker_id)
                .first()
            )
            if linked_worker:
                event_time = _parse_dt(worker_data.first_seen) or datetime.utcnow()
                if not _is_within_shift(linked_worker, event_time):
                    alert_type = "unauthorized_presence"

            if existing:
                existing.violations = ", ".join(worker_data.violations) if worker_data.violations else existing.violations
                existing.last_seen = _parse_dt(worker_data.last_seen) or existing.last_seen
                existing.duration_seconds = worker_data.violation_duration_seconds or existing.duration_seconds
                existing.repeat_offender = worker_data.repeat_offender or existing.repeat_offender
                existing.total_violation_events = worker_data.total_violation_events or existing.total_violation_events
                if worker_data.image:
                    existing.evidence_image_path = worker_data.image
                if matching_event:
                    existing.status = matching_event.status
                    existing.transition = matching_event.transition
                existing.alert_type = alert_type
                db.commit()
            else:
                new_row = WorkerViolation(
                    inspection_id=inspection_id,
                    worker_id=worker_data.worker_id,
                    event_id=matching_event.event_id if matching_event else None,
                    violations=", ".join(worker_data.violations) if worker_data.violations else None,
                    status=matching_event.status if matching_event else "open",
                    transition=matching_event.transition if matching_event else "opened",
                    alert_type=alert_type,
                    first_seen=_parse_dt(worker_data.first_seen),
                    last_seen=_parse_dt(worker_data.last_seen),
                    duration_seconds=worker_data.violation_duration_seconds or 0.0,
                    repeat_offender=worker_data.repeat_offender or False,
                    total_violation_events=worker_data.total_violation_events or 1,
                    evidence_image_path=worker_data.image,
                    employee_id=linked_worker.employee_id if linked_worker else None,
                )
                db.add(new_row)
                db.commit()

    @staticmethod
    def process_live_payload(db: Session, payload: LiveDetectionPayload):
        camera = LiveDetectionService._get_or_create_camera(db, payload.camera_name, payload.location)
        inspection = LiveDetectionService._get_or_create_active_inspection(db, camera)

        if payload.workers:
            LiveDetectionService._upsert_worker_violations(db, inspection.id, payload)

        if not payload.findings:
            return {
                "message": "Heartbeat received, no new findings",
                "inspection_id": inspection.id,
                "camera_id": camera.id,
            }

        violations_payload = []
        for f in payload.findings:
            violations_payload.append(ViolationCreate(
                category=_map_category(f.finding),
                violation_name=f.finding,
                severity=_map_severity(f.severity),
                confidence=f.confidence,
                count=f.count,
            ))

        class _WrappedEvent:
            def __init__(self, workers_detected, violations):
                self.workers_detected = workers_detected
                self.violations = violations

        wrapped = _WrappedEvent(
            workers_detected=payload.workers_detected,
            violations=violations_payload,
        )

        result = DetectionService.process_detection_event(db, inspection.id, wrapped)

        return {
            "message": "Live detection processed",
            "inspection_id": inspection.id,
            "camera_id": camera.id,
            **result,
        }