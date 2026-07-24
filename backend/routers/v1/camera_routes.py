from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.dependencies import get_db, get_current_user
from backend.services.camera_service import CameraService
from backend.models.user import User
from backend.models.site_assignment import SiteAssignment

router = APIRouter(prefix="/cameras", tags=["Cameras"])


def _get_allowed_locations(db: Session, current_user: User):
    """Returns None if user is admin (no restriction), else a list of allowed locations."""
    if current_user.role == "admin":
        return None
    assignments = db.query(SiteAssignment).filter(SiteAssignment.user_id == current_user.id).all()
    return [a.location for a in assignments]


@router.get("/")
def list_cameras(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cameras = CameraService.get_all(db)
    allowed = _get_allowed_locations(db, current_user)
    if allowed is not None:
        cameras = [c for c in cameras if c.location in allowed]
    return cameras


@router.get("/{camera_id}")
def get_camera(camera_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    camera = CameraService.get_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    allowed = _get_allowed_locations(db, current_user)
    if allowed is not None and camera.location not in allowed:
        raise HTTPException(status_code=403, detail="You are not assigned to this site")
    return camera


@router.post("/")
def create_camera(camera_name: str, location: str, source_type: str = "cctv", db: Session = Depends(get_db)):
    return CameraService.create(db, camera_name, location, source_type)


@router.patch("/{camera_id}/status")
def update_camera_status(camera_id: int, status: str, db: Session = Depends(get_db)):
    camera = CameraService.update_status(db, camera_id, status)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.delete("/{camera_id}")
def delete_camera(camera_id: int, db: Session = Depends(get_db)):
    deleted = CameraService.delete(db, camera_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"message": "Camera deleted successfully"}