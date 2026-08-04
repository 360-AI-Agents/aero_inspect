"""
streaming.py

Live HLS video streaming for the dashboard -- milestone 1 of the
video-streaming feature agreed with Mahani (HLS + ffmpeg relay, one
architecture for both today's webcam and next week's RTSP site
camera, a lower-res "display" sub-stream decoupled from the full-res
frames YOLO analyzes). Violation clip recording/upload is a separate
follow-up piece, once Mahani has a clip-upload endpoint ready -- this
file is just the continuous live view.

Deliberately does NOT open the camera a second time. cv2.VideoCapture
in live_detection.py is the ONLY thing that ever reads from
CAMERA_SOURCE -- this module receives a copy of each frame
live_detection.py already captured, resizes/throttles it, and pipes
the raw bytes into a persistent ffmpeg subprocess via stdin. ffmpeg
does the actual encoding + HLS segmenting; this file just manages
that subprocess's lifecycle.

Why not let ffmpeg open the camera itself? Most cameras (a plain USB
webcam especially) only allow ONE process to hold them open at a
time -- OpenCV already owns that for YOLO, so a second independent
open from ffmpeg would likely just fail or conflict. Feeding it
frames already decoded sidesteps that entirely, and means the exact
same code works unchanged whether CAMERA_SOURCE is a webcam index or
(next week) an RTSP URL -- either way, OpenCV is still the single
point of frame acquisition.

Setup: requires ffmpeg installed and on PATH -- this is a SYSTEM
dependency, not a pip package (`pip install` won't get it). Windows:
download a static build from https://www.gyan.dev/ffmpeg/builds/ (the
"essentials" build is enough), unzip it somewhere permanent, add its
bin/ folder to your PATH environment variable, then open a NEW
terminal and confirm with `ffmpeg -version` (existing terminals won't
pick up a PATH change). If ffmpeg isn't found, this module disables
itself and prints a warning -- detection/violations/backend reporting
all continue completely unaffected either way.
"""

import os
import subprocess
import shutil
import threading
import time
import cv2

from backend_client import send_stream_file
from config import (
    FFMPEG_PATH,
    STREAM_WIDTH,
    STREAM_HEIGHT,
    STREAM_FPS,
    HLS_OUTPUT_FOLDER,
    HLS_SEGMENT_SECONDS,
    HLS_PLAYLIST_SIZE,
    STREAM_UPLOAD_POLL_SECONDS,
    CAMERA_NAME
)

_ffmpeg_process = None
_frame_interval = 1     # recomputed in start_stream() from the camera's real fps
_frame_counter = 0

# ---------------------------------------------------------------
# Push-to-backend uploader
#
# The architecture agreed with Mahani: this side PUSHES the playlist
# + each new segment to the backend (mirrors send_evidence_photo()'s
# shape), rather than exposing a direct URL on this machine for the
# dashboard to pull from. Runs on its own background thread, polling
# HLS_OUTPUT_FOLDER -- decoupled from the video loop entirely, so a
# slow/unreachable backend can never stall detection, same principle
# as backend_worker.py.
#
# Exact contract, so the backend's receiving endpoint matches this
# exactly instead of guessing:
#   - Playlist filename is CONSTANT ("stream.m3u8") -- ffmpeg rewrites
#     the same file in place every time a new segment completes, so
#     this uploads it again (overwrite) each time its mtime changes.
#   - Segment filenames INCREMENT and are never reused/overwritten
#     (segment_00001.ts, segment_00002.ts, ...) -- each one is
#     uploaded exactly once, the moment it's noticed.
#   - A new segment completes roughly every HLS_SEGMENT_SECONDS
#     (default 4s) -- that's also, in practice, how often the
#     playlist gets re-uploaded, since ffmpeg rewrites it each time.
# ---------------------------------------------------------------
_uploader_thread = None
_uploader_running = False
_uploaded_segments = set()
_last_playlist_mtime = None


