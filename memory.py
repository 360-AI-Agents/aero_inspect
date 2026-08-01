"""
memory.py

Runtime memory that ISN'T about the violation-event lifecycle
(see violations.py for that): general worker presence bookkeeping,
and cross-frame ID continuity state. This is in-process memory only
-- it resets when the script restarts. A future step (see roadmap)
is to persist this to PostgreSQL so history survives restarts and
works across multiple camera processes.
"""

from datetime import datetime

# ---------------------------------------------------------------
# Worker presence (NOT violation-specific)
#
# Tracks how long a worker has been seen in frame at all, regardless
# of whether they're currently violating. Violation timing/counts/
# repeat-offender status now live in violations.py as proper events
# -- this dict deliberately stays simple.
# ---------------------------------------------------------------
worker_presence = {}


def update_worker_presence(worker_id):
    """
    Call once per worker, once per frame, regardless of violation
    state, so first_seen/last_seen/total_frames_seen stay accurate.
    """

    now_iso = datetime.now().isoformat()

    if worker_id not in worker_presence:

        worker_presence[worker_id] = {
            "first_seen": now_iso,
            "last_seen": now_iso,
            "total_frames_seen": 0
        }

    record = worker_presence[worker_id]

    record["last_seen"] = now_iso
    record["total_frames_seen"] += 1

    return record


# ---------------------------------------------------------------
# Cross-frame ID continuity ("track stitching") -- runtime state only.
#
# The tunable thresholds (gap window, IoU, distance) now live in
# config.py alongside every other tunable constant. This dict is just
# the live memory of where each canonical worker was last seen,
# keyed by canonical ID -- see worker_manager.stabilize_worker_ids()
# for the matching logic itself.
# ---------------------------------------------------------------
last_known_positions = {}
