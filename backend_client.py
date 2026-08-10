import os
import time
import requests
from datetime import datetime
from config import (
    API_URL,
    EVIDENCE_API_URL,
    LINK_TRACKER_URL,
    STREAM_UPLOAD_URL,
    CLIP_UPLOAD_URL,
    CAMERA_NAME,
    LOCATION,
    PERMANENT_ID_OFFSET,
)
from memory import worker_presence
from violations import get_worker_event_history, is_repeat_offender, open_events

# NOTE: get_registered_name is imported INSIDE build_payload() below,
# not up here. face_id.py now needs to call back into this module
# (to report a confirmed face match via link_tracker()), so a
# top-level import here would create a circular import
# (backend_client -> face_id -> backend_worker -> backend_client).
# Deferring it to call-time breaks the cycle -- by the time
# build_payload() actually runs, every module involved has already
# finished loading.


def build_payload(report, workers, transitions=None):
    """
    Convert YOLO report + worker information into backend JSON format.

    transitions: list of (event, transition_str) tuples for violation
    events that opened/resolved since the last send (see violations.py
    and live_detection.py's pending_transitions). Optional -- omit or
    pass [] for a payload with no event data (e.g. a pure heartbeat).
    """

    from face_id import get_registered_name as _lookup_registered_name

    transitions = transitions or []

    findings = []

    # ==========================================
    # PPE Findings
    # ==========================================
    if report["helmet_violation"] > 0:
        findings.append({
            "category": "PPE",
            "finding": "Helmet Missing",
            "severity": "High",
            "confidence": 0.95,
            "count": report["helmet_violation"]
        })

    if report["vest_violation"] > 0:
        findings.append({
            "category": "PPE",
            "finding": "Safety Vest Missing",
            "severity": "High",
            "confidence": 0.94,
            "count": report["vest_violation"]
        })

    if report["mask_violation"] > 0:
        findings.append({
            "category": "PPE",
            "finding": "Mask Missing",
            "severity": "Medium",
            "confidence": 0.92,
            "count": report["mask_violation"]
        })

    # ==========================================
    # Site Safety
    # ==========================================
    if report["vehicle"] > 0:
        findings.append({
            "category": "Site Safety",
            "finding": "Construction Vehicle Present",
            "severity": "Low",
            "confidence": 0.96,
            "count": report["vehicle"]
        })

    if report["machinery"] > 0:
        findings.append({
            "category": "Site Safety",
            "finding": "Heavy Machinery Operating",
            "severity": "Medium",
            "confidence": 0.96,
            "count": report["machinery"]
        })

    if report["safety_cone"] == 0:
        findings.append({
            "category": "Site Safety",
            "finding": "Safety Cone Missing",
            "severity": "Medium",
            "confidence": 0.90,
            "count": 1
        })

    # ==========================================
    # Worker-wise Data
    #
    # total_violation_events / repeat_offender / evidence_history are
    # now derived from actual violation EVENTS (see violations.py),
    # not a frame counter -- e.g. total_violation_events: 3 means this
    # worker has had 3 distinct violation incidents, not that they
    # were in violation for 3 frames.
    # ==========================================
    worker_data = []

    for worker_id, info in workers.items():

        presence = worker_presence.get(worker_id, {})
        event_history = get_worker_event_history(worker_id)
        open_event = open_events.get(worker_id)

        # Sum of duration_seconds across EVERY incident this worker has
        # had (open + resolved + abandoned) -- "how long has this
        # person been in violation today," as one number, so HR
        # doesn't have to add up the event history themselves.
        total_violation_duration = sum(
            e["duration_seconds"] for e in event_history
        )

        # The incident to report start/end time for: whichever is
        # ongoing right now, or if none is, the most recent one that
        # closed. This is what lets a long-running violation be
        # tracked by TIME instead of by taking repeated photos --
        # start_time is set the moment it begins, end_time fills in
        # only once it resolves/is abandoned, no new photo needed
        # while it's still ongoing.
        latest_event = open_event or (event_history[-1] if event_history else None)

        worker_data.append({

            "worker_id": worker_id,

            # None for a plain session ID. Set once this worker's face
            # matched an enrolled photo (registration.py) -- this is
            # the actual point of the permanent-ID system: a name tied
            # to the identity, not just a number, the same way an
            # Aadhaar card ties records to a person rather than a slot.
            "registered_name": _lookup_registered_name(worker_id),

            "is_registered": worker_id >= PERMANENT_ID_OFFSET,

            "bbox": info["bbox"],

            "helmet": info["helmet"],

            "vest": info["vest"],

            "mask": info["mask"],

            "violations": info["violations"],

            # How many distinct PPE items THIS worker is missing right
            # now (0-3) -- e.g. worker A: 3 violations, worker B: 1.
            "violation_count": len(info["violations"]),

            # Evidence photo for their currently open incident, if any.
            "image": info.get("image", None),

            "first_seen": presence.get("first_seen"),

            "last_seen": presence.get("last_seen"),

            # Duration of the CURRENTLY open violation event (0 if
            # they're compliant right now).
            "violation_duration_seconds": open_event["duration_seconds"] if open_event else 0,

            # Sum of duration_seconds across ALL of this worker's
            # incidents today (open + resolved + abandoned) -- total
            # time spent in violation, as a single number.
            "total_violation_duration_seconds": round(total_violation_duration, 1),

            # When the most recent incident started / ended. end_time
            # is null while it's still ongoing -- that's the point:
            # a violation that continues for a long time is tracked
            # by these timestamps, not by taking another photo.
            "violation_start_time": latest_event["start_time"] if latest_event else None,
            "violation_end_time": latest_event["end_time"] if latest_event else None,

            # Count of distinct violation INCIDENTS (open + resolved),
            # not frames.
            "total_violation_events": len(event_history),

            "repeat_offender": is_repeat_offender(worker_id),

            "evidence_history": [
                e["evidence_image"] for e in event_history if e["evidence_image"]
            ],

            # Full per-incident record -- one entry per violation, each
            # with its own start/end time, duration, and single photo.
            # This is the complete audit trail HR asked for: how many
            # times, for how long each time, without extra photos for
            # incidents that just ran long.
            "violation_history": [
                {
                    "event_id": e["event_id"],
                    "violations": e["violations"],
                    "start_time": e["start_time"],
                    "end_time": e["end_time"],
                    "status": e["status"],
                    "duration_seconds": e["duration_seconds"],
                    "evidence_image": e["evidence_image"]
                }
                for e in event_history
            ]

        })

    # ==========================================
    # Violation Events
    #
    # Only the events that actually transitioned (opened or resolved)
    # since the last send -- this is the real "what happened" log,
    # separate from the live worker snapshot above.
    # ==========================================
    event_data = [
        {
            "event_id": event["event_id"],
            "worker_id": event["worker_id"],
            "transition": transition,
            "violations": event["violations"],
            "start_time": event["start_time"],
            "end_time": event["end_time"],
            "status": event["status"],
            "duration_seconds": event["duration_seconds"],
            "evidence_image": event["evidence_image"]
        }
        for event, transition in transitions
    ]

    # ==========================================
    # Final Payload
    # ==========================================
    payload = {

        "camera_name": CAMERA_NAME,

        "location": LOCATION,

        "timestamp": datetime.now().isoformat(),

        "workers_detected": report["workers"],

        "overall_compliance": report["overall_compliance"],

        "findings": findings,

        "workers": worker_data,

        "events": event_data

    }

    return payload


