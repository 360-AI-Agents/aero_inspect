from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from backend.database import Base


class WorkerViolation(Base):
    __tablename__ = "worker_violations"

    id = Column(Integer, primary_key=True, index=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False, index=True)
    worker_id = Column(Integer, nullable=False, index=True)
    employee_id = Column(String, nullable=True, index=True)
    event_id = Column(Integer, nullable=True)

    violations = Column(Text, nullable=True)
    status = Column(String, default="open")
    transition = Column(String, nullable=True)
    alert_type = Column(String, default="ppe_violation")

    first_seen = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, default=0.0)

    repeat_offender = Column(Boolean, default=False)
    total_violation_events = Column(Integer, default=1)

    evidence_image_path = Column(String, nullable=True)
    evidence_image_url = Column(String, nullable=True)

    clip_path = Column(String, nullable=True)
    clip_url = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())