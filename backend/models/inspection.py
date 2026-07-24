from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class Inspection(Base):
    __tablename__ = "inspections"

    id = Column(Integer, primary_key=True, index=True)
    inspection_name = Column(String(150), nullable=False)

    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    camera = relationship("Camera", back_populates="inspections")

    workers_detected = Column(Integer, default=0)
    total_violations = Column(Integer, default=0)
    compliance_score = Column(Float, default=100.0)
    inspection_status = Column(String(50), default="pending")

    violations = relationship(
        "Violation",
        back_populates="inspection",
        cascade="all, delete-orphan"
    )

    reports = relationship(
        "Report",
        back_populates="inspection",
        cascade="all, delete-orphan"
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())