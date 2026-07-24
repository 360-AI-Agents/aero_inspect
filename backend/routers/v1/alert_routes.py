from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.dependencies import get_db, get_current_user
from backend.schemas.alert import AlertsResponse
from backend.services.alert_service import AlertService
from backend.models.user import User
from backend.models.site_assignment import SiteAssignment

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("/", response_model=AlertsResponse)
def get_alerts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    allowed_locations = None
    if current_user.role != "admin":
        assignments = db.query(SiteAssignment).filter(SiteAssignment.user_id == current_user.id).all()
        allowed_locations = [a.location for a in assignments]
    return AlertService.get_risk_heatmap(db, allowed_locations=allowed_locations)