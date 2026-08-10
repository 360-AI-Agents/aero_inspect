"""
clip_recorder.py

Violation clip recording -- milestone 2 of the video-streaming feature
agreed with Mahani. Maintains a short rolling buffer of recent frames
and, the moment a violation event OPENS (same trigger evidence.py's
single photo already uses), encodes that buffer into a short local
MP4 clip for upload -- "what led up to and included the moment this
violation started," not a live camera feed and not a recording of the
whole incident.

Deliberate MVP scope: PRE-ROLL only, no post-roll. The trigger frame
itself already shows the violation in progress (that's WHY the event
just opened), so a pre-roll-only clip still ends on a frame showing
the actual violation -- it just doesn't keep recording for a few more
seconds AFTER that moment. True pre+post-roll would mean holding this
clip "pending" across several more loop iterations before finalizing/
uploading it -- a reasonable next enhancement, not attempted here to
keep this piece shippable and testable now.

Buffers a DOWNSCALED copy of each frame (same resolution as the live
stream's sub-stream, config.STREAM_WIDTH/HEIGHT) rather than full
camera resolution -- keeps memory bounded (tens of MB, not hundreds)
since this buffer runs continuously for the entire life of the
process, regardless of whether a violation ever actually uses it.
"""

import os
import time
import threading
import collections
import cv2

from config import (
    STREAM_WIDTH,
    STREAM_HEIGHT,
    CLIP_BUFFER_SECONDS,
    CLIP_BUFFER_FPS,
    CLIP_FOLDER
)

os.makedirs(CLIP_FOLDER, exist_ok=True)

_buffer = collections.deque(maxlen=CLIP_BUFFER_SECONDS * CLIP_BUFFER_FPS)

_last_append_time = 0
_MIN_APPEND_INTERVAL = 1.0 / CLIP_BUFFER_FPS


def record_frame(frame):
    """
    Call once per frame from the main loop, with the SAME annotated
    frame already shown locally/streamed -- throttled internally to
    CLIP_BUFFER_FPS so this costs very little regardless of how fast
    the actual detection loop runs, and so the buffer holds a
    predictable CLIP_BUFFER_SECONDS worth of frames rather than
    growing/shrinking with the camera's own frame rate.
    """

    global _last_append_time

    now = time.time()

    if now - _last_append_time < _MIN_APPEND_INTERVAL:
        return

    _last_append_time = now

    small_frame = cv2.resize(frame, (STREAM_WIDTH, STREAM_HEIGHT))

    _buffer.append(small_frame)


def _encode_clip(frames, worker_id, filepath):
    """
    The actual encoding work -- runs on a background thread (see
    save_violation_clip() below). Encoding ~80 buffered frames via
    cv2.VideoWriter is not instant, and doing it inline in the main
    video loop caused a visible stutter every time a violation opened
    (confirmed in testing -- lag correlated exactly with violation
    events). Moving it here means the main loop never blocks on it;
    it just keeps capturing/displaying/detecting frames as normal
    while this writes the file in the background.
    """

    try:

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(filepath, fourcc, CLIP_BUFFER_FPS, (STREAM_WIDTH, STREAM_HEIGHT))

        for buffered_frame in frames:
            writer.write(buffered_frame)

        writer.release()

    except Exception as e:

        print(f"[ClipRecorder] Could not write violation clip for worker {worker_id}: {e}")


def save_violation_clip(worker_id):
    """
    Snapshot everything currently in the rolling buffer and hand the
    actual encoding off to a background thread, returning the file
    path IMMEDIATELY (before encoding finishes) -- so the main video
    loop is never blocked waiting for a clip to write. Call exactly
    once, at the moment a violation event OPENS -- never for an
    "updated"/"resolved"/"abandoned" transition, mirroring evidence.py's
    single-photo-per-incident rule.

    Known trade-off, not a fully airtight guarantee: the returned path
    may not have a complete file on disk the INSTANT this returns --
    only once the background thread finishes a moment later. This is
    fine in practice, since the actual upload (backend_worker.py) only
    happens after the main report's own network round-trip completes,
    which normally takes longer than encoding ~80 small frames does.
    send_violation_clip() also tolerates a short "not there yet" gap
    (see backend_client.py) as a safety net for the rare case it isn't.

    Returns None (not an exception) if the buffer is empty (e.g.
    called within the first second of the process starting) --
    callers should treat that as "no clip this time," same as a
    missing evidence photo, not a fatal error.
    """

    if not _buffer:
        return None

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"worker_{worker_id}_{timestamp}.mp4"
    filepath = os.path.join(CLIP_FOLDER, filename)

    # Snapshot the buffer's CURRENT contents into a plain list before
    # handing off -- _buffer is a deque that keeps getting appended to
    # by record_frame() on the main thread, so the background thread
    # needs its own frozen copy, not a live reference into it.
    frames_snapshot = list(_buffer)

    encode_thread = threading.Thread(
        target=_encode_clip,
        args=(frames_snapshot, worker_id, filepath),
        daemon=True
    )
    encode_thread.start()

    return filepath
