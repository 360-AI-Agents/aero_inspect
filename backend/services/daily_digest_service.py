from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.models.worker import Worker
from backend.models.worker_violation import WorkerViolation
from backend.services.email_service import EmailService
from backend.core.logger import logger


class DailyDigestService:

    @staticmethod
    def get_last_hour_violations_by_worker(db: Session):
        """
        Groups the past hour's violation events by employee_id (only linked
        workers, since we need their real registered email to send anything).
        """
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)

        records = (
            db.query(WorkerViolation)
            .filter(
                WorkerViolation.employee_id.isnot(None),
                WorkerViolation.first_seen >= one_hour_ago,
            )
            .all()
        )

        grouped = {}
        for r in records:
            grouped.setdefault(r.employee_id, []).append(r)

        return grouped

    @staticmethod
    def send_hourly_digests(db: Session):
        grouped = DailyDigestService.get_last_hour_violations_by_worker(db)

        if not grouped:
            logger.info("Hourly digest: no violations recorded in the past hour, nothing to send.")
            return {"sent": 0, "skipped_no_email": 0}

        sent_count = 0
        skipped_count = 0

        for employee_id, violations in grouped.items():
            worker = db.query(Worker).filter(Worker.employee_id == employee_id).first()

            if not worker or not worker.email:
                logger.info(f"Hourly digest: skipping {employee_id} — no registered email on file.")
                skipped_count += 1
                continue

            unauthorized_count = sum(1 for v in violations if v.alert_type == "unauthorized_presence")
            ppe_violations = [v for v in violations if v.alert_type != "unauthorized_presence"]

            violation_lines = []
            for v in ppe_violations:
                time_str = v.first_seen.strftime("%I:%M %p") if v.first_seen else "—"
                violation_lines.append(f"  • {time_str} — {v.violations or 'Safety violation'}")

            if unauthorized_count > 0:
                violation_lines.append(f"  • {unauthorized_count} instance(s) of being on-site outside your registered shift hours")

            now_str = datetime.utcnow().strftime("%I:%M %p")
            body = f"""Hi {worker.name},

This is your safety check-in from AeroInspect AI, covering the last hour (as of {now_str}).

Our monitoring system recorded the following:

{chr(10).join(violation_lines)}

This is just a friendly reminder to help keep you and your team safe right now — please make sure you're wearing the required safety gear for the rest of your shift.

If you believe any of this was recorded in error, please speak with your site supervisor.

Stay safe,
AeroInspect AI
"""

            success = EmailService.send_custom_email(
                to_email=worker.email,
                subject=f"Safety Check-In — {now_str}",
                body=body,
            )

            if success:
                sent_count += 1
            else:
                skipped_count += 1

        return {"sent": sent_count, "skipped_no_email": skipped_count}