from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from backend.database import Base


class SiteAssignment(Base):
    __tablename__ = "site_assignments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    location = Column(String, nullable=False, index=True)
    alert_email = Column(String, nullable=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())