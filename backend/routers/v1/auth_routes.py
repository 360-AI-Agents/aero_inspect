from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.dependencies import get_db, get_current_user, require_admin
from backend.schemas.auth import LoginRequest, TokenResponse, CurrentUserResponse, RegisterRequest, RegisterResponse, GoogleLoginRequest
from backend.services.auth_service import AuthService
from backend.services.google_auth_service import GoogleAuthService
from backend.models.user import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    user, error_reason = AuthService.authenticate_user(db, credentials.username, credentials.password)

    if not user:
        if error_reason == "pending":
            raise HTTPException(status_code=403, detail="Your account is pending admin approval. Please check back soon.")
        if error_reason == "rejected":
            raise HTTPException(status_code=403, detail="Your registration was not approved. Please contact your administrator.")
        if error_reason == "disabled":
            raise HTTPException(status_code=403, detail="Your account has been disabled. Please contact your administrator.")
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = AuthService.create_access_token(user)
    return TokenResponse(access_token=token, username=user.username, role=user.role)


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = AuthService.register_user(db, payload.username, payload.email, payload.password, payload.role)
        return RegisterResponse(
            message="Registration successful. Your account is pending admin approval.",
            username=user.username,
            approval_status=user.approval_status,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/google", response_model=TokenResponse)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)):
    try:
        google_data = GoogleAuthService.verify_google_token(payload.id_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    email = google_data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email on file")

    user = GoogleAuthService.find_existing_user_by_email(db, email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="No account found for this Google email. Please register first, or ask your admin to create your account."
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Your account has been disabled. Please contact your administrator.")
    if user.approval_status == "pending":
        raise HTTPException(status_code=403, detail="Your account is pending admin approval.")
    if user.approval_status == "rejected":
        raise HTTPException(status_code=403, detail="Your registration was not approved. Please contact your administrator.")

    token = AuthService.create_access_token(user)
    return TokenResponse(access_token=token, username=user.username, role=user.role)


@router.get("/pending-approvals")
def list_pending_approvals(db: Session = Depends(get_db), admin=Depends(require_admin)):
    return db.query(User).filter(User.approval_status == "pending").all()


@router.patch("/approve/{user_id}")
def approve_user(user_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.approval_status = "approved"
    db.commit()
    db.refresh(user)
    return {"message": f"{user.username} approved successfully"}


@router.patch("/reject/{user_id}")
def reject_user(user_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.approval_status = "rejected"
    db.commit()
    db.refresh(user)
    return {"message": f"{user.username} rejected"}


@router.get("/me", response_model=CurrentUserResponse)
def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.post("/seed-demo-user")
def seed_demo_user(db: Session = Depends(get_db)):
    user = AuthService.seed_demo_user(db)
    return {"message": "Demo admin ready", "username": user.username, "password": "admin123"}


@router.post("/seed-demo-inspector")
def seed_demo_inspector(db: Session = Depends(get_db)):
    user = AuthService.seed_demo_inspector(db)
    return {"message": "Demo inspector ready", "username": user.username, "password": "inspector123"}