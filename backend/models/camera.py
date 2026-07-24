from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    camera_name = Column(String(150), nullable=False)
    location = Column(String(150), nullable=False)
    source_type = Column(String(50), nullable=False, default="cctv")  # cctv | drone
    status = Column(String(50), nullable=False, default="active")     # active | inactive | offline

    inspections = relationship(
        "Inspection",
        back_populates="camera"
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())