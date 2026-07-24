from sqlalchemy.orm import Session
from backend.models.report import Report


class ReportRepository:

    @staticmethod
    def create(db: Session, inspection_id: int, report_title: str, summary: str, file_path: str = None):
        report = Report(
            inspection_id=inspection_id,
            report_title=report_title,
            summary=summary,
            file_path=file_path
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report

    @staticmethod
    def get_by_inspection(db: Session, inspection_id: int):
        return (
            db.query(Report)
            .filter(Report.inspection_id == inspection_id)
            .order_by(Report.generated_at.desc())
            .first()
        )