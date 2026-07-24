from sqlalchemy.orm import Session
from backend.models.camera import Camera


class CameraService:

    @staticmethod
    def get_all(db: Session):
        return db.query(Camera).order_by(Camera.created_at.desc()).all()

    @staticmethod
    def get_by_id(db: Session, camera_id: int):
        return db.query(Camera).filter(Camera.id == camera_id).first()

    @staticmethod
    def create(db: Session, camera_name: str, location: str, source_type: str = "cctv"):
        camera = Camera(
            camera_name=camera_name,
            location=location,
            source_type=source_type,
            status="active"
        )
        db.add(camera)
        db.commit()
        db.refresh(camera)
        return camera

    @staticmethod
    def update_status(db: Session, camera_id: int, status: str):
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            return None
        camera.status = status
        db.commit()
        db.refresh(camera)
        return camera

    @staticmethod
    def delete(db: Session, camera_id: int):
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            return False
        db.delete(camera)
        db.commit()
        return True