def send_payload(payload):
    """
    Send an ALREADY-BUILT payload dict (from build_payload()) to the
    backend. Pure network I/O -- reads no shared mutable app state, only
    the dict handed to it. That's what makes this safe to call from a
    background thread (see backend_worker.py): by the time a payload
    reaches here it's a static snapshot, not a live reference into
    workers/violations/memory, so there's nothing for the main video
    thread to race against.

    Returns (delivered, inspection_id):
      delivered      -- True only if the backend actually received and
                         accepted the payload (HTTP 2xx). False on any
                         failure -- timeout, connection refused, non-2xx
                         response, etc. Callers MUST check this before
                         treating the events in this payload as reported:
                         a violation event that opened or resolved is
                         only "reported" once this is True.
      inspection_id  -- the backend's inspection_id for this detection
                         report, read from its JSON response. None if
                         the send failed or the response didn't include
                         one. Needed to upload evidence photos afterward
                         (see send_evidence_photo()) -- the backend ties
                         each photo to the inspection it belongs to.
    """

    print("\n================ JSON PAYLOAD ================\n")

    print(payload)

    print("\n==============================================\n")

    try:

        response = requests.post(
            API_URL,
            json=payload,
            timeout=5
        )

        print(f"Backend Response Code : {response.status_code}")

        inspection_id = None

        try:

            response_data = response.json()

            print("Backend Response :", response_data)

            inspection_id = response_data.get("inspection_id")

        except Exception:

            print("Backend Response Text :", response.text)

        return response.ok, inspection_id

    except requests.exceptions.Timeout:

        print("\nBackend Timed Out!")

        print("Server took too long to respond (>5s).")

        return False, None

    except requests.exceptions.ConnectionError:

        print("\nBackend Connection Failed!")

        print("FastAPI server is probably not running.")

        print(f"Expected URL : {API_URL}\n")

        return False, None

    except Exception as e:

        print("\nUnexpected Error")

        print(e)

        return False, None


