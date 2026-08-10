MODEL_PATH = "best.pt"

CAMERA_SOURCE = 0

# ---------------------------------------------------------------
# Worker Identity (registration.py + face_id.py)
#
# registration.py assigns permanent worker IDs (1, 2, 3...) that are
# meant to persist across restarts/days -- separate from ByteTrack's
# own session-scoped track IDs (ALSO small increasing integers
# starting near 1). Those two ID spaces would otherwise collide: a
# face-matched permanent worker_id=1 could numerically clash with an
# unrelated ByteTrack session id=1 assigned to a totally different
# person in the same frame. Offsetting every permanent ID by a large
# constant before it's used as a `workers` dict key keeps the two
# namespaces from ever overlapping in practice for a single test
# session -- e.g. registered worker 1 becomes internal key 100001.
# ---------------------------------------------------------------
PERMANENT_ID_OFFSET = 100000

CONFIDENCE = 0.4

# A stricter floor applied only to "Person" detections. A wrong
# PPE call is annoying; a phantom "worker" detected on background
# clutter is worse (it pollutes violation events and evidence storage
# forever), so we hold Person detections to a slightly higher bar
# than PPE -- but only slightly. 0.6 was tried and immediately broke
# a REAL detection at 0.56 confidence (a worker went completely
# undetected -- worse than any false positive, since a missed real
# violation beats a phantom one every time). Backed off to 0.45.
#
# Nudged 0.45 -> 0.50 after real evidence gave an actual number to
# work with: a hanging jacket on the wall (clothing/fabric clutter,
# same class of false positive as an earlier stuffed-toy pile) was
# confidently detected as "Person" at 0.4595 -- just above the old
# 0.45 floor. 0.50 excludes that specific case while staying a clear
# 0.06 below the lowest REAL detection ever observed (0.56, the case
# that broke at 0.6 above), so it shouldn't reintroduce that failure.
# Not a permanent fix -- another clutter object could still land
# somewhere in the 0.50-0.56 gap, in which case this is a config
# value to revisit again from new evidence, not a solved problem.
# MIN_CONFIRMATION_FRAMES below remains the PRIMARY defense against
# transient background false positives; this confidence floor is
# still a backstop, not the main filter.
PERSON_MIN_CONFIDENCE = 0.50

# How many consecutive frames a worker must be continuously present
# for before they're allowed to open a violation event (or have
# evidence captured) at all. A real worker stays in frame far longer
# than a one-off spurious background blip does, so this filters those
# out without having to reject real people via confidence alone.
MIN_CONFIRMATION_FRAMES = 6

# NMS IoU threshold passed to model.track(). Ultralytics' own default
# (0.7) only suppresses near-identical duplicate boxes for the same
# object. In practice the model sometimes throws two "Person" boxes
# for one real person with overlap in the 0.4-0.5 range -- below the
# default, so both survive into tracking as separate workers (and,
# with the event system, as two separate violation events for one
# real incident). Tightened twice now: first 0.7 -> 0.45 for an
# observed ~0.50 overlap case, then 0.45 -> 0.35 after a second case
# came in at ~0.40 overlap. This makes YOLO merge those at the
# source, before ByteTrack ever sees them.
#
# Trade-off to watch: push this too low and two genuinely DIFFERENT
# people standing close together risk being merged into one. 0.35 is
# still well above the overlap two people just standing near each
# other would normally produce -- but if a future test with two real,
# distinct people shows them getting incorrectly merged, that's the
# signal to stop lowering this value and solve it a different way
# (e.g. requiring a minimum center-distance in addition to low IoU).
NMS_IOU_THRESHOLD = 0.35

WINDOW_NAME = "AeroInspect AI"

# One base URL for the backend -- everything else derives from it, so
# changing IP/port only ever needs editing this one line.
BACKEND_BASE_URL = "http://192.168.137.178:8000"

# Main detection report endpoint (JSON only -- no image bytes).
API_URL = f"{BACKEND_BASE_URL}/api/live_detection/"

# Separate endpoint for the evidence PHOTO itself (multipart file
# upload), since JSON can't carry raw image bytes cleanly. Only ever
# called once per violation event, at the moment it opens -- see
# send_evidence_photo() in backend_client.py.
EVIDENCE_API_URL = f"{BACKEND_BASE_URL}/api/live_detection/evidence"

