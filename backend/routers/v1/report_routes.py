from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.dependencies import get_db, get_current_user
from backend.services.report_service import ReportService
from backend.services.inspection_service import InspectionService
from backend.models.user import User
from backend.models.site_assignment import SiteAssignment
from backend.models.camera import Camera

router = APIRouter(prefix="/reports", tags=["Reports"])


def _check_access(db: Session, current_user: User, inspection_id: int):
    if current_user.role == "admin":
        return
    inspection = InspectionService.get_inspection(db, inspection_id)
    if not inspection:
        return
    if inspection.camera_id:
        cam = db.query(Camera).filter(Camera.id == inspection.camera_id).first()
        if cam:
            assignments = db.query(SiteAssignment).filter(SiteAssignment.user_id == current_user.id).all()
            allowed = [a.location for a in assignments]
            if cam.location not in allowed:
                raise HTTPException(status_code=403, detail="You are not assigned to this site")


@router.get("/{inspection_id}")
def get_report(inspection_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _check_access(db, current_user, inspection_id)
    report = ReportService.generate_report(db, inspection_id)
    if not report:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return report


@router.get("/{inspection_id}/pdf")
def get_report_pdf(inspection_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _check_access(db, current_user, inspection_id)
    filepath = ReportService.generate_pdf(db, inspection_id)
    if not filepath:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return FileResponse(
        filepath,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=AeroInspect_Report_{inspection_id}.pdf"}
    )