def _uploader_loop():

    global _last_playlist_mtime

    playlist_path = os.path.join(HLS_OUTPUT_FOLDER, "stream.m3u8")

    while _uploader_running:

        try:

            if os.path.exists(playlist_path):

                mtime = os.path.getmtime(playlist_path)

                if mtime != _last_playlist_mtime:

                    if send_stream_file(CAMERA_NAME, "stream.m3u8", "playlist", playlist_path):
                        _last_playlist_mtime = mtime
                    # On failure, _last_playlist_mtime is left unchanged
                    # so the next poll retries this same upload rather
                    # than silently moving on.

            if os.path.isdir(HLS_OUTPUT_FOLDER):

                current_segments = {
                    name for name in os.listdir(HLS_OUTPUT_FOLDER)
                    if name.endswith(".ts")
                }

                # Drop anything ffmpeg's own delete_segments cleanup
                # already removed locally -- keeps this set bounded to
                # roughly HLS_PLAYLIST_SIZE instead of growing for the
                # life of the process.
                _uploaded_segments.intersection_update(current_segments)

                for name in sorted(current_segments - _uploaded_segments):

                    segment_path = os.path.join(HLS_OUTPUT_FOLDER, name)

                    if send_stream_file(CAMERA_NAME, name, "segment", segment_path):
                        _uploaded_segments.add(name)
                    # On failure, NOT added to _uploaded_segments -- the
                    # next poll retries it, same "delivered late beats
                    # silently dropped" principle as backend_worker.py.

        except Exception as e:

            print(f"[Streaming] Uploader loop error (will keep retrying): {e}")

        time.sleep(STREAM_UPLOAD_POLL_SECONDS)

_FFMPEG_AVAILABLE = shutil.which(FFMPEG_PATH) is not None

if not _FFMPEG_AVAILABLE:
    print(
        f"[Streaming] Warning: '{FFMPEG_PATH}' not found on PATH -- live "
        f"HLS streaming is DISABLED for this run (detection is completely "
        f"unaffected). Install ffmpeg and add it to PATH to enable this -- "
        f"see this module's docstring for a Windows install pointer."
    )


def start_stream(source_fps):
    """
    Launch the persistent ffmpeg subprocess that receives raw frames
    on stdin and writes HLS segments to HLS_OUTPUT_FOLDER. Call once
    at startup, right after the camera is opened (so source_fps --
    the camera's OWN reported frame rate -- is known). Harmless no-op
    if ffmpeg isn't available.

    source_fps is used to compute how many incoming frames to SKIP so
    the display stream runs at STREAM_FPS regardless of how fast the
    camera/YOLO loop actually runs -- e.g. a 30fps camera with
    STREAM_FPS=12 sends roughly every 2nd-3rd frame to ffmpeg, not
    every single one.
    """

    global _ffmpeg_process, _frame_interval, _uploader_thread, _uploader_running, _uploaded_segments, _last_playlist_mtime

    if not _FFMPEG_AVAILABLE:
        return

    os.makedirs(HLS_OUTPUT_FOLDER, exist_ok=True)

    # Clear out anything left over from a PREVIOUS run before starting
    # a fresh one. This matters more than it looks: if the last run
    # shut down cleanly, ffmpeg's final write to stream.m3u8 appends
    # #EXT-X-ENDLIST -- the tag that marks a playlist as a finished,
    # fixed-length VOD clip rather than an ongoing live stream. With
    # "append_list" (removed below) that stale, ENDLIST-terminated
    # file would otherwise still be sitting there for a player to load
    # before this run's first fresh segment even lands, and some
    # players latch onto whatever they first saw -- which matches
    # exactly what showed up on the dashboard (a fixed clip with a
    # scrub bar, not a live feed). Starting every run from a genuinely
    # empty folder means the very first stream.m3u8 a player can
    # possibly fetch is this run's own, live, ENDLIST-free one.
    for name in os.listdir(HLS_OUTPUT_FOLDER):
        if name.endswith(".ts") or name.endswith(".m3u8"):
            try:
                os.remove(os.path.join(HLS_OUTPUT_FOLDER, name))
            except OSError:
                pass

    _uploaded_segments = set()
    _last_playlist_mtime = None

    # Guard against a nonsense/zero source_fps (some webcams/backends
    # misreport this) -- fall back to a sane assumption rather than
    # dividing by zero or accidentally sending every single frame.
    safe_source_fps = source_fps if source_fps and source_fps > 0 else 30
    _frame_interval = max(1, round(safe_source_fps / STREAM_FPS))

    playlist_path = os.path.join(HLS_OUTPUT_FOLDER, "stream.m3u8")
    segment_path = os.path.join(HLS_OUTPUT_FOLDER, "segment_%05d.ts")

    command = [
        FFMPEG_PATH,
        "-y",
        "-f", "rawvideo",
        "-pixel_format", "bgr24",
        "-video_size", f"{STREAM_WIDTH}x{STREAM_HEIGHT}",
        "-framerate", str(STREAM_FPS),
        "-i", "-",                      # read raw frames from stdin
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "zerolatency",
        # Explicit pixel format + profile/level -- WITHOUT -pix_fmt,
        # libx264's default can end up something other than yuv420p
        # depending on the ffmpeg build, which Safari's MSE-based HLS
        # player rejects outright (bufferAddCodecError) even though
        # it's still technically H.264. yuv420p + High profile is the
        # broadly-compatible combination basically every HLS player
        # (Safari included) can decode.
        "-pix_fmt", "yuv420p",
        "-profile:v", "high",
        "-level", "4.0",
        "-g", str(STREAM_FPS * 2),      # keyframe every ~2s -- HLS needs frequent keyframes
        "-f", "hls",
        "-hls_time", str(HLS_SEGMENT_SECONDS),
        "-hls_list_size", str(HLS_PLAYLIST_SIZE),
        # NOT "append_list" -- that flag makes ffmpeg continue writing
        # onto whatever playlist file already exists instead of
        # starting fresh, which is wrong here: every run of this
        # script is its own independent live session (a new camera
        # open, a new ffmpeg process), not a continuation of the last
        # one. See start_stream()'s cleanup step above for why this
        # combination was producing a "looks like a finished recording"
        # playlist instead of a genuinely live one.
        "-hls_flags", "delete_segments",
        "-hls_segment_filename", segment_path,
        playlist_path
    ]

    try:

        _ffmpeg_process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        print(
            f"[Streaming] HLS relay started -- writing to "
            f"{HLS_OUTPUT_FOLDER}/stream.m3u8 at {STREAM_WIDTH}x"
            f"{STREAM_HEIGHT}@{STREAM_FPS}fps (source ~{safe_source_fps:.0f}fps, "
            f"sending every {_frame_interval} frame(s))."
        )

        _uploader_running = True
        _uploader_thread = threading.Thread(target=_uploader_loop, daemon=True)
        _uploader_thread.start()

        print("[Streaming] Uploader thread started -- pushing playlist/segments to the backend.")

    except Exception as e:

        print(f"[Streaming] Could not start ffmpeg -- streaming disabled for this run: {e}")
        _ffmpeg_process = None