# ---------------------------------------------------------------
# Worker identity now lives entirely on the backend/UI side --
# registration.py's old local camera-capture flow is no longer used
# by live_detection.py (see that file's docstring). Instead, face_id.py
# pulls the current worker roster + reference photos from the first
# URL below, and reports a confident face match back via the second
# so the backend can auto-link a tracking ID to a real employee
# profile instead of an admin doing it by hand.
# ---------------------------------------------------------------
REFERENCE_PHOTOS_URL = f"{BACKEND_BASE_URL}/workers/reference-photos/all"
LINK_TRACKER_URL = f"{BACKEND_BASE_URL}/workers/link-tracker"

# ---------------------------------------------------------------
# Live HLS Streaming (streaming.py)
#
# Milestone 1 of the video-streaming feature agreed with Mahani: an
# ffmpeg relay producing HLS, fed from a downscaled/throttled COPY of
# the same frames already captured for YOLO -- never a second camera
# connection. Same setup works unchanged for today's webcam and next
# week's RTSP site camera, since either way this only ever sees
# frames OpenCV already decoded.
# ---------------------------------------------------------------
FFMPEG_PATH = "ffmpeg"  # assumes ffmpeg is installed and on PATH

# Display stream is intentionally lower-res/lower-fps than what YOLO
# analyzes -- the "sub-stream vs main-stream" split real IP cameras
# already use internally. Detection is completely unaffected by these.
STREAM_WIDTH = 640
STREAM_HEIGHT = 360
STREAM_FPS = 12

HLS_OUTPUT_FOLDER = "stream"
HLS_SEGMENT_SECONDS = 4    # shorter = lower latency, more file churn
HLS_PLAYLIST_SIZE = 6      # how many recent segments the .m3u8 keeps listed

# Push endpoint for HLS files -- mirrors EVIDENCE_API_URL's shape
# (multipart upload) rather than exposing a direct URL on this
# machine, per the architecture agreed with Mahani: this side pushes,
# her backend stores/serves. See streaming.py's uploader.
STREAM_UPLOAD_URL = f"{BACKEND_BASE_URL}/api/live_detection/stream/segment"

# How often the uploader checks HLS_OUTPUT_FOLDER for a new segment or
# an updated playlist to push. Doesn't need to be faster than
# HLS_SEGMENT_SECONDS itself -- nothing new to send in between.
STREAM_UPLOAD_POLL_SECONDS = 1

# ---------------------------------------------------------------
# Violation Clip Recording (clip_recorder.py)
#
# Milestone 2 of the video-streaming feature: a short PRE-ROLL clip
# captured the instant a violation event opens (same trigger as the
# single evidence photo), uploaded via Mahani's contract -- worker_id
# + inspection_id + file, identical shape to evidence photos, matched
# the same way (using the inspection_id from the SAME report send
# that carried this event's "opened" transition -- see
# backend_worker.py). No event_id needed: our own reporting model
# only ever includes at most one "opened" event per worker per
# inspection, so worker_id + inspection_id already uniquely resolves.
# ---------------------------------------------------------------
CLIP_UPLOAD_URL = f"{BACKEND_BASE_URL}/api/live_detection/clip"

# How many seconds of recent frames to keep buffered, and at what
# throttled rate -- keeps memory bounded (a few dozen MB) since this
# buffer runs continuously for the life of the process, not just
# during a violation.
CLIP_BUFFER_SECONDS = 8
CLIP_BUFFER_FPS = 10
CLIP_FOLDER = "clips"

CAMERA_NAME = "Tower Camera 01"

LOCATION = "Block A"

# ---------------------------------------------------------------
# Region of Interest (ROI) / Zoom
#
# Restrict monitoring to a specific zone of the frame (e.g. the
# actual work platform) instead of the whole camera view, and show
# a digitally zoomed inset of that zone so small/distant workers are
# easier for an operator to see. Coordinates are normalized
# (0.0-1.0) so the same ROI definition works at any resolution.
# Toggle at runtime with 'r' (ROI filtering) and 'z' (zoom inset)
# while live_detection.py is running.
# ---------------------------------------------------------------
ENABLE_ROI = True