def send_to_backend(report, workers, transitions=None):
    """
    Convenience wrapper: build the payload AND send it, synchronously,
    in one call.

    live_detection.py no longer calls this directly -- it builds the
    payload itself and hands off to backend_worker.queue_backend_send()
    so the actual network call happens on a background thread and never
    blocks the video loop. This wrapper is kept for anything that wants
    a simple one-shot synchronous send (manual testing, a one-off
    script, etc.).
    """

    payload = build_payload(report, workers, transitions)

    return send_payload(payload)


def send_evidence_photo(worker_id, inspection_id, image_path):
    """
    Upload the evidence photo for a violation event to the backend's
    dedicated binary-upload endpoint (JSON can't carry raw image bytes
    cleanly, hence a separate endpoint from the main /api/live_detection/
    call).

    Call this ONLY for a transition == "opened" -- never "updated"
    (an ongoing violation) or "resolved"/"abandoned". This mirrors the
    same "capture exactly once, at the moment the incident starts"
    rule already enforced at the source in violations.py -- this just
    gets that one photo to the backend, per HR's explicit instruction
    not to flood duplicate photos for one ongoing violation.

    Returns True only on a confirmed HTTP 2xx from the backend.
    """

    if not image_path:
        print(f"[Evidence] No image path for worker {worker_id} -- skipping upload.")
        return False

    if inspection_id is None:
        print(
            f"[Evidence] No inspection_id available for worker {worker_id} "
            f"-- skipping upload (main report send may have failed)."
        )
        return False

    try:

        with open(image_path, "rb") as f:

            response = requests.post(
                EVIDENCE_API_URL,
                data={
                    "worker_id": worker_id,
                    "inspection_id": inspection_id
                },
                files={"file": f},
                timeout=10
            )

        print(f"[Evidence] Upload for worker {worker_id} -> {response.status_code}")

        if not response.ok:
            print(f"[Evidence] Backend rejected upload: {response.text}")

        return response.ok

    except FileNotFoundError:

        print(f"[Evidence] Image file not found on disk: {image_path}")

        return False

    except requests.exceptions.Timeout:

        print(f"[Evidence] Upload timed out for worker {worker_id} (not retried).")

        return False

    except requests.exceptions.ConnectionError:

        print(f"[Evidence] Connection failed uploading evidence for worker {worker_id}.")

        return False

    except Exception as e:

        print(f"[Evidence] Unexpected error uploading for worker {worker_id}: {e}")

        return False


def link_tracker(tracked_worker_id, employee_id):
    """
    Report a CONFIDENT face match to the backend: "this YOLO tracking
    ID is this real employee." This is the exact same endpoint an
    admin's manual link button calls -- Mahani's contract explicitly
    keeps it that way so nothing changes on her side once face_id.py's
    ReID is confident enough to call it automatically instead of
    waiting for a human to recognize the person in an evidence photo.

    tracked_worker_id: the RAW session/ByteTrack tracking ID (e.g. 3),
    NOT our internal PERMANENT_ID_OFFSET-shifted key (e.g. 100003) --
    the backend has no concept of that offset, it only knows the
    tracking ID as YOLO assigned it.

    Pure network I/O, safe to call from backend_worker.py's background
    thread -- same shape as send_payload()/send_evidence_photo().
    Returns True only on a confirmed HTTP 2xx.
    """

    try:

        response = requests.post(
            LINK_TRACKER_URL,
            json={
                "tracked_worker_id": tracked_worker_id,
                "employee_id": employee_id
            },
            timeout=5
        )

        print(
            f"[Link] tracked_worker_id={tracked_worker_id} -> "
            f"employee_id={employee_id} -> {response.status_code}"
        )

        if not response.ok:
            print(f"[Link] Backend rejected the link: {response.text}")

        return response.ok

    except requests.exceptions.Timeout:

        print(f"[Link] Timed out linking tracked_worker_id={tracked_worker_id}.")

        return False

    except requests.exceptions.ConnectionError:

        print(f"[Link] Connection failed linking tracked_worker_id={tracked_worker_id}.")

        return False

    except Exception as e:

        print(f"[Link] Unexpected error linking tracked_worker_id={tracked_worker_id}: {e}")

        return False