def push_frame(frame):
    """
    Call once per frame from the main loop, with the SAME frame
    already produced for display (annotated with worker boxes/
    violation labels) -- this resizes a COPY down to the display
    resolution and throttles to STREAM_FPS before writing to ffmpeg,
    so this never affects what YOLO itself analyzes or the local
    preview window's own framerate.

    Cheap, harmless no-op if streaming isn't running (ffmpeg missing,
    failed to start, or not yet started).
    """

    global _frame_counter

    if _ffmpeg_process is None:
        return

    _frame_counter += 1

    if _frame_counter % _frame_interval != 0:
        return

    try:

        small_frame = cv2.resize(frame, (STREAM_WIDTH, STREAM_HEIGHT))

        _ffmpeg_process.stdin.write(small_frame.tobytes())

    except (BrokenPipeError, OSError) as e:

        # ffmpeg died or its pipe closed -- don't crash the video loop
        # over a streaming failure. Detection/violations/backend
        # reporting all continue completely unaffected.
        print(f"[Streaming] Lost connection to ffmpeg -- streaming stopped for this run: {e}")
        stop_stream()


def stop_stream():
    """
    Cleanly shut down the ffmpeg subprocess -- close stdin so ffmpeg
    finishes writing its current segment and exits gracefully instead
    of being killed mid-write. Call from live_detection.py's cleanup
    (the same finally: block that already handles cap.release()).
    """

    global _ffmpeg_process, _uploader_running

    _uploader_running = False  # signals the uploader thread to exit its loop

    if _ffmpeg_process is None:
        return

    try:

        _ffmpeg_process.stdin.close()
        _ffmpeg_process.wait(timeout=5)

    except Exception:

        _ffmpeg_process.kill()

    finally:

        _ffmpeg_process = None

        print("[Streaming] HLS relay stopped.")
