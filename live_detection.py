from worker_manager import (
    get_workers,
    deduplicate_workers,
    filter_worker_boxes,
    stabilize_worker_ids,
    assign_ppe,
    calculate_worker_violations
)

from backend_client import send_to_backend
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
    SHOW_ZOOM_INSET,
    ZOOM_FACTOR,
    ZOOM_INSET_WIDTH,
    MIN_CONFIRMATION_FRAMES,
    ID_CONTINUITY_MAX_GAP_SECONDS,
    ID_CONTINUITY_IOU_THRESHOLD,
    ID_CONTINUITY_MAX_CENTER_DISTANCE
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
pending_transitions = []

# Runtime-toggleable copies of the config defaults -- press 'r' to
# flip ROI filtering, 'z' to flip the zoom inset, while the app runs.
roi_enabled = ENABLE_ROI
zoom_enabled = SHOW_ZOOM_INSET


# ==========================================
# Load YOLO Model
# ==========================================
model = load_model()

# ==========================================
# Open Webcam
# ==========================================
cap = cv2.VideoCapture(CAMERA_SOURCE)

if not cap.isOpened():
    print("Error: Could not access webcam.")
    exit()

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
            tracker="bytetrack.yaml",
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
            workers = filter_workers_by_roi(workers, roi_pixels)

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
        # for the same ongoing incident.
        # ==========================================
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

        if pending_transitions or is_heartbeat:

            print("\n========== WORKERS ==========\n")

            for worker_id, info in workers.items():

                print(f"Worker {worker_id}")

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

            send_to_backend(report, workers, pending_transitions)

            last_heartbeat = current_time
            pending_transitions = []

        # ==========================================
        # Draw Detection
        # ==========================================
        annotated_frame = results[0].plot()

        # ==========================================
        # Show Worker IDs
        #
        # Drawn from the stabilized `workers` dict (canonical IDs),
        # not the raw YOLO/ByteTrack box list -- otherwise the on-screen
        # label could show a different ID than the console/JSON output
        # after ID stitching or dedup/filtering.
        # ==========================================
        for worker_id, info in workers.items():

            x1, y1, x2, y2 = info["bbox"]

            cv2.putText(
                annotated_frame,
                f"Worker {worker_id}",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2
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
