MODEL_PATH = "best.pt"

CAMERA_SOURCE = 0

CONFIDENCE = 0.4

# A stricter floor applied only to "Person" detections. A wrong
# PPE call is annoying; a phantom "worker" detected on background
# clutter is worse (it pollutes violation events and evidence storage
# forever), so we hold Person detections to a slightly higher bar
# than PPE -- but only slightly. 0.6 was tried and immediately broke
# a REAL detection at 0.56 confidence (a worker went completely
# undetected -- worse than any false positive, since a missed real
# violation beats a phantom one every time). Backed off to 0.45,
# just above the general CONFIDENCE floor. MIN_CONFIRMATION_FRAMES
# below is now the PRIMARY defense against transient background
# false positives -- this confidence floor is a light backstop only,
# not meant to carry that job alone.
PERSON_MIN_CONFIDENCE = 0.45

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

API_URL = "http://127.0.0.1:8000/api/live_detection"

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
ID_CONTINUITY_MAX_CENTER_DISTANCE = 220