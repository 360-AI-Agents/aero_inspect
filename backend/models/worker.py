from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from backend.database import Base


class Worker(Base):
    __tablename__ = "workers"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    company = Column(String, nullable=True)
    role = Column(String, nullable=True)
    assigned_site = Column(String, nullable=False, index=True)

    shift_start = Column(String, nullable=True)
    shift_end = Column(String, nullable=True)
    weekly_off_day = Column(String, nullable=True)

    reference_photo_url = Column(String, nullable=True)
    tracked_worker_id = Column(Integer, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())