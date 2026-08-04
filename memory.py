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


def migrate_presence(old_id, new_id):
    """
    Move presence tracking from a temporary session ID to a permanent
    one -- called from face_id.py the moment a worker's face is first
    matched to a registered identity mid-session. Without this,
    first_seen/total_frames_seen would restart from zero under the new
    permanent ID, as if the worker had just walked in, even though
    they'd already been present (and possibly already confirmed past
    MIN_CONFIRMATION_FRAMES) under their session ID.
    """

    if old_id not in worker_presence:
        return

    old_record = worker_presence.pop(old_id)

    if new_id in worker_presence:

        existing = worker_presence[new_id]

        existing["first_seen"] = min(existing["first_seen"], old_record["first_seen"])
        existing["last_seen"] = max(existing["last_seen"], old_record["last_seen"])
        existing["total_frames_seen"] += old_record["total_frames_seen"]

    else:

        worker_presence[new_id] = old_record


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
