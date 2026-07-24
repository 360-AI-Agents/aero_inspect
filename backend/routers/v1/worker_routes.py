import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.dependencies import get_db, require_admin, get_current_user
from backend.models.worker import Worker
from backend.models.worker_violation import WorkerViolation
from backend.models.user import User
from backend.models.site_assignment import SiteAssignment
from backend.schemas.worker import WorkerCreate, WorkerUpdate, WorkerResponse

router = APIRouter(prefix="/workers", tags=["Workers"])

WORKER_PHOTO_DIR = "backend/uploads/worker_photos"
os.makedirs(WORKER_PHOTO_DIR, exist_ok=True)


class LinkTrackerRequest(BaseModel):
    tracked_worker_id: int
    employee_id: str


@router.get("/", response_model=List[WorkerResponse])
def list_workers(
    site: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Worker)

    if current_user.role != "admin":
        assignments = db.query(SiteAssignment).filter(SiteAssignment.user_id == current_user.id).all()
        allowed_sites = [a.location for a in assignments]
        query = query.filter(Worker.assigned_site.in_(allowed_sites))

    if site:
        query = query.filter(Worker.assigned_site == site)

    return query.order_by(Worker.name).all()


@router.get("/reference-photos/all")
def get_all_reference_photos(db: Session = Depends(get_db)):
    """
    Public-facing endpoint for the AI/ReID pipeline to fetch every registered
    worker's employee_id + reference photo URL, so it can compare detected
    faces against these and auto-link matches via POST /workers/link-tracker.
    """
    workers = db.query(Worker).filter(Worker.reference_photo_url.isnot(None)).all()

    return [
        {
            "employee_id": w.employee_id,
            "name": w.name,
            "assigned_site": w.assigned_site,
            "reference_photo_url": f"{w.reference_photo_url}",
        }
        for w in workers
    ]


@router.get("/{worker_id}", response_model=WorkerResponse)
def get_worker(worker_id: int, db: Session = Depends(get_db)):
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    return worker


@router.get("/{worker_id}/history")
def get_worker_history(worker_id: int, db: Session = Depends(get_db)):
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    records = (
        db.query(WorkerViolation)
        .filter(WorkerViolation.employee_id == worker.employee_id)
        .order_by(WorkerViolation.first_seen.desc())
        .all()
    )

    total_violations = len(records)
    total_duration = sum(r.duration_seconds or 0 for r in records)

    violation_type_counts = {}
    for r in records:
        if r.violations:
            for v in r.violations.split(", "):
                violation_type_counts[v] = violation_type_counts.get(v, 0) + 1

    return {
        "worker": {
            "id": worker.id,
            "employee_id": worker.employee_id,
            "name": worker.name,
            "role": worker.role,
            "company": worker.company,
            "assigned_site": worker.assigned_site,
            "reference_photo_url": worker.reference_photo_url,
        },
        "summary": {
            "total_violation_events": total_violations,
            "total_duration_seconds": total_duration,
            "violation_type_counts": violation_type_counts,
        },
        "records": [
            {
                "id": r.id,
                "violations": r.violations,
                "status": r.status,
                "first_seen": r.first_seen,
                "last_seen": r.last_seen,
                "duration_seconds": r.duration_seconds,
                "evidence_image_url": r.evidence_image_url,
                "repeat_offender": r.repeat_offender,
            }
            for r in records
        ],
    }


@router.post("/", response_model=WorkerResponse)
def create_worker(payload: WorkerCreate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    existing = db.query(Worker).filter(Worker.employee_id == payload.employee_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Employee ID already registered")

    worker = Worker(**payload.dict())
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return worker


@router.post("/{worker_id}/photo")
def upload_worker_photo(worker_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), admin=Depends(require_admin)):
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    ext = os.path.splitext(file.filename)[1] or ".jpg"
    unique_name = f"worker_{worker.employee_id}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(WORKER_PHOTO_DIR, unique_name)

    with open(filepath, "wb") as f:
        f.write(file.file.read())

    worker.reference_photo_url = f"/worker_photos/{unique_name}"
    db.commit()

    return {"message": "Worker photo saved", "url": worker.reference_photo_url}


@router.put("/{worker_id}", response_model=WorkerResponse)
def update_worker(worker_id: int, payload: WorkerUpdate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(worker, field, value)

    db.commit()
    db.refresh(worker)
    return worker


@router.delete("/{worker_id}")
def delete_worker(worker_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    db.delete(worker)
    db.commit()
    return {"detail": "Worker removed"}


@router.post("/link-tracker")
def link_tracker(payload: LinkTrackerRequest, db: Session = Depends(get_db)):
    """
    Shared contract endpoint (matches Ajay's AI-side integration).
    Called automatically by Ajay's ReID pipeline when it has a confident
    face match (LBPH distance <= 70), or manually by an admin from the
    Workers page UI for lower-confidence cases.

    No auth required — this endpoint is called by the AI pipeline directly,
    not through a logged-in browser session, matching the same pattern as
    /api/live_detection/ and /workers/reference-photos/all.

    Links a temporary tracked_worker_id to a permanent employee_id, and
    retroactively attaches ALL existing WorkerViolation records for that
    tracking ID to the linked worker's history — past and future both.
    """
    worker = db.query(Worker).filter(Worker.employee_id == payload.employee_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail=f"No registered worker with employee_id '{payload.employee_id}'")

    worker.tracked_worker_id = payload.tracked_worker_id
    db.commit()
    db.refresh(worker)

    updated_count = (
        db.query(WorkerViolation)
        .filter(WorkerViolation.worker_id == payload.tracked_worker_id)
        .update({"employee_id": payload.employee_id})
    )
    db.commit()

    return {
        "message": "Tracking ID linked successfully",
        "employee_id": payload.employee_id,
        "tracked_worker_id": payload.tracked_worker_id,
        "historical_violations_linked": updated_count,
    }