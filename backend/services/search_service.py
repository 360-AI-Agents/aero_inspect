from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.models.inspection import Inspection
from backend.models.camera import Camera


class SearchService:

    @staticmethod
    def search(db: Session, query: str, limit: int = 8):
        if not query or len(query.strip()) < 2:
            return []

        term = f"%{query.strip()}%"
        results = []

        inspections = (
            db.query(Inspection)
            .filter(Inspection.inspection_name.ilike(term))
            .order_by(Inspection.created_at.desc())
            .limit(limit)
            .all()
        )
        for insp in inspections:
            results.append({
                "type": "inspection",
                "id": insp.id,
                "title": insp.inspection_name,
                "subtitle": f"{insp.total_violations} violations · {insp.compliance_score}% compliance",
                "link": "inspections.html",
            })

        cameras = (
            db.query(Camera)
            .filter(or_(
                Camera.camera_name.ilike(term),
                Camera.location.ilike(term),
            ))
            .limit(limit)
            .all()
        )
        for cam in cameras:
            results.append({
                "type": "camera",
                "id": cam.id,
                "title": cam.camera_name,
                "subtitle": f"{cam.location} · {cam.source_type}",
                "link": "cameras.html",
            })

        return results[:limit]
