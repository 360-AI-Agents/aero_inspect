from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from backend.dependencies import get_db, require_admin
from backend.schemas.safety_manual import SafetyManualResponse
from backend.services.safety_manual_service import SafetyManualService
from backend.services.pdf_text_service import PdfTextService
from backend.services.ai_rule_extraction_service import AIRuleExtractionService
from backend.models.safety_rule import SafetyRule
from backend.core.logger import logger

router = APIRouter(prefix="/safety-manuals", tags=["Safety Manuals"])


@router.post("/", response_model=SafetyManualResponse)
def upload_manual(
    file: UploadFile = File(...),
    manual_name: str = Form(...),
    organization: Optional[str] = Form(None),
    region: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    try:
        return SafetyManualService.create_manual(db, file, manual_name, organization, region, version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[SafetyManualResponse])
def list_manuals(db: Session = Depends(get_db)):
    return SafetyManualService.get_all(db)


@router.patch("/{manual_id}/activate", response_model=SafetyManualResponse)
def activate_manual(manual_id: int, db: Session = Depends(get_db), current_admin=Depends(require_admin)):
    manual = SafetyManualService.activate(db, manual_id)
    if not manual:
        raise HTTPException(status_code=404, detail="Manual not found")
    return manual


@router.delete("/{manual_id}")
def delete_manual(manual_id: int, db: Session = Depends(get_db), current_admin=Depends(require_admin)):
    deleted = SafetyManualService.delete(db, manual_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Manual not found")
    return {"message": "Manual deleted successfully"}


@router.post("/{manual_id}/extract-rules")
async def extract_rules_ai(manual_id: int, db: Session = Depends(get_db), current_admin=Depends(require_admin)):
    manual = SafetyManualService.get_by_id(db, manual_id)
    if not manual:
        raise HTTPException(status_code=404, detail="Manual not found")

    if not manual.file_path.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="AI rule extraction currently only supports PDF manuals.")

    original_status = manual.status  # remember what it was before extraction

    try:
        manual.status = "processing"
        db.commit()

        manual_text = PdfTextService.extract_text(manual.file_path)

        logger.info(f"PDF TEXT LENGTH: {len(manual_text)} characters")
        logger.info(f"PDF TEXT PREVIEW (first 1500 chars):\n{manual_text[:1500]}")

        if not manual_text.strip():
            manual.status = original_status
            db.commit()
            raise HTTPException(status_code=400, detail="Could not extract any text from this PDF — it may be scanned/image-based.")

        extracted_rules = await AIRuleExtractionService.extract_rules_from_text(manual_text)

        # Clear out any previously-extracted rules for this manual before
        # saving the new set, so re-running extraction replaces rather than
        # duplicates on top of earlier runs.
        db.query(SafetyRule).filter(SafetyRule.manual_id == manual_id).delete()
        db.commit()

        saved_count = AIRuleExtractionService.save_extracted_rules(db, manual_id, extracted_rules)

        manual.status = original_status  # restore original status, don't overwrite with "uploaded"
        db.commit()

        return {
            "message": f"Successfully extracted and saved {saved_count} safety rule(s)",
            "rules_found": len(extracted_rules),
            "rules_saved": saved_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        manual.status = original_status
        db.commit()
        raise HTTPException(status_code=500, detail=f"AI rule extraction failed: {str(e)}")