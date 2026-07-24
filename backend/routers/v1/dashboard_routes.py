from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.dependencies import get_db, get_current_user
from backend.schemas.dashboard import DashboardResponse
from backend.services.dashboard_service import DashboardService
from backend.models.user import User
from backend.models.site_assignment import SiteAssignment

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    allowed_locations = None
    if current_user.role != "admin":
        assignments = db.query(SiteAssignment).filter(SiteAssignment.user_id == current_user.id).all()
        allowed_locations = [a.location for a in assignments]
    return DashboardService.get_dashboard_data(db, allowed_locations=allowed_locations)