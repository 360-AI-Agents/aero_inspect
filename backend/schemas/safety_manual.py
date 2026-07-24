from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class SafetyManualResponse(BaseModel):
    id: int
    manual_name: str
    organization: Optional[str] = None
    region: Optional[str] = None
    version: Optional[str] = None
    status: str
    file_path: str
    uploaded_at: datetime

    class Config:
        from_attributes = True