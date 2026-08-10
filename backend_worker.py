"""
backend_worker.py

Runs all backend network I/O -- the main JSON report send, the
evidence photo upload, AND (as of the ReID auto-link integration)
reporting a confirmed face match -- on a background thread, so a slow
or unreachable FastAPI server can never freeze the live video feed.

Why this exists: send_payload(), send_evidence_photo(), and
link_tracker() (all in backend_client.py) are blocking network calls.
Calling any of them directly from live_detection.py's/face_id.py's
code means the camera feed visibly pauses for however long those
calls take -- normally tens of milliseconds, but up to the full
request timeout if the backend is slow or down.

Design: callers build whatever data they need (pure in-memory work --
no network) and hand it off here via queue_backend_send() (a
detection report) or queue_link_tracker() (a confirmed face match).
Both calls return immediately. This module owns a single background
thread that does the actual requests.post calls, and owns its OWN
retry loop for failed sends -- so a failure here never touches the
main video loop.

Note: jobs are processed in order and a failed job is retried in
place before the next one is attempted, so a prolonged backend outage
will make this queue back up until connectivity returns -- at which
point everything queued gets delivered in a quick burst. That's
intentional: "delivered late" beats "silently dropped," consistent
with how retries already work elsewhere in this app.
"""

import threading
import queue
import time

from backend_client import send_payload, send_evidence_photo, link_tracker, send_violation_clip

# How long to wait before retrying a FAILED job. This lives here now
# instead of the main loop, since all retry responsibility moved to
# this background thread.
RETRY_INTERVAL_SECONDS = 5

_send_queue = queue.Queue()


def queue_backend_send(payload, opened_evidence, opened_clips=None):
    """
    Hand off an already-built payload (a plain dict from
    backend_client.build_payload() -- no ties back to any mutable
    shared state, safe to pass across threads) plus the list of
    (worker_id, evidence_image_path) pairs for events that opened this
    round, and optionally (worker_id, clip_path, event_id) triples for
    their pre-roll violation clips (clip_recorder.py) -- event_id lets
    the backend attach the clip to the exact event instead of falling
    back to "most recent." Returns immediately -- never blocks on
    network I/O.
    """

    _send_queue.put({
        "type": "report",
        "payload": payload,
        "opened_evidence": opened_evidence,
        "opened_clips": opened_clips or []
    })


def queue_link_tracker(tracked_worker_id, employee_id):
    """
    Hand off a CONFIRMED face match to be reported to the backend --
    called from face_id.py the moment a session tracking ID is
    confidently matched to a registered employee, so the auto-link
    (POST /workers/link-tracker) happens off-thread just like every
    other backend call. Returns immediately.
    """

    _send_queue.put({"type": "link", "tracked_worker_id": tracked_worker_id, "employee_id": employee_id})


def _worker_loop():

    pending = None  # job dict still waiting on a retry

    while True:

        if pending is None:

            try:
                pending = _send_queue.get(timeout=1)
            except queue.Empty:
                continue

        if pending["type"] == "report":

            payload = pending["payload"]
            opened_evidence = pending["opened_evidence"]

            delivered, inspection_id = send_payload(payload)

            if delivered:

                # Upload evidence photos ONLY for events that opened --
                # never "updated"/"resolved"/"abandoned" -- per HR's
                # instruction not to flood duplicate photos for one
                # ongoing violation. live_detection.py already filtered
                # this list down before handing it off.
                for worker_id, image_path in opened_evidence:
                    send_evidence_photo(worker_id, inspection_id, image_path)

                # Violation clips (clip_recorder.py) -- same "opened
                # only" rule, uploaded with the SAME inspection_id this
                # report just returned.
                #
                # event_id TEMPORARILY not sent: real testing showed
                # every clip upload rejected with a 404 ("no matching
                # worker violation record -- send the JSON event
                # first") the moment event_id was included, even
                # though the IDENTICAL worker_id + inspection_id had
                # just succeeded for the evidence photo seconds
                # earlier. Our event_id here is purely a local counter
                # (violations.py's _next_event_id, resetting to 1 on
                # every process restart) -- it very likely doesn't
                # match whatever ID Mahani's backend actually expects
                # in that field. Reverting to her "most recent"
                # fallback (confirmed working) until she clarifies
                # what that field should actually contain.
                opened_clips = pending.get("opened_clips", [])

                for worker_id, clip_path, event_id in opened_clips:
                    send_violation_clip(worker_id, inspection_id, clip_path)

                pending = None

            else:

                backlog = _send_queue.qsize()

                print(
                    f"[Backend Thread] Send failed (timestamp "
                    f"{payload.get('timestamp')}) -- retrying in "
                    f"{RETRY_INTERVAL_SECONDS}s (video feed unaffected). "
                    f"{backlog} more job(s) queued behind this one -- "
                    f"nothing is being dropped, just delayed.\n"
                )

                time.sleep(RETRY_INTERVAL_SECONDS)
                # Loop again with the SAME `pending` -- retries this
                # exact job instead of moving on and losing it.

        elif pending["type"] == "link":

            tracked_worker_id = pending["tracked_worker_id"]
            employee_id = pending["employee_id"]

            delivered = link_tracker(tracked_worker_id, employee_id)

            if delivered:

                pending = None

            else:

                backlog = _send_queue.qsize()

                print(
                    f"[Backend Thread] Link failed (tracked_worker_id="
                    f"{tracked_worker_id} -> employee_id={employee_id}) "
                    f"-- retrying in {RETRY_INTERVAL_SECONDS}s (video "
                    f"feed unaffected). {backlog} more job(s) queued "
                    f"behind this one.\n"
                )

                time.sleep(RETRY_INTERVAL_SECONDS)

        else:

            # Shouldn't happen -- drop it rather than looping forever
            # on an unrecognized job type.
            print(f"[Backend Thread] Unknown job type {pending.get('type')!r} -- dropping.")
            pending = None


# Single daemon thread for the whole app's lifetime. Daemon=True so it
# never blocks the process from exiting (e.g. on 'q' or Ctrl+C) even
# if it's mid-retry.
_worker_thread = threading.Thread(target=_worker_loop, daemon=True)
_worker_thread.start()
