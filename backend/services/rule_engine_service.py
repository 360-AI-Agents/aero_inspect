import json
import operator
from sqlalchemy.orm import Session

from backend.models.safety_rule import SafetyRule
from backend.models.safety_manual import SafetyManual

OPERATORS = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
}

# Seed rules matching the A & M Constructions manual we uploaded —
# used for demo purposes until Phase 2 (AI extraction) is wired in.
DEMO_RULES = [
    {"category": "helmet", "rule_text": "Helmet is mandatory in all active work zones",
     "severity": "high", "condition": {"type": "flag", "field": "helmet_missing", "equals": True}},

    {"category": "vest", "rule_text": "High-visibility vest is mandatory in all active work zones",
     "severity": "high", "condition": {"type": "flag", "field": "vest_missing", "equals": True}},

    {"category": "fall_protection", "rule_text": "Harness required for work above 2 metres",
     "severity": "critical", "condition": {
         "type": "threshold", "field": "height_meters", "operator": ">=", "value": 2,
         "additional_field": "harness_worn", "additional_equals": False}},

    {"category": "restricted_zone", "rule_text": "No unauthorised entry into restricted zones",
     "severity": "critical", "condition": {"type": "flag", "field": "in_restricted_zone", "equals": True}},

    {"category": "heavy_equipment", "rule_text": "Minimum 3m distance from operating heavy equipment",
     "severity": "critical", "condition": {"type": "flag", "field": "near_heavy_equipment", "equals": True}},

    {"category": "scaffolding", "rule_text": "Scaffolding must be inspected and secured",
     "severity": "high", "condition": {"type": "flag", "field": "unsecured_scaffolding", "equals": True}},

    {"category": "debris", "rule_text": "Walkways must be kept free of debris",
     "severity": "medium", "condition": {"type": "flag", "field": "debris_present", "equals": True}},

    {"category": "material_storage", "rule_text": "Materials must be stored in designated areas only",
     "severity": "medium", "condition": {"type": "flag", "field": "material_storage_issue", "equals": True}},
]


class RuleEngineService:

    @staticmethod
    def seed_demo_rules(db: Session):
        """
        Attaches demo rules to whichever safety manual is currently active.
        If no manual is active, rules are created with manual_id = None
        (treated as always-active fallback rules).
        """
        active_manual = db.query(SafetyManual).filter(SafetyManual.status == "active").first()
        manual_id = active_manual.id if active_manual else None

        created = []
        for rule in DEMO_RULES:
            db_rule = SafetyRule(
                manual_id=manual_id,
                category=rule["category"],
                rule_text=rule["rule_text"],
                severity=rule["severity"],
                condition=json.dumps(rule["condition"]),
            )
            db.add(db_rule)
            created.append(db_rule)

        db.commit()
        for r in created:
            db.refresh(r)
        return created

    @staticmethod
    def get_active_rules(db: Session):
        active_manual = db.query(SafetyManual).filter(SafetyManual.status == "active").first()
        if active_manual:
            return db.query(SafetyRule).filter(SafetyRule.manual_id == active_manual.id).all()
        # Fallback: rules with no manual attached
        return db.query(SafetyRule).filter(SafetyRule.manual_id.is_(None)).all()

    @staticmethod
    def evaluate_rule(rule: SafetyRule, detection: dict) -> bool:
        condition = json.loads(rule.condition)

        if condition["type"] == "flag":
            return detection.get(condition["field"]) == condition["equals"]

        if condition["type"] == "threshold":
            field_value = detection.get(condition["field"])
            if field_value is None:
                return False
            op_func = OPERATORS.get(condition["operator"])
            main_match = op_func(field_value, condition["value"])

            if "additional_field" in condition:
                additional_match = detection.get(condition["additional_field"]) == condition["additional_equals"]
                return main_match and additional_match

            return main_match

        return False

    @staticmethod
    def evaluate_detection(db: Session, detection: dict):
        """
        Takes a raw detection payload (booleans/numbers from YOLO)
        and returns a list of matched violations based on active rules.
        """
        rules = RuleEngineService.get_active_rules(db)
        matched_violations = []

        for rule in rules:
            if RuleEngineService.evaluate_rule(rule, detection):
                matched_violations.append({
                    "category": rule.category,
                    "violation_name": rule.rule_text,
                    "severity": rule.severity,
                    "confidence": detection.get("confidence", 0.9),
                    "count": 1,
                })

        return matched_violations