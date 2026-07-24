import json
import httpx
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.safety_rule import SafetyRule
from backend.core.logger import logger

ROUTERBENCH_URL = "https://api.routerbench.com/v1/chat/completions"
MODEL = "claude-sonnet-4-5"

EXTRACTION_PROMPT = """You are analyzing a construction site safety manual. Extract EVERY concrete, checkable safety rule from the text below — be thorough, not conservative. Long or detailed manuals often contain 15-40+ distinct rules; do not stop early or limit yourself to a small handful if the document supports more.

Read the ENTIRE document carefully, section by section, and extract a rule for every distinct safety requirement you find — including specific numeric thresholds (distances, heights, durations), equipment requirements, and behavioral requirements — as long as they map to one of the categories and fields below.

For each rule you find, output a JSON object with exactly these fields:
- "category": one of exactly these values: helmet, vest, scaffolding, debris, restricted_zone, fall_protection, heavy_equipment, unsafe_behaviour, material_storage
- "rule_text": a short, human-readable description of the rule (max 200 characters)
- "severity": one of exactly: critical, high, medium, low
- "condition": a JSON object in ONE of these two exact shapes:
  - Flag-based: {{"type": "flag", "field": "<detection_field_name>", "equals": true}}
  - Threshold-based: {{"type": "threshold", "field": "<field_name>", "operator": ">=", "value": <number>, "additional_field": "<field_name_or_null>", "additional_equals": <true_false_or_null>}}

Valid detection field names to use in conditions: helmet_missing, vest_missing, in_restricted_zone, near_heavy_equipment, unsecured_scaffolding, debris_present, height_meters, harness_worn.

If the same category appears multiple times with different specific requirements (e.g. multiple distinct scaffolding rules, or multiple distinct restricted-zone rules), extract each as a SEPARATE rule — do not merge or summarize multiple distinct requirements into one.

Only skip content that is genuinely administrative, legal boilerplate, or entirely unrelated to physical site safety (e.g. company policy on holidays, HR procedures). When in doubt about whether something counts as a safety rule, INCLUDE it rather than skip it.

Respond with ONLY a valid JSON array of rule objects, nothing else — no markdown formatting, no explanation, no code fences, no wrapping object. Just a raw JSON array starting with [ and ending with ].

Safety manual text:
---
{manual_text}
---
"""


class AIRuleExtractionService:

    @staticmethod
    async def extract_rules_from_text(manual_text: str) -> list:
        if not settings.ROUTERBENCH_API_KEY:
            raise ValueError("RouterBench API key not configured.")

        truncated_text = manual_text[:80000]
        prompt = EXTRACTION_PROMPT.format(manual_text=truncated_text)

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                ROUTERBENCH_URL,
                headers={
                    "Authorization": f"Bearer {settings.ROUTERBENCH_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 16000,
                    "temperature": 0.2,
                },
            )

        if response.status_code != 200:
            logger.info(f"RouterBench extraction failed: {response.status_code} — {response.text}")
            raise RuntimeError(f"AI extraction failed: {response.status_code}")

        data = response.json()
        raw_content = data["choices"][0]["message"]["content"].strip()

        logger.info(f"RAW AI RESPONSE (first 2000 chars):\n{raw_content[:2000]}")

        if raw_content.startswith("```"):
            lines = raw_content.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw_content = "\n".join(lines).strip()

        try:
            rules = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.info(f"Failed to parse AI response as JSON: {e}\nFull raw content:\n{raw_content}")
            raise ValueError(f"AI returned invalid JSON — could not parse extracted rules. Parse error: {e}")

        if isinstance(rules, dict):
            for key in ["rules", "safety_rules", "extracted_rules", "data"]:
                if key in rules and isinstance(rules[key], list):
                    rules = rules[key]
                    break

        if not isinstance(rules, list):
            logger.info(f"AI response was not a list after parsing. Type: {type(rules)}, Content: {raw_content[:500]}")
            raise ValueError("AI response was not a JSON array of rules.")

        return rules

    @staticmethod
    def save_extracted_rules(db: Session, manual_id: int, rules: list) -> int:
        valid_categories = {
            "helmet", "vest", "scaffolding", "debris", "restricted_zone",
            "fall_protection", "heavy_equipment", "unsafe_behaviour", "material_storage",
        }
        valid_severities = {"critical", "high", "medium", "low"}

        saved_count = 0
        for rule in rules:
            try:
                category = rule.get("category")
                rule_text = rule.get("rule_text")
                severity = rule.get("severity", "medium")
                condition = rule.get("condition")

                if category not in valid_categories:
                    logger.info(f"Skipping rule with invalid category: {category}")
                    continue
                if severity not in valid_severities:
                    severity = "medium"
                if not rule_text or not condition:
                    logger.info(f"Skipping incomplete rule: {rule}")
                    continue

                db_rule = SafetyRule(
                    manual_id=manual_id,
                    category=category,
                    rule_text=rule_text[:300],
                    severity=severity,
                    condition=json.dumps(condition),
                )
                db.add(db_rule)
                saved_count += 1
            except Exception as e:
                logger.info(f"Failed to save individual rule: {rule} — Error: {e}")
                continue

        db.commit()
        return saved_count