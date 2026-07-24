from pydantic import BaseModel
from typing import Optional


class SettingsResponse(BaseModel):
    id: int
    flagged_threshold: float
    unsafe_threshold: float
    alert_email: Optional[str] = None

    class Config:
        from_attributes = True


class SettingsUpdate(BaseModel):
    flagged_threshold: Optional[float] = None
    unsafe_threshold: Optional[float] = None
    alert_email: Optional[str] = None