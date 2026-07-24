from fastapi import APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import SessionLocal
from backend.models.inspection import Inspection
from backend.models.finding import Finding

router = APIRouter(
    prefix="/api/v1/statistics",
    tags=["Statistics"]
)


@router.get("/")
def get_statistics():

    db: Session = SessionLocal()

    try:

        total_inspections = db.query(Inspection).count()

        total_workers = db.query(
            func.sum(Inspection.workers_detected)
        ).scalar() or 0

        total_findings = db.query(Finding).count()

        avg_score = db.query(
            func.avg(Inspection.compliance_score)
        ).scalar() or 100

        safe = db.query(Inspection).filter(
            Inspection.inspection_status == "Safe"
        ).count()

        unsafe = total_inspections - safe

        ppe = db.query(Finding).filter(
            Finding.category == "PPE"
        ).count()

        safety = db.query(Finding).filter(
            Finding.category == "Safety"
        ).count()

        equipment = db.query(Finding).filter(
            Finding.category == "Equipment"
        ).count()

        return {
            "overview": {
                "total_inspections": total_inspections,
                "workers_detected": total_workers,
                "total_findings": total_findings,
                "average_compliance": round(float(avg_score), 2)
            },
            "site_status": {
                "safe": safe,
                "unsafe": unsafe
            },
            "findings": {
                "ppe": ppe,
                "safety": safety,
                "equipment": equipment
            }
        }

    finally:
        db.close()