from pydantic import BaseModel
from datetime import datetime


class ReportResponse(BaseModel):
    id: int
    inspection_id: int
    report_title: str
    summary: str | None = None
    file_path: str | None = None
    generated_at: datetime

    class Config:
        from_attributes = True