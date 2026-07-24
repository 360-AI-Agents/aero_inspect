from sqlalchemy import Column, Integer, Float, String, DateTime
from sqlalchemy.sql import func

from backend.database import Base


class Settings(Base):
    """
    Single-row table holding platform-wide configuration.
    We always read/write the row where id = 1 — no multi-tenant
    settings needed yet.
    """
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    flagged_threshold = Column(Float, nullable=False, default=90.0)
    unsafe_threshold = Column(Float, nullable=False, default=70.0)
    alert_email = Column(String(150), nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())