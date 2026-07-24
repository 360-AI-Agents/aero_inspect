from backend.config import settings


def calculate_compliance_score(workers_detected: int, total_violations: int) -> float:
    """
    Compliance score starts at 100 and loses points per violation.
    Never drops below 0.
    """
    if workers_detected <= 0:
        return settings.COMPLIANCE_BASE_SCORE

    score = settings.COMPLIANCE_BASE_SCORE - (total_violations * settings.VIOLATION_PENALTY_POINTS)
    return max(0.0, round(score, 2))


def determine_status(compliance_score: float) -> str:
    if compliance_score >= 90:
        return "Safe"
    elif compliance_score >= 70:
        return "flagged"
    else:
        return "unsafe"