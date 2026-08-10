from worker_manager import (
    get_workers,
    deduplicate_workers,
    filter_worker_boxes,
    stabilize_worker_ids,
    assign_ppe,
    calculate_worker_violations
)

from backend_client import build_payload
from backend_worker import queue_backend_send
from safety_rules import generate_report
from evidence import save_violation_image
from memory import (
    update_worker_presence,
    last_known_positions
)
from violations import record_violation_state, resolve_stale_events
from roi import (
    normalized_to_pixels,
    draw_roi_overlay,
    filter_workers_by_roi,
    get_zoomed_inset,
    overlay_inset
)
from face_id import load_registered_faces, remap_to_permanent_ids, get_registered_name
from streaming import start_stream, push_frame, stop_stream
from clip_recorder import record_frame, save_violation_clip

import cv2
import time

from detector import load_model
from config import (
    CAMERA_SOURCE,
    WINDOW_NAME,
    CAMERA_NAME,
    CONFIDENCE,
    NMS_IOU_THRESHOLD,
    ENABLE_ROI,
    ROI,
    ROI_MIN_OVERLAP_FRACTION,
    SHOW_ZOOM_INSET,
    ZOOM_FACTOR,
    ZOOM_INSET_WIDTH,
    MIN_CONFIRMATION_FRAMES,
    ID_CONTINUITY_MAX_GAP_SECONDS,
    ID_CONTINUITY_IOU_THRESHOLD,
    ID_CONTINUITY_MAX_CENTER_DISTANCE,
    PERMANENT_ID_OFFSET
)

# Send a heartbeat to the backend at least this often even if no
# violation event has opened/resolved, so the backend knows the
# camera is still alive and monitoring.
HEARTBEAT_SECONDS = 30
last_heartbeat = 0

# Event transitions (opened/resolved) accumulate here across frames
# until the next backend send flushes them. This is what makes
# reporting event-driven instead of a per-second state poll: we only
# ever tell the backend about something that actually happened.
#
# Note: once handed off to queue_backend_send() below, delivery and
# retries are entirely backend_worker.py's responsibility -- this list
# is safe to clear immediately after handoff, since the payload it
# produced is a static snapshot, not a live reference into this list.
pending_transitions = []

# Distinct color per violation type, so the precise per-item boxes
# (see worker_manager.py's assign_ppe -> violation_boxes) are visually
# distinguishable from each other and from the outer worker box.
VIOLATION_BOX_COLORS = {
    "Helmet Missing": (0, 165, 255),        # orange
    "Safety Vest Missing": (255, 0, 255),   # magenta
    "Mask Missing": (255, 255, 0),          # cyan
}

# Runtime-toggleable copies of the config defaults -- press 'r' to
# flip ROI filtering, 'z' to flip the zoom inset, while the app runs.
roi_enabled = ENABLE_ROI
zoom_enabled = SHOW_ZOOM_INSET


# ==========================================
# Load YOLO Model
# ==========================================
model = load_model()

# ==========================================
# Load Registered Worker Faces
#
# Trains the face-matching recognizer from the current worker roster
# pulled from the backend (GET /workers/reference-photos/all -- see
# face_id.py). Registration itself now lives entirely on the UI side.
# If the backend is unreachable and there's no local cache yet, this
# is a harmless no-op -- every worker just keeps getting a normal
# session ID, same as before this feature existed.
# ==========================================
load_registered_faces()

# ==========================================
# Open Webcam
# ==========================================
cap = cv2.VideoCapture(CAMERA_SOURCE)

if not cap.isOpened():
    print("Error: Could not access webcam.")
    exit()

# ==========================================
# Start Live HLS Streaming (streaming.py)
#
# Uses the camera's OWN reported fps to figure out how many frames to
# skip so the display stream runs at STREAM_FPS -- NOT a second camera
# connection, just a downscaled/throttled copy of frames this loop
# already captures. Harmless no-op if ffmpeg isn't installed.
# ==========================================
start_stream(cap.get(cv2.CAP_PROP_FPS))

print("Starting Live Detection... Press 'q' to quit.")

