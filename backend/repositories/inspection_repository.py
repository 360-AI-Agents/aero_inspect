from sqlalchemy.orm import Session
from backend.models.inspection import Inspection


class InspectionRepository:

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 50):
        return (
            db.query(Inspection)
            .order_by(Inspection.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_by_id(db: Session, inspection_id: int):
        return db.query(Inspection).filter(Inspection.id == inspection_id).first()

    @staticmethod
    def get_latest(db: Session):
        return db.query(Inspection).order_by(Inspection.created_at.desc()).first()

    @staticmethod
    def create(db: Session, inspection):
        db_inspection = Inspection(
            inspection_name=inspection.inspection_name,
            camera_id=inspection.camera_id,
            inspection_status="pending"
        )
        db.add(db_inspection)
        db.commit()
        db.refresh(db_inspection)
        return db_inspection

    @staticmethod
    def update(db: Session, inspection_id: int, inspection):
        db_inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
        if not db_inspection:
            return None

        update_data = inspection.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_inspection, field, value)

        db.commit()
        db.refresh(db_inspection)
        return db_inspection

    @staticmethod
    def update_detection_results(db: Session, inspection_id: int, workers_detected: int,
                                   total_violations: int, compliance_score: float, status: str):
        db_inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
        if not db_inspection:
            return None

        db_inspection.workers_detected = workers_detected
        db_inspection.total_violations = total_violations
        db_inspection.compliance_score = compliance_score
        db_inspection.inspection_status = status

        db.commit()
        db.refresh(db_inspection)
        return db_inspection

    @staticmethod
    def delete(db: Session, inspection_id: int):
        db_inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
        if not db_inspection:
            return False
        db.delete(db_inspection)
        db.commit()
        return True