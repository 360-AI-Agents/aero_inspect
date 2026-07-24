import os
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from backend.schemas.live_detection import LiveDetectionPayload
from backend.services.live_detection_service import LiveDetectionService
from backend.models.worker_violation import WorkerViolation

router = APIRouter(prefix="/api/live_detection", tags=["Live Detection"])

EVIDENCE_DIR = "backend/uploads/evidence"
os.makedirs(EVIDENCE_DIR, exist_ok=True)

CLIPS_DIR = "backend/uploads/clips"
os.makedirs(CLIPS_DIR, exist_ok=True)

STREAM_DIR = "backend/uploads/stream"
os.makedirs(STREAM_DIR, exist_ok=True)


@router.post("/")
def receive_live_detection(payload: LiveDetectionPayload, db: Session = Depends(get_db)):
    try:
        result = LiveDetectionService.process_live_payload(db, payload)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process live detection: {str(e)}")


@router.post("/evidence")
def upload_evidence_photo(
    worker_id: int = Form(...),
    inspection_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    worker_violation = (
        db.query(WorkerViolation)
        .filter(
            WorkerViolation.inspection_id == inspection_id,
            WorkerViolation.worker_id == worker_id,
        )
        .order_by(WorkerViolation.created_at.desc())
        .first()
    )
    if not worker_violation:
        raise HTTPException(status_code=404, detail="No matching worker violation record found — send the JSON event first")

    ext = os.path.splitext(file.filename)[1] or ".jpg"
    unique_name = f"worker_{worker_id}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(EVIDENCE_DIR, unique_name)

    with open(filepath, "wb") as f:
        f.write(file.file.read())

    worker_violation.evidence_image_url = f"/evidence/{unique_name}"
    db.commit()

    return {"message": "Evidence photo saved", "url": worker_violation.evidence_image_url}


@router.post("/clip")
def upload_violation_clip(
    worker_id: int = Form(...),
    inspection_id: int = Form(...),
    file: UploadFile = File(...),
    event_id: int = Form(None),
    db: Session = Depends(get_db),
):
    """
    Attaches a clip to a specific WorkerViolation record. If event_id is
    provided, matches on that specifically (correct when a worker has
    multiple violation events within the same inspection). If not provided,
    falls back to the most recent matching record for worker_id+inspection_id,
    same behavior as before.
    """
    query = db.query(WorkerViolation).filter(
        WorkerViolation.inspection_id == inspection_id,
        WorkerViolation.worker_id == worker_id,
    )

    if event_id is not None:
        query = query.filter(WorkerViolation.event_id == event_id)

    worker_violation = query.order_by(WorkerViolation.created_at.desc()).first()

    if not worker_violation:
        raise HTTPException(status_code=404, detail="No matching worker violation record found — send the JSON event first")

    ext = os.path.splitext(file.filename)[1] or ".mp4"
    unique_name = f"clip_{worker_id}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(CLIPS_DIR, unique_name)

    with open(filepath, "wb") as f:
        f.write(file.file.read())

    worker_violation.clip_path = filepath
    worker_violation.clip_url = f"/clips/{unique_name}"
    db.commit()

    return {"message": "Violation clip saved", "url": worker_violation.clip_url}
    

@router.post("/stream/segment")
def upload_stream_segment(
    camera_name: str = Form(...),
    filename: str = Form(...),
    file_type: str = Form(...),
    file: UploadFile = File(...),
):
    safe_camera_name = camera_name.replace("/", "_").replace("\\", "_")
    camera_dir = os.path.join(STREAM_DIR, safe_camera_name)
    os.makedirs(camera_dir, exist_ok=True)

    filepath = os.path.join(camera_dir, filename)

    with open(filepath, "wb") as f:
        f.write(file.file.read())

    return {
        "message": f"{file_type} saved",
        "camera_name": safe_camera_name,
        "filename": filename,
        "url": f"/stream/{safe_camera_name}/{filename}",
    }


@router.get("/worker-violations/{inspection_id}")
def get_worker_violations(inspection_id: int, db: Session = Depends(get_db)):
    records = (
        db.query(WorkerViolation)
        .filter(WorkerViolation.inspection_id == inspection_id)
        .order_by(WorkerViolation.created_at.desc())
        .all()
    )
    return records


@router.delete("/worker-violations/{record_id}")
def delete_worker_violation(record_id: int, db: Session = Depends(get_db)):
    record = db.query(WorkerViolation).filter(WorkerViolation.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Worker violation record not found")

    if record.evidence_image_url:
        filename = record.evidence_image_url.replace("/evidence/", "")
        filepath = os.path.join(EVIDENCE_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)

    if record.clip_url:
        clip_filename = record.clip_url.replace("/clips/", "")
        clip_filepath = os.path.join(CLIPS_DIR, clip_filename)
        if os.path.exists(clip_filepath):
            os.remove(clip_filepath)

    db.delete(record)
    db.commit()
    return {"message": "Worker violation record deleted successfully"}


@router.get("/worker-counts/{inspection_id}")
def get_worker_counts(inspection_id: int, db: Session = Depends(get_db)):
    records = (
        db.query(WorkerViolation)
        .filter(WorkerViolation.inspection_id == inspection_id)
        .all()
    )

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    today_workers = set()
    week_workers = set()
    total_workers = set()

    for r in records:
        total_workers.add(r.worker_id)
        ts = r.first_seen or r.created_at
        if ts:
            ts_naive = ts.replace(tzinfo=None) if ts.tzinfo else ts
            if ts_naive >= today_start:
                today_workers.add(r.worker_id)
            if ts_naive >= week_start:
                week_workers.add(r.worker_id)

    return {
        "today": len(today_workers),
        "this_week": len(week_workers),
        "total": len(total_workers),
    }