from sqlalchemy.orm import Session
from backend.models.violation import Violation


class ViolationRepository:

    @staticmethod
    def get_by_inspection(db: Session, inspection_id: int):
        return db.query(Violation).filter(Violation.inspection_id == inspection_id).all()

    @staticmethod
    def bulk_create(db: Session, inspection_id: int, violations: list):
        db_violations = []
        for v in violations:
            db_violation = Violation(
                inspection_id=inspection_id,
                category=v.category,
                violation_name=v.violation_name,
                severity=v.severity,
                confidence=v.confidence,
                count=v.count
            )
            db.add(db_violation)
            db_violations.append(db_violation)

        db.commit()
        for dv in db_violations:
            db.refresh(dv)

        return db_violations

    @staticmethod
    def get_all(db: Session):
        return db.query(Violation).order_by(Violation.created_at.desc()).all()