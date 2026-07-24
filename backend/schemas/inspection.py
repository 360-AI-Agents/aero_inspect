from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

from backend.schemas.violation import ViolationResponse


class InspectionCreate(BaseModel):
    inspection_name: str
    camera_id: Optional[int] = None


class InspectionUpdate(BaseModel):
    inspection_name: Optional[str] = None
    inspection_status: Optional[str] = None


class InspectionResponse(BaseModel):
    id: int
    inspection_name: str
    camera_id: Optional[int] = None
    workers_detected: int
    total_violations: int
    compliance_score: float
    inspection_status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InspectionDetailResponse(InspectionResponse):
    violations: List[ViolationResponse] = []