from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class WorkerCreate(BaseModel):
    employee_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    assigned_site: str
    shift_start: Optional[str] = None
    shift_end: Optional[str] = None
    weekly_off_day: Optional[str] = None


class WorkerUpdate(BaseModel):
    employee_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    assigned_site: Optional[str] = None
    shift_start: Optional[str] = None
    shift_end: Optional[str] = None
    weekly_off_day: Optional[str] = None
    tracked_worker_id: Optional[int] = None


class WorkerResponse(BaseModel):
    id: int
    employee_id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    company: Optional[str]
    role: Optional[str]
    assigned_site: str
    shift_start: Optional[str]
    shift_end: Optional[str]
    weekly_off_day: Optional[str]
    reference_photo_url: Optional[str]
    tracked_worker_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True