# (x1, y1, x2, y2) as fractions of frame width/height.
#
# NOTE: on a real wide CCTV/drone shot, this should be a SMALL box
# around the actual work platform (e.g. 0.3-0.4 of the frame width) --
# that's what makes the zoom inset useful, since you're magnifying a
# small distant area. On a close-up webcam test there's nothing far
# away to zoom into, so this default is deliberately a smaller,
# upper-body box just so you can *see* the zoom effect working.
# Widen it back out (e.g. back to (0.1, 0.05, 0.9, 0.95)) once you're
# testing with an actual wide-angle site camera.
#
# Left edge pushed in from 0.1 -> 0.3 to exclude a mirror on the left
# wall of the test room -- it was reflecting a second, smaller image
# of whoever's in frame, which the model correctly detected as a
# "Person" (it looks like one) but which isn't a real second worker.
# This is a test-environment fix, not a general code fix -- a real
# job site is unlikely to have a mirror in frame. Revert this back
# toward 0.1 (or wherever) once testing somewhere without a mirror.
ROI = (0.3, 0.05, 0.9, 0.95)

# How much of a worker's OWN box area must fall inside the ROI to
# count as "in the zone" (roi.py) -- replaced a pure center-point
# check after a low-confidence, edge-of-frame false-positive detection
# (mostly outside the zone) still passed because its center alone
# crept just inside the boundary. 0.5 is a starting point: a box
# needs at least half its area actually inside to count. Tune from
# real evidence, same as other thresholds in this app.
ROI_MIN_OVERLAP_FRACTION = 0.5

SHOW_ZOOM_INSET = True
ZOOM_FACTOR = 2.0
ZOOM_INSET_WIDTH = 260

# ---------------------------------------------------------------
# Cross-frame ID continuity ("track stitching")
#
# ByteTrack sometimes drops a person for a frame or two (motion
# blur, brief occlusion) and hands them a brand-new ID when they
# reappear. Full re-identification (face/appearance matching) is
# future work -- but in the meantime, we catch the common case
# cheaply: if a worker disappears and, within a grace window, a
# *new* ID shows up in about the same spot, it's almost certainly
# the same person.
#
# Honest limitation: this is spatial/temporal heuristics, not real
# identity. A worker gone for minutes (lunch break) will still get a
# new ID -- and if a *different* person stands in roughly the same
# spot within the gap window, they could incorrectly inherit the old
# ID. Guaranteeing "exactly one capture per person for the whole day,
# no matter how long they're gone" requires real re-identification
# (stored reference photo + face/appearance matching), which remains
# future work.
# ---------------------------------------------------------------

# How long (seconds) a worker can be "missing" before we give up
# trying to re-attach a new ID to them. Widened from 2s -> 45s to
# cover realistic movement (stepping back, bending down, brief
# occlusion) without needing full re-identification.
ID_CONTINUITY_MAX_GAP_SECONDS = 45.0

# How much a new detection's box must overlap a recently-vanished
# worker's last known box to be considered "probably the same person".
ID_CONTINUITY_IOU_THRESHOLD = 0.5

# Fallback: if boxes don't overlap enough (because the worker moved
# during the gap), still re-attach if the new box's center is within
# this many pixels of the vanished worker's last known center.
#
# Widened from 220 -> 350 after real evidence this was too tight: an
# earlier near-miss failed re-attachment at 219.5px (just under the old
# threshold), and later the same person was logged as three separate
# workers (IDs 3, 4, 401) in the live dashboard because reappearing
# detections kept landing just outside 220px of their last known spot.
# This is expected to happen more on close-range webcam testing than on
# a real site camera: at close range, a person taking one step covers a
# much larger number of PIXELS than the same physical step would on a
# wide, distant CCTV/drone shot. Revisit this back down once testing
# with an actual wide-angle site camera, where 220 (or less) may be
# plenty.
#
# Trade-off to watch: widening this raises the risk of the OPPOSITE
# failure -- a different person who happens to stand within 350px of
# where the last one vanished could incorrectly inherit their ID. If a
# future test shows that happening, this is the value to bring back
# down (paired with the ByteTrack track_buffer increase in
# bytetrack_custom.yaml, which reduces how often a brand new ID gets
# generated in the first place).
ID_CONTINUITY_MAX_CENTER_DISTANCE = 350