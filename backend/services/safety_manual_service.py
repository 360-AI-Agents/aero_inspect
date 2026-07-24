import os
import uuid
from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.models.safety_manual import SafetyManual
from backend.models.safety_rule import SafetyRule

UPLOAD_DIR = "backend/uploads/safety_manuals"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


class SafetyManualService:

    @staticmethod
    def save_file(file: UploadFile) -> str:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {ext}. Only PDF and DOCX are allowed.")

        unique_name = f"{uuid.uuid4().hex}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)

        with open(file_path, "wb") as f:
            f.write(file.file.read())

        return file_path

    @staticmethod
    def create_manual(db: Session, file: UploadFile, manual_name: str,
                       organization: str = None, region: str = None, version: str = None):
        file_path = SafetyManualService.save_file(file)

        manual = SafetyManual(
            manual_name=manual_name,
            organization=organization,
            region=region,
            version=version,
            file_path=file_path,
            status="uploaded",
        )
        db.add(manual)
        db.commit()
        db.refresh(manual)
        return manual

    @staticmethod
    def get_all(db: Session):
        return db.query(SafetyManual).order_by(SafetyManual.uploaded_at.desc()).all()

    @staticmethod
    def get_by_id(db: Session, manual_id: int):
        return db.query(SafetyManual).filter(SafetyManual.id == manual_id).first()

    @staticmethod
    def activate(db: Session, manual_id: int):
        # Only one manual can be active at a time.
        db.query(SafetyManual).filter(SafetyManual.status == "active").update({"status": "inactive"})

        manual = SafetyManualService.get_by_id(db, manual_id)
        if not manual:
            return None

        manual.status = "active"
        db.commit()
        db.refresh(manual)
        return manual

    @staticmethod
    def delete(db: Session, manual_id: int):
        manual = SafetyManualService.get_by_id(db, manual_id)
        if not manual:
            return False

        # Delete any AI-extracted (or seeded) rules tied to this manual first —
        # the foreign key constraint on safety_rules.manual_id otherwise blocks
        # deleting the manual while rules still reference it.
        db.query(SafetyRule).filter(SafetyRule.manual_id == manual_id).delete()

        if os.path.exists(manual.file_path):
            os.remove(manual.file_path)

        db.delete(manual)
        db.commit()
        return True