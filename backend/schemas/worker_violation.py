from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class WorkerViolationResponse(BaseModel):
    id: int
    inspection_id: int
    worker_id: int
    violations: Optional[str]
    status: str
    transition: Optional[str]
    first_seen: Optional[datetime]
    last_seen: Optional[datetime]
    duration_seconds: float
    repeat_offender: bool
    total_violation_events: int
    evidence_image_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True