from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class Finding(Base):
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, index=True)

    inspection_id = Column(
        Integer,
        ForeignKey("inspections.id", ondelete="CASCADE"),
        nullable=False
    )

    category = Column(String(100), nullable=False)

    finding_name = Column(String(150), nullable=False)

    severity = Column(String(50), nullable=False)

    confidence = Column(Float, nullable=False)

    count = Column(Integer, default=1)

    inspection = relationship(
        "Inspection",
        back_populates="findings"
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )