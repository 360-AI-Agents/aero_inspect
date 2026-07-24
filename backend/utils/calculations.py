from collections import Counter
from typing import List


def build_violation_breakdown(violations: List) -> dict:
    """
    Takes a list of Violation ORM objects and returns
    counts grouped by category, e.g.:
    {"helmet": 3, "vest": 1, "scaffolding": 0, ...}
    """
    counter = Counter()
    for v in violations:
        counter[v.category] += v.count

    categories = [
        "helmet", "vest", "scaffolding", "debris",
        "restricted_zone", "fall_protection",
        "heavy_equipment", "unsafe_behaviour", "material_storage"
    ]
    return {cat: counter.get(cat, 0) for cat in categories}


def sum_total_violations(violations: List) -> int:
    return sum(v.count for v in violations)