def send_stream_file(camera_name, filename, file_type, file_path):
    """
    Push one HLS file (the playlist or a segment) to the backend --
    the "push" half of the live-streaming architecture agreed with
    Mahani: this side sends files, her backend stores/serves them,
    the dashboard never reaches into this machine directly.

    file_type is "playlist" or "segment" -- lets the backend tell
    apart "overwrite the existing file at this name" (the playlist,
    which ffmpeg continuously rewrites in place, same filename every
    time) from "store this as a new file" (a segment, a fresh
    filename every time, never overwritten).

    Same shape as send_evidence_photo(): multipart upload, pure
    network I/O, safe to call from a background thread. Returns True
    only on a confirmed HTTP 2xx.
    """

    try:

        with open(file_path, "rb") as f:

            response = requests.post(
                STREAM_UPLOAD_URL,
                data={
                    "camera_name": camera_name,
                    "filename": filename,
                    "file_type": file_type
                },
                files={"file": f},
                timeout=10
            )

        if not response.ok:
            print(f"[Streaming] Backend rejected {filename}: {response.text}")

        return response.ok

    except FileNotFoundError:

        # Can legitimately happen if ffmpeg's own delete_segments
        # cleanup removed this file between when the uploader noticed
        # it and when it tried to open it -- not worth alarming about.
        return False

    except requests.exceptions.Timeout:

        print(f"[Streaming] Upload timed out for {filename}.")

        return False

    except requests.exceptions.ConnectionError:

        print(f"[Streaming] Connection failed uploading {filename}.")

        return False

    except Exception as e:

        print(f"[Streaming] Unexpected error uploading {filename}: {e}")

        return False


def send_violation_clip(worker_id, inspection_id, clip_path, event_id=None):
    """
    Upload a violation's pre-roll clip (clip_recorder.py) to Mahani's
    clip endpoint. Base contract, straight from her: multipart POST
    with worker_id (int), inspection_id (int), file -- identical shape
    to send_evidence_photo(), NOT the link endpoint's tracked_worker_id/
    employee_id shape. Her backend finds the matching WorkerViolation
    record by worker_id + inspection_id by default.

    event_id is OPTIONAL, per her update: if provided, the clip
    attaches to that EXACT event instead of her "most recent" fallback
    -- strictly more correct when a worker has multiple violation
    events within one inspection, and costs nothing to include since
    we already have it on hand the moment a clip is captured (see
    live_detection.py). Omitted from the request entirely when None,
    rather than sent as a literal "None" string.

    Call this ONLY for a transition == "opened" -- mirrors evidence
    photos' "capture exactly once, at the moment the incident starts"
    rule. Returns True only on a confirmed HTTP 2xx.
    """

    if not clip_path:
        print(f"[Clip] No clip path for worker {worker_id} -- skipping upload.")
        return False

    if inspection_id is None:
        print(
            f"[Clip] No inspection_id available for worker {worker_id} "
            f"-- skipping upload (main report send may have failed)."
        )
        return False

    # clip_recorder.py encodes clips on a background thread and
    # returns the path before the file is necessarily finished writing
    # (see its docstring) -- in the normal case, the main report's own
    # network round-trip takes longer than encoding does, so the file
    # is already there by the time we get here. This is just a short
    # safety net for the rare case it isn't, rather than failing
    # outright on a race that usually doesn't happen.
    wait_attempts = 0

    while not os.path.exists(clip_path) and wait_attempts < 10:
        time.sleep(0.3)
        wait_attempts += 1

    try:

        form_data = {
            "worker_id": worker_id,
            "inspection_id": inspection_id
        }

        if event_id is not None:
            form_data["event_id"] = event_id

        with open(clip_path, "rb") as f:

            response = requests.post(
                CLIP_UPLOAD_URL,
                data=form_data,
                files={"file": f},
                timeout=20  # video files are bigger than an evidence photo -- more generous timeout
            )

        print(f"[Clip] Upload for worker {worker_id} -> {response.status_code}")

        if not response.ok:
            print(f"[Clip] Backend rejected upload: {response.text}")

        return response.ok

    except FileNotFoundError:

        print(f"[Clip] Clip file not found on disk: {clip_path}")

        return False

    except requests.exceptions.Timeout:

        print(f"[Clip] Upload timed out for worker {worker_id} (not retried).")

        return False

    except requests.exceptions.ConnectionError:

        print(f"[Clip] Connection failed uploading clip for worker {worker_id}.")

        return False

    except Exception as e:

        print(f"[Clip] Unexpected error uploading for worker {worker_id}: {e}")

        return False