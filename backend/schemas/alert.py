from pydantic import BaseModel
from datetime import datetime
from typing import List


class AlertItem(BaseModel):
    inspection_id: int
    inspection_name: str
    camera_name: str
    location: str
    violation_name: str
    category: str
    severity: str
    count: int
    risk_level: str
    inspection_status: str
    timestamp: datetime


class AlertsSummary(BaseModel):
    critical: int
    high: int
    medium: int
    low: int


class AlertsResponse(BaseModel):
    summary: AlertsSummary
    critical: List[AlertItem]
    high: List[AlertItem]
    medium: List[AlertItem]
    low: List[AlertItem]