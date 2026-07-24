from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class SafetyRuleResponse(BaseModel):
    id: int
    manual_id: Optional[int] = None
    category: str
    rule_text: str
    severity: str
    condition: str
    created_at: datetime

    class Config:
        from_attributes = True