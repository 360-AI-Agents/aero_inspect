from sqlalchemy.orm import Session
from backend.models.violation import Violation


CRITICAL_CATEGORIES = {"restricted_zone", "fall_protection", "heavy_equipment"}
HIGH_CATEGORIES = {"scaffolding"}
MEDIUM_CATEGORIES = {"debris", "material_storage"}
REPEAT_ESCALATE_CATEGORIES = {"helmet", "vest"}  # escalate to High if count >= 2


def classify_risk_level(category: str, severity: str, count: int) -> str:
    """
    Rule-based risk classification. Category-based rules take priority
    (life-safety categories are always critical), then explicit severity,
    then repeat-offense escalation for helmet/vest.
    """
    if category in CRITICAL_CATEGORIES:
        return "critical"
    if severity == "critical":
        return "critical"

    if category in HIGH_CATEGORIES:
        return "high"
    if category in REPEAT_ESCALATE_CATEGORIES and count >= 2:
        return "high"
    if severity == "high":
        return "high"

    if category in MEDIUM_CATEGORIES:
        return "medium"
    if severity == "medium":
        return "medium"

    return "low"


class AlertService:

    @staticmethod
    def get_risk_heatmap(db: Session, allowed_locations: list = None):
        violations = (
            db.query(Violation)
            .order_by(Violation.created_at.desc())
            .all()
        )

        buckets = {"critical": [], "high": [], "medium": [], "low": []}

        for v in violations:
            inspection = v.inspection
            if not inspection:
                continue

            camera = inspection.camera
            camera_name = camera.camera_name if camera else "Unknown Camera"
            location = camera.location if camera else "Unknown Location"

            if allowed_locations is not None:
                if not camera or camera.location not in allowed_locations:
                    continue

            risk_level = classify_risk_level(v.category, v.severity, v.count)

            item = {
                "inspection_id": inspection.id,
                "inspection_name": inspection.inspection_name,
                "camera_name": camera_name,
                "location": location,
                "violation_name": v.violation_name,
                "category": v.category,
                "severity": v.severity,
                "count": v.count,
                "risk_level": risk_level,
                "inspection_status": inspection.inspection_status,
                "timestamp": v.created_at,
            }

            buckets[risk_level].append(item)

        summary = {
            "critical": len(buckets["critical"]),
            "high": len(buckets["high"]),
            "medium": len(buckets["medium"]),
            "low": len(buckets["low"]),
        }

        return {
            "summary": summary,
            "critical": buckets["critical"],
            "high": buckets["high"],
            "medium": buckets["medium"],
            "low": buckets["low"],
        }