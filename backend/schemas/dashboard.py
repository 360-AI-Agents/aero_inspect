from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
from backend.schemas.inspection import InspectionResponse


class DashboardOverview(BaseModel):
    workers_detected: int
    total_violations: int
    compliance_score: float
    inspection_status: str
    compliance_trend: str
    compliance_delta: float


class ActivityItem(BaseModel):
    inspection_name: str
    violation_name: str
    severity: str
    timestamp: datetime


class DashboardResponse(BaseModel):
    overview: DashboardOverview
    violation_breakdown: Dict[str, int]
    inspection_history: List[InspectionResponse]
    latest_inspection: Optional[InspectionResponse] = None
    recent_activity: List[ActivityItem] = []