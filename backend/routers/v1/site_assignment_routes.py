from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.database import get_db
from backend.dependencies import require_admin, get_current_user
from backend.models.site_assignment import SiteAssignment
from backend.models.user import User
from backend.schemas.site_assignment import SiteAssignmentCreate, SiteAssignmentResponse, UserSitesResponse

router = APIRouter(prefix="/site-assignments", tags=["site-assignments"])


@router.get("/", response_model=List[SiteAssignmentResponse])
def list_assignments(db: Session = Depends(get_db), admin=Depends(require_admin)):
    assignments = db.query(SiteAssignment).all()
    results = []
    for a in assignments:
        user = db.query(User).filter(User.id == a.user_id).first()
        results.append(SiteAssignmentResponse(
            id=a.id, user_id=a.user_id, username=user.username if user else None,
            location=a.location, alert_email=a.alert_email, assigned_at=a.assigned_at,
        ))
    return results


@router.post("/", response_model=SiteAssignmentResponse)
def create_assignment(payload: SiteAssignmentCreate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.query(SiteAssignment).filter(
        SiteAssignment.user_id == payload.user_id,
        SiteAssignment.location == payload.location,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="This user is already assigned to this site")

    assignment = SiteAssignment(
        user_id=payload.user_id,
        location=payload.location,
        alert_email=payload.alert_email or user.email,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return SiteAssignmentResponse(
        id=assignment.id, user_id=assignment.user_id, username=user.username,
        location=assignment.location, alert_email=assignment.alert_email, assigned_at=assignment.assigned_at,
    )


@router.delete("/{assignment_id}")
def delete_assignment(assignment_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    assignment = db.query(SiteAssignment).filter(SiteAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.delete(assignment)
    db.commit()
    return {"detail": "Assignment removed"}


@router.get("/my-sites", response_model=UserSitesResponse)
def get_my_sites(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "admin":
        return UserSitesResponse(locations=[])

    assignments = db.query(SiteAssignment).filter(SiteAssignment.user_id == current_user.id).all()
    return UserSitesResponse(locations=[a.location for a in assignments])