# ==========================================
# Main Loop
#
# Wrapped in try/except/finally so that:
#   - a clean Ctrl+C always prints a friendly message instead of a
#     raw traceback (KeyboardInterrupt doesn't inherit from Exception,
#     so it can slip past the narrower except clauses elsewhere, e.g.
#     in backend_client.py, if it lands mid-network-call)
#   - cap.release() / cv2.destroyAllWindows() ALWAYS run, no matter
#     how the loop ends -- normal 'q' quit, an unexpected exception,
#     or Ctrl+C -- so the webcam never stays locked by a dead process
# ==========================================
try:

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        current_time = time.time()

        roi_pixels = normalized_to_pixels(ROI, frame.shape)

        # ==========================================
        # YOLO Tracking
        # ==========================================
        results = model.track(
            frame,
            persist=True,
            tracker="bytetrack_custom.yaml",
            conf=CONFIDENCE,
            iou=NMS_IOU_THRESHOLD,
            verbose=False
        )

        # ==========================================
        # Worker-wise Analysis
        # ==========================================
        workers = get_workers(results)

        # Collapse ByteTrack duplicate IDs for the same physical person
        workers = deduplicate_workers(workers)

        # Reject implausible person boxes before they poison PPE assignment
        workers = filter_worker_boxes(workers, frame.shape)

        # Drop workers outside the monitored zone -- e.g. someone walking
        # past in the background shouldn't count against site compliance
        if roi_enabled:
            workers = filter_workers_by_roi(workers, roi_pixels, ROI_MIN_OVERLAP_FRACTION)

        # Re-attach a worker to their old canonical ID if ByteTrack handed
        # them a new one after a brief tracking glitch
        workers = stabilize_worker_ids(
            workers,
            last_known_positions,
            current_time,
            ID_CONTINUITY_MAX_GAP_SECONDS,
            ID_CONTINUITY_IOU_THRESHOLD,
            ID_CONTINUITY_MAX_CENTER_DISTANCE
        )

        # If this worker's face matches someone in the backend's worker
        # roster, swap their session ID for that permanent ID (and
        # report the match back to the backend for auto-linking) --
        # everything from here on (PPE assignment, violation events,
        # evidence, duration) accumulates against the permanent
        # identity instead of a session-only number. A
        # no-op if nobody's enrolled yet.
        workers, newly_closed_duplicates = remap_to_permanent_ids(workers, frame, PERMANENT_ID_OFFSET)

        # Almost always empty -- only populated in the rare case where
        # the same real person got tracked under two different session
        # IDs before either matched a face, and the second one to match
        # found its target permanent identity already had its own open
        # event (see migrate_open_event()'s docstring in violations.py).
        # Report these exactly like any other transition so the
        # backend's record for the orphaned session ID gets closed out
        # now instead of silently left "open" from its point of view.
        pending_transitions.extend(newly_closed_duplicates)

        workers = assign_ppe(results, workers)

        workers = calculate_worker_violations(workers)

        # ==========================================
        # Presence + Violation Events
        #
        # Presence (first_seen/last_seen) is tracked every frame
        # regardless of violation state. Violations go through the
        # event lifecycle in violations.py: a new event opens only
        # when a violation STARTS, the same event is updated while
        # it continues, and it's resolved (closed) once the worker
        # is compliant again. Evidence is captured exactly once, at
        # the moment an event opens -- never per-frame, never twice
        # for the same ongoing incident. A violation CLIP is captured
        # at that same "opened" moment too -- see clip_recorder.py.
        # ==========================================
        newly_recorded_clips = {}

        for worker_id, info in workers.items():

            presence = update_worker_presence(worker_id)

            # Require a short run of consecutive frames before this
            # worker is allowed to open a violation event at all. This
            # is what stops a one-off false-positive "Person" detection
            # on background clutter from generating its own violation
            # event and evidence photo -- a real worker stays in frame
            # far longer than MIN_CONFIRMATION_FRAMES, a spurious blip
            # usually doesn't.
            if presence["total_frames_seen"] < MIN_CONFIRMATION_FRAMES:
                continue

            def capture_evidence(wid=worker_id, w_info=info):
                return save_violation_image(
                    frame,
                    wid,
                    w_info["bbox"],
                    w_info["violations"],
                    CAMERA_NAME
                )

            event, transition = record_violation_state(
                worker_id,
                info["violations"],
                CAMERA_NAME,
                capture_evidence
            )

            if event is not None:
                info["image"] = event["evidence_image"]

            if transition == "opened":

                # Pre-roll clip from whatever's currently buffered
                # (clip_recorder.py) -- same "exactly once, at the
                # moment the incident starts" rule as the evidence
                # photo above. None if the buffer was empty (e.g. this
                # happened within the first second of the process
                # starting) -- treated as "no clip this time," not an
                # error.
                clip_path = save_violation_clip(worker_id)

                if clip_path:
                    newly_recorded_clips[worker_id] = clip_path

            if transition in ("opened", "resolved"):
                pending_transitions.append((event, transition))

        # ==========================================
        # Close out any open event whose worker simply isn't in
        # frame anymore -- otherwise an event stays "open" forever
        # if the worker walks off still in violation, since the loop
        # above only ever sees workers actually present this frame.
        # Uses the SAME grace window as ID-continuity stitching, so
        # a worker mid-way through a brief tracking gap gets
        # re-attached to their event instead of it being closed out
        # from under them.
        # ==========================================
        abandoned = resolve_stale_events(
            set(workers.keys()),
            ID_CONTINUITY_MAX_GAP_SECONDS
        )

        pending_transitions.extend(abandoned)

        # ==========================================
        # Overall Report
        # ==========================================
        report = generate_report(results, workers)

        # ==========================================
        # Backend Update: send only when a violation
        # event actually opened/resolved this frame, or
        # on a periodic heartbeat -- never a blind
        # per-second poll of current state.
        # ==========================================
        is_heartbeat = (current_time - last_heartbeat) >= HEARTBEAT_SECONDS
        should_send = pending_transitions or is_heartbeat

        if should_send:

            print("\n========== WORKERS ==========\n")

            for worker_id, info in workers.items():

                registered_name = get_registered_name(worker_id)

                label = (
                    f"Worker {worker_id} ({registered_name})"
                    if registered_name else f"Worker {worker_id}"
                )

                print(label)

                print(info)

                print()

            if pending_transitions:

                print("========== EVENTS ==========\n")

                for event, transition in pending_transitions:

                    print(
                        f"[{transition.upper()}] event #{event['event_id']} "
                        f"worker {event['worker_id']} -- {event['violations']} "
                        f"(duration so far: {event['duration_seconds']}s)"
                    )

                print()

            print("========== REPORT ==========\n")

            print(report)

            reason = (
                f"{len(pending_transitions)} event(s)"
                if pending_transitions else "heartbeat"
            )
            print(f"\n========== JSON ({reason}) ==========\n")

            # Build the payload here (fast, in-memory, no network) and
            # hand it off to the background thread -- queue_backend_send()
            # returns immediately. The actual requests.post calls (main
            # report + evidence photo upload) happen off-thread, and any
            # retry-on-failure is backend_worker.py's job now, not the
            # video loop's. See backend_worker.py for why this is safe:
            # the payload is a static snapshot by the time it's queued.
            payload = build_payload(report, workers, pending_transitions)

            # Only events that just OPENED this round get an evidence
            # photo uploaded -- never "updated" (still ongoing) or
            # "resolved"/"abandoned". Snapshotting this as plain
            # (worker_id, path) tuples keeps the handoff to the
            # background thread free of any live object references.
            opened_evidence = [
                (event["worker_id"], event["evidence_image"])
                for event, transition in pending_transitions
                if transition == "opened"
            ]

            # Same idea for violation clips -- newly_recorded_clips was
            # populated in the per-worker loop above, keyed by whatever
            # worker_id was current AT THE MOMENT the event opened
            # (already the canonical/permanent id by this point, since
            # remap_to_permanent_ids runs before this loop). Read via
            # event["worker_id"] so this stays correct even in the
            # (normally impossible, since pending_transitions never
            # survives more than one frame) case of it spanning frames.
            # event["event_id"] is included per Mahani's optional
            # event_id support -- costs nothing since we already have
            # it, and lets her attach the clip to the exact event
            # instead of her "most recent" fallback.
            opened_clips = [
                (event["worker_id"], newly_recorded_clips[event["worker_id"]], event["event_id"])
                for event, transition in pending_transitions
                if transition == "opened" and event["worker_id"] in newly_recorded_clips
            ]

            queue_backend_send(payload, opened_evidence, opened_clips)

            last_heartbeat = current_time
            pending_transitions = []

        # ==========================================
        # Draw Detection
        #
        # Deliberately NOT using results[0].plot() -- that draws EVERY
        # raw YOLO/ByteTrack detection in the frame, at whatever
        # confidence just cleared the 0.4 floor, with none of our own
        # filtering applied (ROI, dedup, MIN_CONFIRMATION_FRAMES,
        # implausible-box rejection). That's what was causing random
        # background clutter to show up as "NO-Hardhat"/"NO-Mask"
        # boxes, and why the drawn boxes didn't match the on-screen
        # violation COUNTS -- the counts came from the filtered
        # `workers`/`report` data, the boxes came from raw model
        # output. Drawing only from `workers` below means the frame
        # always shows exactly what was counted and sent to the
        # backend -- nothing more, nothing less.
        # ==========================================
        annotated_frame = frame.copy()

        # ==========================================
        # Show Worker Boxes + IDs + Violations
        #
        # Drawn from the stabilized, filtered `workers` dict (canonical
        # IDs), not the raw YOLO/ByteTrack box list -- otherwise the
        # on-screen label could show a different ID than the
        # console/JSON output after ID stitching or dedup/filtering,
        # or show a "violation" that was never actually counted.
        # ==========================================
        for worker_id, info in workers.items():

            x1, y1, x2, y2 = info["bbox"]

            has_violation = len(info["violations"]) > 0
            box_color = (0, 0, 255) if has_violation else (0, 255, 0)

            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), box_color, 2)

            registered_name = get_registered_name(worker_id)

            label = (
                f"Worker {worker_id} ({registered_name})"
                if registered_name else f"Worker {worker_id}"
            )

            cv2.putText(
                annotated_frame,
                label,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2
            )

            # List exactly the violations this worker was actually
            # charged with (same list the report/backend payload use)
            # -- not a raw per-class detection box, so there's no way
            # for the screen to show something the count doesn't agree
            # with.
            for i, violation in enumerate(info["violations"]):

                cv2.putText(
                    annotated_frame,
                    violation,
                    (x1, y2 + 20 + (i * 22)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 0, 255),
                    2
                )

                # Precise per-item box, when assign_ppe() found an
                # actual "NO-X" detection inside THIS worker's real
                # body region this frame (worker_manager.py). Falls
                # back to just the text above (no box) on a frame
                # where the model didn't emit that specific detection
                # -- still a violation, just nothing precise to draw
                # that frame. Either way this only ever attaches to a
                # confirmed real worker, never background clutter,
                # since assign_ppe() only records these via the same
                # region-containment check used for present PPE.
                vbox = info.get("violation_boxes", {}).get(violation)

                if vbox:

                    vx1, vy1, vx2, vy2 = vbox
                    color = VIOLATION_BOX_COLORS.get(violation, (0, 0, 255))

                    cv2.rectangle(annotated_frame, (vx1, vy1), (vx2, vy2), color, 2)

                    cv2.putText(
                        annotated_frame,
                        violation,
                        (vx1, max(vy1 - 6, 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        color,
                        1
                    )

        # ==========================================
        # Live Statistics
        # ==========================================
        cv2.putText(
            annotated_frame,
            f"Workers: {report['workers']}",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )

        cv2.putText(
            annotated_frame,
            f"Helmet Violations: {report['helmet_violation']}",
            (20, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )

        cv2.putText(
            annotated_frame,
            f"Vest Violations: {report['vest_violation']}",
            (20, 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )

        cv2.putText(
            annotated_frame,
            f"Mask Violations: {report['mask_violation']}",
            (20, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )

        cv2.putText(
            annotated_frame,
            f"Compliance: {report['overall_compliance']}%",
            (20, 150),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 0),
            2
        )

        cv2.putText(
            annotated_frame,
            f"ROI: {'ON' if roi_enabled else 'OFF'} (r)   Zoom: {'ON' if zoom_enabled else 'OFF'} (z)",
            (20, 180),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (200, 200, 200),
            1
        )

        # ==========================================
        # ROI Overlay + Zoomed Inset
        # ==========================================
        if roi_enabled:

            annotated_frame = draw_roi_overlay(annotated_frame, roi_pixels)

            if zoom_enabled:

                inset = get_zoomed_inset(
                    frame,
                    roi_pixels,
                    zoom_factor=ZOOM_FACTOR,
                    inset_width=ZOOM_INSET_WIDTH
                )

                annotated_frame = overlay_inset(annotated_frame, inset)

        # ==========================================
        # Push to Live Stream (streaming.py)
        #
        # Sends the SAME annotated frame shown locally (worker boxes,
        # violation labels, compliance overlay) -- a safety dashboard
        # benefits from seeing what the AI flagged, not just a bare
        # camera view. Easy to switch to the raw `frame` instead if
        # Mahani/Vijay would rather the dashboard show a clean feed.
        # No-op if ffmpeg isn't running.
        # ==========================================
        push_frame(annotated_frame)

        # ==========================================
        # Feed the Violation Clip Buffer (clip_recorder.py)
        #
        # Same annotated frame, kept in a short rolling buffer so a
        # clip can be assembled the instant a violation opens (see the
        # per-worker loop above) without needing to have "already been
        # recording" from process start via some separate mechanism.
        # ==========================================
        record_frame(annotated_frame)

        # ==========================================
        # Display Video
        # ==========================================
        cv2.imshow(WINDOW_NAME, annotated_frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

        elif key == ord("r"):
            roi_enabled = not roi_enabled
            print(f"[ROI] filtering {'ENABLED' if roi_enabled else 'DISABLED'}")

        elif key == ord("z"):
            zoom_enabled = not zoom_enabled
            print(f"[Zoom] inset {'ENABLED' if zoom_enabled else 'DISABLED'}")

except KeyboardInterrupt:
    print("\nStopped by user (Ctrl+C). Shutting down cleanly...")

finally:

    # ==========================================
    # Cleanup -- always runs, no matter how the
    # loop above was exited.
    # ==========================================
    cap.release()
    cv2.destroyAllWindows()
    stop_stream()
