from pydantic import BaseModel
from typing import List, Optional


class LiveFinding(BaseModel):
    category: str
    finding: str
    severity: str
    confidence: float
    count: int


class LiveWorker(BaseModel):
    worker_id: int
    bbox: Optional[List[int]] = None
    helmet: Optional[bool] = None
    vest: Optional[bool] = None
    mask: Optional[bool] = None
    violations: List[str] = []
    violation_count: int = 0
    image: Optional[str] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    violation_duration_seconds: Optional[float] = None
    total_violation_events: Optional[int] = None
    repeat_offender: Optional[bool] = None
    evidence_history: Optional[List[str]] = []


class LiveEvent(BaseModel):
    event_id: int
    worker_id: int
    transition: str
    violations: List[str] = []
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    status: str
    duration_seconds: Optional[float] = None
    evidence_image: Optional[str] = None


class LiveDetectionPayload(BaseModel):
    camera_name: str
    location: str
    timestamp: str
    workers_detected: int
    overall_compliance: float
    findings: List[LiveFinding] = []
    workers: List[LiveWorker] = []
    events: List[LiveEvent] = []