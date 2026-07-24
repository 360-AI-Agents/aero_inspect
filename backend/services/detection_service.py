from sqlalchemy.orm import Session

from backend.repositories.violation_repository import ViolationRepository
from backend.repositories.inspection_repository import InspectionRepository
from backend.utils.compliance import calculate_compliance_score, determine_status
from backend.utils.calculations import sum_total_violations
from backend.services.settings_service import SettingsService
from backend.services.email_service import EmailService
from backend.models.camera import Camera
from backend.models.site_assignment import SiteAssignment


class DetectionService:

    @staticmethod
    def _get_alert_recipients(db: Session, inspection):
        """
        Returns a list of email addresses to notify for a critical violation
        on this inspection. Prefers inspectors specifically assigned to the
        inspection's site; falls back to the global admin alert email if
        no one is assigned yet.
        """
        recipients = []

        if inspection.camera_id:
            camera = db.query(Camera).filter(Camera.id == inspection.camera_id).first()
            if camera:
                assignments = (
                    db.query(SiteAssignment)
                    .filter(SiteAssignment.location == camera.location)
                    .all()
                )
                recipients = [a.alert_email for a in assignments if a.alert_email]

        if not recipients:
            app_settings = SettingsService.get_settings(db)
            if app_settings.alert_email:
                recipients = [app_settings.alert_email]

        return recipients

    @staticmethod
    def process_detection_event(db: Session, inspection_id: int, detection_data):
        inspection = InspectionRepository.get_by_id(db, inspection_id)
        if not inspection:
            return None

        new_violations = ViolationRepository.bulk_create(
            db, inspection_id, detection_data.violations
        )

        all_violations = ViolationRepository.get_by_inspection(db, inspection_id)
        total_violations = sum_total_violations(all_violations)

        compliance_score = calculate_compliance_score(
            detection_data.workers_detected, total_violations
        )
        status = determine_status(compliance_score)

        updated_inspection = InspectionRepository.update_detection_results(
            db,
            inspection_id,
            workers_detected=detection_data.workers_detected,
            total_violations=total_violations,
            compliance_score=compliance_score,
            status=status
        )

        critical_violations = [v for v in new_violations if v.severity == "critical"]
        if critical_violations:
            recipients = DetectionService._get_alert_recipients(db, inspection)
            for to_email in recipients:
                for v in critical_violations:
                    EmailService.send_critical_alert(
                        to_email=to_email,
                        inspection_name=inspection.inspection_name,
                        violation_name=v.violation_name,
                        severity=v.severity,
                        compliance_score=compliance_score,
                    )

        return {
            "message": "Detection event processed",
            "inspection_id": inspection_id,
            "new_violations_recorded": len(new_violations),
            "total_violations": total_violations,
            "compliance_score": compliance_score,
            "inspection_status": status
        }