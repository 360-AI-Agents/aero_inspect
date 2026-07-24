from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.dependencies import get_db, get_current_user
from backend.schemas.inspection import InspectionCreate, InspectionUpdate, InspectionResponse, InspectionDetailResponse
from backend.schemas.detection import DetectionEventCreate, RawDetectionCreate
from backend.services.inspection_service import InspectionService
from backend.services.detection_service import DetectionService
from backend.services.rule_engine_service import RuleEngineService
from backend.schemas.violation import ViolationCreate
from backend.models.user import User
from backend.models.site_assignment import SiteAssignment
from backend.models.camera import Camera

router = APIRouter(prefix="/inspections", tags=["Inspections"])


def _get_allowed_locations(db: Session, current_user: User):
    if current_user.role == "admin":
        return None
    assignments = db.query(SiteAssignment).filter(SiteAssignment.user_id == current_user.id).all()
    return [a.location for a in assignments]


@router.post("/", response_model=InspectionResponse)
def create_inspection(inspection: InspectionCreate, db: Session = Depends(get_db)):
    return InspectionService.create_inspection(db, inspection)


@router.get("/", response_model=list[InspectionResponse])
def list_inspections(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inspections = InspectionService.get_all_inspections(db, skip, limit)
    allowed = _get_allowed_locations(db, current_user)

    if allowed is not None:
        filtered = []
        for insp in inspections:
            if insp.camera_id:
                cam = db.query(Camera).filter(Camera.id == insp.camera_id).first()
                if cam and cam.location in allowed:
                    filtered.append(insp)
        inspections = filtered

    return inspections


@router.get("/{inspection_id}", response_model=InspectionDetailResponse)
def get_inspection(inspection_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inspection = InspectionService.get_inspection(db, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    allowed = _get_allowed_locations(db, current_user)
    if allowed is not None and inspection.camera_id:
        cam = db.query(Camera).filter(Camera.id == inspection.camera_id).first()
        if cam and cam.location not in allowed:
            raise HTTPException(status_code=403, detail="You are not assigned to this site")

    return inspection


@router.put("/{inspection_id}", response_model=InspectionResponse)
def update_inspection(inspection_id: int, inspection: InspectionUpdate, db: Session = Depends(get_db)):
    updated = InspectionService.update_inspection(db, inspection_id, inspection)
    if not updated:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return updated


@router.delete("/{inspection_id}")
def delete_inspection(inspection_id: int, db: Session = Depends(get_db)):
    deleted = InspectionService.delete_inspection(db, inspection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return {"message": "Inspection deleted successfully"}


@router.post("/{inspection_id}/detections")
def submit_detection_event(inspection_id: int, detection: DetectionEventCreate, db: Session = Depends(get_db)):
    result = DetectionService.process_detection_event(db, inspection_id, detection)
    if not result:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return result


@router.post("/{inspection_id}/detections/raw")
def submit_raw_detection(inspection_id: int, detection: RawDetectionCreate, db: Session = Depends(get_db)):
    matched = RuleEngineService.evaluate_detection(db, detection.dict())

    violations_payload = [ViolationCreate(**v) for v in matched]
    wrapped_event = DetectionEventCreate(
        workers_detected=detection.workers_detected,
        violations=violations_payload,
    )

    result = DetectionService.process_detection_event(db, inspection_id, wrapped_event)
    if not result:
        raise HTTPException(status_code=404, detail="Inspection not found")

    result["matched_rules"] = len(matched)
    return result