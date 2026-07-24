from pydantic import BaseModel
from typing import List, Optional
from backend.schemas.violation import ViolationCreate


class DetectionEventCreate(BaseModel):
    workers_detected: int = 0
    violations: List[ViolationCreate] = []


class RawDetectionCreate(BaseModel):
    workers_detected: int = 0
    helmet_missing: Optional[bool] = False
    vest_missing: Optional[bool] = False
    in_restricted_zone: Optional[bool] = False
    near_heavy_equipment: Optional[bool] = False
    unsecured_scaffolding: Optional[bool] = False
    debris_present: Optional[bool] = False
    material_storage_issue: Optional[bool] = False
    height_meters: Optional[float] = None
    harness_worn: Optional[bool] = False
    confidence: Optional[float] = 0.9
