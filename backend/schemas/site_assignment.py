from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class SiteAssignmentCreate(BaseModel):
    user_id: int
    location: str
    alert_email: Optional[str] = None


class SiteAssignmentResponse(BaseModel):
    id: int
    user_id: int
    username: Optional[str] = None
    location: str
    alert_email: Optional[str]
    assigned_at: datetime

    class Config:
        from_attributes = True


class UserSitesResponse(BaseModel):
    locations: List[str]