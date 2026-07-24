from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.dependencies import get_db, require_admin
from backend.services.daily_digest_service import DailyDigestService

router = APIRouter(prefix="/digest", tags=["Daily Digest"])


@router.post("/send-now")
def send_digest_now(db: Session = Depends(get_db), admin=Depends(require_admin)):
    result = DailyDigestService.send_hourly_digests(db)
    return {
        "message": f"Digest run complete. Sent: {result['sent']}, Skipped (no email): {result['skipped_no_email']}",
        **result,
    }