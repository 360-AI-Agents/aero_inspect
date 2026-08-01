"""
safety_rules.py

Converts YOLO detections into construction safety statistics.
"""

from collections import Counter


def count_objects(results):
    """
    Count all detected object classes.
    """

    counts = Counter()

    for box in results[0].boxes:

        class_id = int(box.cls[0])
        class_name = results[0].names[class_id]

        counts[class_name] += 1

    return dict(counts)


def calculate_compliance(worker_count, violations):
    """
    Calculate helmet, vest, mask and overall compliance.

    worker_count must be the count of *cleaned* workers (post
    dedup/filtering), not a raw YOLO box count -- otherwise this
    can disagree with the actual per-worker violation breakdown.
    """

    workers = worker_count

    if workers == 0:
        return {
            "helmet_compliance": 100.0,
            "vest_compliance": 100.0,
            "mask_compliance": 100.0,
            "overall_compliance": 100.0
        }

    helmet_violations = min(
        violations["helmet_violation"],
        workers
    )

    vest_violations = min(
        violations["vest_violation"],
        workers
    )

    mask_violations = min(
        violations["mask_violation"],
        workers
    )

    helmet_compliance = (
        (workers - helmet_violations) / workers
    ) * 100

    vest_compliance = (
        (workers - vest_violations) / workers
    ) * 100

    mask_compliance = (
        (workers - mask_violations) / workers
    ) * 100

    overall_compliance = (
        helmet_compliance +
        vest_compliance +
        mask_compliance
    ) / 3

    return {

        "helmet_compliance": round(helmet_compliance, 2),

        "vest_compliance": round(vest_compliance, 2),

        "mask_compliance": round(mask_compliance, 2),

        "overall_compliance": round(overall_compliance, 2)

    }


def generate_alerts(report):
    """
    Generate safety alerts.
    """

    alerts = []

    if report["helmet_violation"] > 0:
        alerts.append("Helmet Violation")

    if report["vest_violation"] > 0:
        alerts.append("Vest Violation")

    if report["mask_violation"] > 0:
        alerts.append("Mask Violation")

    return alerts


def generate_report(results, workers):
    """
    Generate complete safety report using
    worker-wise PPE analysis.
    """

    counts = count_objects(results)

    # -----------------------------
    # Worker-wise Violations
    # -----------------------------
    helmet_violation = 0
    vest_violation = 0
    mask_violation = 0

    for worker in workers.values():

        if not worker["helmet"]:
            helmet_violation += 1

        if not worker["vest"]:
            vest_violation += 1

        if not worker["mask"]:
            mask_violation += 1

    violations = {

        "helmet_violation": helmet_violation,

        "vest_violation": vest_violation,

        "mask_violation": mask_violation

    }

    compliance = calculate_compliance(
        len(workers),
        violations
    )

    report = {

        "workers": len(workers),

        "hardhat": counts.get("Hardhat", 0),

        "no_hardhat": counts.get("NO-Hardhat", 0),

        "safety_vest": counts.get("Safety Vest", 0),

        "no_safety_vest": counts.get("NO-Safety Vest", 0),

        "mask": counts.get("Mask", 0),

        "no_mask": counts.get("NO-Mask", 0),

        "vehicle": counts.get("Vehicle", 0),

        "machinery": counts.get("Machinery", 0),

        "safety_cone": counts.get("Safety Cone", 0),

        **violations,

        **compliance

    }

    return report