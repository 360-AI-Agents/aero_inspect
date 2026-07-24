from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class SafetyRule(Base):
    __tablename__ = "safety_rules"

    id = Column(Integer, primary_key=True, index=True)
    manual_id = Column(Integer, ForeignKey("safety_manuals.id"), nullable=True)

    category = Column(String(100), nullable=False)       # helmet, vest, fall_protection, etc.
    rule_text = Column(String(300), nullable=False)       # human-readable rule
    severity = Column(String(50), nullable=False, default="medium")

    # Matching condition, stored as JSON text. Two supported shapes:
    # {"type": "flag", "field": "helmet_missing", "equals": true}
    # {"type": "threshold", "field": "height_meters", "operator": ">=", "value": 2,
    #   "additional_field": "harness_worn", "additional_equals": false}
    condition = Column(String(500), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())