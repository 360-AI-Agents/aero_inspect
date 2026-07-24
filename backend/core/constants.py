# ============================================================
# Shared enums / constant values used across the backend.
# Centralized here so category or status strings never drift
# between models, schemas, and services.
# ============================================================

class InspectionStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SAFE = "Safe"
    FLAGGED = "flagged"
    COMPLETED = "completed"


class ViolationSeverity:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ViolationCategory:
    HELMET = "helmet"
    VEST = "vest"
    SCAFFOLDING = "scaffolding"
    DEBRIS = "debris"
    RESTRICTED_ZONE = "restricted_zone"
    FALL_PROTECTION = "fall_protection"
    HEAVY_EQUIPMENT = "heavy_equipment"
    UNSAFE_BEHAVIOUR = "unsafe_behaviour"
    MATERIAL_STORAGE = "material_storage"


class CameraSourceType:
    CCTV = "cctv"
    DRONE = "drone"


class CameraStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    OFFLINE = "offline"