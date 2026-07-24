from sqlalchemy.orm import Session
from backend.models.settings import Settings


class SettingsService:

    @staticmethod
    def get_settings(db: Session):
        """
        Returns the single settings row, creating it with
        defaults on first ever call if it doesn't exist yet.
        """
        settings_row = db.query(Settings).filter(Settings.id == 1).first()
        if not settings_row:
            settings_row = Settings(id=1, flagged_threshold=90.0, unsafe_threshold=70.0)
            db.add(settings_row)
            db.commit()
            db.refresh(settings_row)
        return settings_row

    @staticmethod
    def update_settings(db: Session, updates):
        settings_row = SettingsService.get_settings(db)

        update_data = updates.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(settings_row, field, value)

        db.commit()
        db.refresh(settings_row)
        return settings_row