from sqlalchemy.orm import Session
from backend.repositories.inspection_repository import InspectionRepository


class InspectionService:

    @staticmethod
    def get_all_inspections(db: Session, skip: int = 0, limit: int = 50):
        return InspectionRepository.get_all(db, skip, limit)

    @staticmethod
    def get_inspection(db: Session, inspection_id: int):
        return InspectionRepository.get_by_id(db, inspection_id)

    @staticmethod
    def create_inspection(db: Session, inspection):
        return InspectionRepository.create(db, inspection)

    @staticmethod
    def update_inspection(db: Session, inspection_id: int, inspection):
        return InspectionRepository.update(db, inspection_id, inspection)

    @staticmethod
    def delete_inspection(db: Session, inspection_id: int):
        return InspectionRepository.delete(db, inspection_id)