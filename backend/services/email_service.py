import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from backend.config import settings
from backend.core.logger import logger


class EmailService:

    @staticmethod
    def send_critical_alert(to_email: str, inspection_name: str, violation_name: str,
                             severity: str, compliance_score: float):
        if not to_email:
            return False

        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.info(f"SMTP not configured — skipping email alert to {to_email}")
            return False

        subject = f"AeroInspect AI — Critical Safety Alert: {inspection_name}"

        body = f"""A critical safety violation has been detected.

Inspection: {inspection_name}
Violation: {violation_name}
Severity: {severity.upper()}
Current Compliance Score: {compliance_score}%

Please review this inspection immediately in the AeroInspect AI dashboard.

This is an automated alert from AeroInspect AI.
"""

        msg = MIMEMultipart()
        msg["From"] = settings.SMTP_USER
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, to_email, msg.as_string())
            server.quit()
            logger.info(f"Critical alert email sent to {to_email}")
            return True
        except Exception as e:
            logger.info(f"Failed to send email alert: {e}")
            return False

    @staticmethod
    def send_custom_email(to_email: str, subject: str, body: str):
        """
        Generic email sender for cases where the fixed critical-alert template
        doesn't apply — e.g. the worker daily digest, which needs its own
        custom subject and body content.
        """
        if not to_email:
            return False

        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.info(f"SMTP not configured — skipping email to {to_email}")
            return False

        msg = MIMEMultipart()
        msg["From"] = settings.SMTP_USER
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, to_email, msg.as_string())
            server.quit()
            logger.info(f"Email sent to {to_email} — subject: {subject}")
            return True
        except Exception as e:
            logger.info(f"Failed to send email: {e}")
            return False