from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.dependencies import get_db, require_admin
from backend.schemas.settings import SettingsResponse, SettingsUpdate
from backend.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    return SettingsService.get_settings(db)


@router.put("/", response_model=SettingsResponse)
def update_settings(updates: SettingsUpdate, db: Session = Depends(get_db), current_admin=Depends(require_admin)):
    return SettingsService.update_settings(db, updates)