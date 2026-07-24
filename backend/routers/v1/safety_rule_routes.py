from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from backend.schemas.safety_rule import SafetyRuleResponse
from backend.services.rule_engine_service import RuleEngineService
from backend.models.safety_rule import SafetyRule

router = APIRouter(prefix="/safety-rules", tags=["Safety Rules"])


@router.get("/", response_model=list[SafetyRuleResponse])
def list_rules(db: Session = Depends(get_db)):
    return db.query(SafetyRule).order_by(SafetyRule.created_at.desc()).all()


@router.get("/active", response_model=list[SafetyRuleResponse])
def list_active_rules(db: Session = Depends(get_db)):
    """
    Returns only the rules currently driving live detection —
    i.e., rules belonging to whichever manual is currently active.
    """
    return RuleEngineService.get_active_rules(db)


@router.post("/seed-demo", response_model=list[SafetyRuleResponse])
def seed_demo_rules(db: Session = Depends(get_db)):
    return RuleEngineService.seed_demo_rules(db)