from pydantic import BaseModel
from datetime import datetime


class ViolationCreate(BaseModel):
    category: str
    violation_name: str
    severity: str = "medium"
    confidence: float = 0.0
    count: int = 1


class ViolationResponse(BaseModel):
    id: int
    category: str
    violation_name: str
    severity: str
    confidence: float
    count: int
    created_at: datetime

    class Config:
        from_attributes = True