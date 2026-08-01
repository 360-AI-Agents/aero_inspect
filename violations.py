"""
violations.py

Violation EVENT lifecycle -- replaces per-frame violation "state"
tracking with real event sourcing.

Why this changed: the previous approach re-derived violation state
every frame and kept a running counter of how many frames a worker
had any violation in ("total_violation_events: 802" after a couple
minutes) -- a frame count, not an incident count, and not something
a human or a backend can reason about. Evidence capture was also a
separate, loosely related mechanism ("has this worker ID ever gotten
a photo") that didn't line up with the actual incident.

This module makes the incident the first-class thing:

  - A violation STARTS   -> exactly one event is created (an id, a
    start time, the missing PPE items, one evidence photo captured
    right then).
  - It CONTINUES          -> the SAME event is updated in place (the
    specific missing items can drift as things are put on/taken off,
    duration grows) -- no new event, no new photo.
  - It RESOLVES (worker becomes fully compliant) -> the event is
    closed (end time set, duration finalized) and filed into history.
  - The worker violates AGAIN later -> that's a new, distinct event
    with its own id, start time, and evidence photo.

This is "detect a violation once, create one event, track it until
it's resolved, and only create a new event if a new violation occurs."
"""

from datetime import datetime

# Every event ever created this session, in creation order (both
# open and resolved). Each entry:
# {
#   "event_id": int,
#   "worker_id": int,
#   "camera_name": str,
#   "violations": [...],        # current/most-recent set of missing PPE
#   "start_time": iso str,
#   "end_time": iso str | None, # None while still open
#   "last_seen": iso str,       # last time this event was confirmed live
#   "status": "open" | "resolved" | "abandoned",
#   "duration_seconds": float,
#   "evidence_image": str | None
# }
violation_events = []

# worker_id -> the event dict currently open for them, if any. This is
# the SAME dict object stored in violation_events (not a copy), so
# updating one updates the other automatically.
open_events = {}

# A worker is a repeat offender once they've racked up this many
# distinct violation incidents (open + resolved) -- a much more
# meaningful signal than a frame count.
REPEAT_OFFENDER_EVENT_THRESHOLD = 2

_next_event_id = 1


def _new_event_id():
    global _next_event_id
    event_id = _next_event_id
    _next_event_id += 1
    return event_id


def record_violation_state(worker_id, violations, camera_name, capture_evidence):
    """
    Call once per worker, once per frame, with their CURRENT list of
    missing PPE items. Opens, updates, or resolves that worker's
    violation event as needed.

    capture_evidence: a zero-argument callable that captures and saves
    an evidence image, returning its file path. Called exactly once --
    at the moment a brand-new event opens. Never called for an event
    that's merely continuing, and never called while resolving one.

    Returns (event, transition) where transition is one of:
      "opened"   -- a new event was just created
      "updated"  -- an existing open event continued
      "resolved" -- an open event just closed because the worker
                    became compliant
      "none"     -- nothing to do (no violation, no open event)
    event is None only when transition == "none".

    Note: a worker simply vanishing from frame (walked off, tracking
    lost) is NOT handled here -- their event stays open until either
    they're re-attached to the same worker_id (handled upstream by
    stabilize_worker_ids) or resolve_stale_events() below decides
    enough time has passed to give up on them. This function only
    ever sees workers who are actually present in the current frame.
    """

    now = datetime.now()
    now_iso = now.isoformat()

    existing_event = open_events.get(worker_id)
    has_violation = len(violations) > 0

    if has_violation:

        if existing_event is None:

            # A violation just started -- open exactly one new event.
            event = {
                "event_id": _new_event_id(),
                "worker_id": worker_id,
                "camera_name": camera_name,
                "violations": list(violations),
                "start_time": now_iso,
                "end_time": None,
                "last_seen": now_iso,
                "status": "open",
                "duration_seconds": 0.0,
                "evidence_image": capture_evidence()
            }

            violation_events.append(event)
            open_events[worker_id] = event

            return event, "opened"

        else:

            # Still violating -- update the SAME event, don't create
            # a new one or take a new photo. The specific missing
            # items can change (e.g. helmet fixed, vest still missing)
            # without ending the incident.
            existing_event["violations"] = list(violations)
            existing_event["last_seen"] = now_iso

            start = datetime.fromisoformat(existing_event["start_time"])
            existing_event["duration_seconds"] = round(
                (now - start).total_seconds(), 1
            )

            return existing_event, "updated"

    else:

        if existing_event is not None:

            # Violation resolved -- close this event out for good.
            existing_event["end_time"] = now_iso
            existing_event["last_seen"] = now_iso
            existing_event["status"] = "resolved"

            start = datetime.fromisoformat(existing_event["start_time"])
            existing_event["duration_seconds"] = round(
                (now - start).total_seconds(), 1
            )

            del open_events[worker_id]

            return existing_event, "resolved"

        return None, "none"


def resolve_stale_events(active_worker_ids, timeout_seconds):
    """
    Close out any open event whose worker hasn't been seen in the
    current frame's active worker set for longer than timeout_seconds.

    Why this exists: record_violation_state() only ever runs for
    workers present in the current frame, so a worker who just walks
    off camera for good (rather than becoming compliant) would
    otherwise leave their event open forever -- stale data, and a
    backend has no way to know the incident is actually over.

    timeout_seconds should match (or exceed) the ID-continuity gap
    window, so a worker mid-way through a brief tracking gap gets
    re-attached to the SAME event by stabilize_worker_ids before we
    ever consider giving up on them here.

    Call once per frame with the set of worker_ids present THIS
    frame (post dedup/filter/stabilize). Returns a list of
    (event, "abandoned") tuples for every event this closes, in the
    same shape as record_violation_state()'s return value, so callers
    can report them identically to any other transition.
    """

    now = datetime.now()
    newly_abandoned = []

    for worker_id in list(open_events.keys()):

        if worker_id in active_worker_ids:
            continue

        event = open_events[worker_id]

        last_seen = datetime.fromisoformat(event["last_seen"])
        gap = (now - last_seen).total_seconds()

        if gap <= timeout_seconds:
            continue

        # Gave stitching its full window -- this worker is genuinely
        # gone. Close the event as "abandoned", distinct from
        # "resolved", so a backend can tell "PPE was fixed" apart
        # from "worker walked off still in violation".
        event["end_time"] = event["last_seen"]
        event["status"] = "abandoned"

        start = datetime.fromisoformat(event["start_time"])
        end = datetime.fromisoformat(event["end_time"])
        event["duration_seconds"] = round((end - start).total_seconds(), 1)

        del open_events[worker_id]

        newly_abandoned.append((event, "abandoned"))

    return newly_abandoned


def get_worker_event_history(worker_id):
    """All events (open + resolved) ever recorded for this worker."""
    return [e for e in violation_events if e["worker_id"] == worker_id]


def is_repeat_offender(worker_id):
    """True once this worker has accumulated enough distinct events."""
    return len(get_worker_event_history(worker_id)) >= REPEAT_OFFENDER_EVENT_THRESHOLD
