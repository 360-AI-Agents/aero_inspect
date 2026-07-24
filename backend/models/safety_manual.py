from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from backend.database import Base


class SafetyManual(Base):
    __tablename__ = "safety_manuals"

    id = Column(Integer, primary_key=True, index=True)
    manual_name = Column(String(200), nullable=False)
    organization = Column(String(150), nullable=True)
    region = Column(String(100), nullable=True)
    version = Column(String(50), nullable=True)
    file_path = Column(String(400), nullable=False)
    status = Column(String(50), nullable=False, default="uploaded")
    # status values: uploaded | processing | processed | active | inactive

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())