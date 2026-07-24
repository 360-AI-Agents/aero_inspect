import jwt
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.models.user import User
from backend.core.security import hash_password, verify_password

SECRET_KEY = "aeroinspect-dev-secret-change-in-production"
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


class AuthService:

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str):
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None, None
        if not verify_password(password, user.hashed_password):
            return None, None
        if not user.is_active:
            return None, "disabled"
        if user.approval_status == "pending":
            return None, "pending"
        if user.approval_status == "rejected":
            return None, "rejected"
        return user, None

    @staticmethod
    def register_user(db: Session, username: str, email: str, password: str, role: str):
        existing_username = db.query(User).filter(User.username == username).first()
        if existing_username:
            raise ValueError("Username already taken")

        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            raise ValueError("Email already registered")

        if role not in ["admin", "inspector"]:
            raise ValueError("Invalid role")

        # Admins go through manual approval; inspectors are meant to be created
        # by an admin via the Users page, but if someone self-registers as one
        # here, they also require approval for the same safety reason.
        approval_status = "pending"

        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role=role,
            is_active=True,
            approval_status=approval_status,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def create_access_token(user: User) -> str:
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
            "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS),
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def decode_token(token: str):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    @staticmethod
    def seed_demo_user(db: Session):
        existing = db.query(User).filter(User.username == "admin").first()
        if existing:
            return existing

        user = User(
            username="admin",
            email="admin@amconstructions.example.in",
            hashed_password=hash_password("admin123"),
            role="admin",
            is_active=True,
            approval_status="approved",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def seed_demo_inspector(db: Session):
        existing = db.query(User).filter(User.username == "inspector").first()
        if existing:
            return existing

        user = User(
            username="inspector",
            email="inspector@amconstructions.example.in",
            hashed_password=hash_password("inspector123"),
            role="inspector",
            is_active=True,
            approval_status="approved",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user