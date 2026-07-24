from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func

from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(150), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="inspector")  # admin | inspector | viewer
    is_active = Column(Boolean, default=True)
    approval_status = Column(String(50), default="approved")  # approved | pending | rejected
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())