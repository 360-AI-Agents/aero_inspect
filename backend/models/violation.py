from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class Violation(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, index=True)

    inspection_id = Column(
        Integer,
        ForeignKey("inspections.id", ondelete="CASCADE"),
        nullable=False
    )

    category = Column(String(100), nullable=False)       # helmet, vest, scaffolding, etc.
    violation_name = Column(String(150), nullable=False)
    severity = Column(String(50), nullable=False, default="medium")
    confidence = Column(Float, nullable=False, default=0.0)
    count = Column(Integer, default=1)

    inspection = relationship("Inspection", back_populates="violations")

    created_at = Column(DateTime(timezone=True), server_default=func.now())