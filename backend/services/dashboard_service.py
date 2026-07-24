from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.inspection import Inspection
from backend.models.violation import Violation
from backend.models.camera import Camera
from backend.repositories.inspection_repository import InspectionRepository
from backend.repositories.violation_repository import ViolationRepository
from backend.utils.calculations import build_violation_breakdown


class DashboardService:

    @staticmethod
    def get_dashboard_data(db: Session, allowed_locations: list = None):
        history = InspectionRepository.get_all(db, skip=0, limit=100)

        if allowed_locations is not None:
            filtered = []
            for insp in history:
                if insp.camera_id:
                    cam = db.query(Camera).filter(Camera.id == insp.camera_id).first()
                    if cam and cam.location in allowed_locations:
                        filtered.append(insp)
            history = filtered

        history = history[:20]
        latest = history[0] if history else None

        if allowed_locations is not None:
            total_workers = sum(i.workers_detected for i in history)
            total_violations = sum(i.total_violations for i in history)
            avg_compliance = (
                sum(i.compliance_score for i in history) / len(history)
                if history else 100.0
            )
        else:
            total_workers = db.query(func.sum(Inspection.workers_detected)).scalar() or 0
            total_violations = db.query(func.sum(Inspection.total_violations)).scalar() or 0
            avg_compliance = db.query(func.avg(Inspection.compliance_score)).scalar() or 100.0

        latest_violations = []
        if latest:
            latest_violations = ViolationRepository.get_by_inspection(db, latest.id)

        breakdown = build_violation_breakdown(latest_violations)

        compliance_trend = "flat"
        compliance_delta = 0.0
        if len(history) >= 2:
            current_score = history[0].compliance_score
            previous_score = history[1].compliance_score
            compliance_delta = round(current_score - previous_score, 1)
            if compliance_delta > 0:
                compliance_trend = "up"
            elif compliance_delta < 0:
                compliance_trend = "down"

        if allowed_locations is not None:
            allowed_inspection_ids = [i.id for i in history]
            recent_violations = (
                db.query(Violation)
                .filter(Violation.inspection_id.in_(allowed_inspection_ids))
                .order_by(Violation.created_at.desc())
                .limit(5)
                .all()
            )
        else:
            recent_violations = (
                db.query(Violation)
                .order_by(Violation.created_at.desc())
                .limit(5)
                .all()
            )

        recent_activity = []
        for v in recent_violations:
            inspection = v.inspection
            recent_activity.append({
                "inspection_name": inspection.inspection_name if inspection else "Unknown",
                "violation_name": v.violation_name,
                "severity": v.severity,
                "timestamp": v.created_at,
            })

        return {
            "overview": {
                "workers_detected": total_workers,
                "total_violations": total_violations,
                "compliance_score": round(float(avg_compliance), 2),
                "inspection_status": latest.inspection_status if latest else "pending",
                "compliance_trend": compliance_trend,
                "compliance_delta": abs(compliance_delta),
            },
            "violation_breakdown": breakdown,
            "inspection_history": history,
            "latest_inspection": latest,
            "recent_activity": recent_activity,
        }