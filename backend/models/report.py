from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)

    inspection_id = Column(
        Integer,
        ForeignKey("inspections.id", ondelete="CASCADE"),
        nullable=False
    )

    report_title = Column(String(200), nullable=False)
    summary = Column(Text, nullable=True)
    file_path = Column(String(300), nullable=True)  # path to generated PDF, if saved to disk

    inspection = relationship("Inspection", back_populates="reports")

    generated_at = Column(DateTime(timezone=True), server_default=func.now())