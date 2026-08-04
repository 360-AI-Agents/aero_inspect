"""
face_id.py

Matches a currently-tracked worker's face against the worker roster
pulled from the BACKEND (GET /workers/reference-photos/all) so
violation events, evidence, and duration tie to a PERMANENT worker
identity -- the same person recognized across restarts and days --
instead of only worker_manager.stabilize_worker_ids()'s session-scoped
ID, which resets every time live_detection.py starts and only
survives brief in-session gaps.

Worker registration no longer happens on the AI side (see
registration.py's docstring) -- the UI owns that now: employee_id,
name, phone, company, role, site, shift, and a reference photo. This
module's job is narrower than before: fetch that roster + reference
photos, run face matching against the live feed, and when confident,
report the match back via POST /workers/link-tracker so the backend
can auto-link a YOLO tracking ID to a real employee profile instead of
an admin doing it by hand.

---------------------------------------------------------------------
MODEL CHANGE: LBPH -> InsightFace (ArcFace embeddings)
---------------------------------------------------------------------
This USED to run on OpenCV's LBPH recognizer (texture-histogram
matching) with a Haar cascade for face detection. Real testing showed
its limits once the backend started enrolling workers with only ONE
reference photo each (vs. the 5-photo capture our old local
registration flow used): LBPH's distances got noisy enough that
genuine matches and true non-matches overlapped in the same
60-80 "distance" band, no matter how the threshold was tuned --
tuning the number further wasn't going to fix a discrimination
problem in the underlying algorithm.

InsightFace's "buffalo_l" model produces a 512-dimension embedding
per face via ArcFace -- a real deep-learning face representation,
not a texture histogram. Critically, this is the standard tool for
EXACTLY the situation we're in: recognizing someone confidently off a
single reference photo. It also does its own face detection
internally (RetinaFace-based), which replaces the old Haar cascade
too -- one less fragile dependency (no more haarcascade_frontalface_
default.xml, no more "chin got clipped by the crop" failures).

Similarity here is COSINE SIMILARITY between two normalized
embeddings (higher = more confident match) -- the OPPOSITE convention
from LBPH's distance (lower = better). Comments below call this out
explicitly wherever it matters.

Setup note: `pip install insightface onnxruntime` (both pure-Python/
prebuilt-wheel installs on Windows -- no CMake/C++ build toolchain
needed, unlike dlib-based alternatives). The first run downloads the
buffalo_l model weights automatically (needs internet access once,
a couple hundred MB) -- expect a delay the very first time
load_registered_faces() runs after this change.

MATCH_SIMILARITY_THRESHOLD below is a reasonable starting point, NOT
a calibrated value -- same as MATCH_DISTANCE_THRESHOLD was for LBPH,
expect to tune it from the real numbers the diagnostic print in
match_worker_face() shows during actual testing, rather than trusting
the default blindly.
"""

import cv2
import json
import os
import numpy as np
import requests

from insightface.app import FaceAnalysis

from memory import migrate_presence
from violations import migrate_open_event
from backend_worker import queue_link_tracker
from config import PERMANENT_ID_OFFSET, BACKEND_BASE_URL, REFERENCE_PHOTOS_URL

# Local cache folder -- NOT a registration store anymore, just a copy
# of whatever the backend last sent, so a temporary backend/network
# outage at startup doesn't disable face matching entirely (see the
# fallback path in load_registered_faces()).
_CACHE_FOLDER = os.path.join("worker_registry", "reference_cache")
os.makedirs(_CACHE_FOLDER, exist_ok=True)

# The backend's identity is a string employee_id (e.g. "W-101"). This
# small local file maps it to a stable integer label, PERSISTED across
# restarts, so the same employee always gets the same internal label
# -- and therefore the same PERMANENT_ID_OFFSET-shifted worker_id --
# run after run, not just within one session.
# {employee_id: {"label": int, "name": str}}
_LABEL_CACHE_FILE = os.path.join("worker_registry", "employee_id_labels.json")

_employee_meta = {}       # employee_id -> {"label": int, "name": str}
_label_to_employee = {}   # label -> employee_id
_next_label = 1

# registered_id (NOT offset) -> name, populated by load_registered_faces().
# Kept separate from face training so a lookup still works even for a
# worker whose enrollment photo failed face detection (name/ID are
# still valid registry data regardless of whether their photo was
# usable for matching).
_worker_names = {}

# For a worker's first FACE_MATCH_FAST_ATTEMPTS frames, try face
# matching on EVERY frame -- this is the window that matters most:
# MIN_CONFIRMATION_FRAMES (config.py) gates violation events open at
# frame 6, so matching fast here shrinks how often a worker is ever
# seen under their bare session ID at all, rather than relying on
# violations.migrate_open_event() to clean up after the fact. After
# that many failed attempts, back off to retrying only once every
# FACE_MATCH_RETRY_EVERY_N_FRAMES -- someone who hasn't matched by
# then probably isn't going to (bad angle, not enrolled, lighting),
# and there's no reason to keep paying full detection + embedding cost
# forever. Once matched, the session_to_permanent cache below makes
# this moot entirely (no further detection needed for that worker
# again).
FACE_MATCH_FAST_ATTEMPTS = 15
FACE_MATCH_RETRY_EVERY_N_FRAMES = 5

# Cosine similarity between two L2-normalized ArcFace embeddings --
# HIGHER means a more confident match (opposite of LBPH's distance).
# Starting point only -- see module docstring. Expect to tune this
# from the real numbers match_worker_face()'s diagnostic print shows.
#
# Too high -> real matches get missed (registered workers keep getting
#             fresh session IDs instead of their permanent one).
# Too low  -> two different people risk being matched to the same
#             registered identity, silently misattributing violations.
MATCH_SIMILARITY_THRESHOLD = 0.45

# InsightFace does its own face detection internally (RetinaFace-based)
# -- no separate Haar cascade file needed anymore. providers=CPU since
# this runs on a regular dev machine, not a GPU box. det_size controls
# the internal detection resolution.
#
# Dropped 640x640 -> 320x320 after real testing showed sustained lag:
# FACE_MATCH_FAST_ATTEMPTS runs a FULL InsightFace detection+embedding
# pass on every single frame for any not-yet-matched session ID (by
# design -- see that constant's comment, shrinking the duplicate-event
# window matters more than raw speed there), and a live log showed 15-
# 20+ consecutive "no face detected" attempts back to back multiple
# times in one run. That's real, repeated CPU cost on the SAME thread
# that also feeds the HLS stream and renders the local preview, so it's
# a plausible direct contributor to reported video lag -- unlike the
# stutter fixed earlier (clip encoding), which was isolated to the
# instant a violation opened, this cost is spread across ordinary
# frames. 320x320 was called out in this module's own prior comment as
# the fallback for exactly this situation. Trade-off to watch: lower
# detection resolution can miss a face that's small/far from the
# camera -- fine for a close-up webcam test, worth revisiting if a
# real site camera has workers farther away and match rate drops.
_face_app = None
_FACE_DETECTION_AVAILABLE = False

try:

    _face_app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    _face_app.prepare(ctx_id=0, det_size=(320, 320))
    _FACE_DETECTION_AVAILABLE = True

except Exception as e:

    # Mirrors the old Haar-cascade-missing behavior: degrade to "face
    # matching disabled" (every worker keeps their normal session ID)
    # instead of crashing the whole app on the first frame -- e.g. if
    # the model weights failed to download (no internet on first run)
    # or insightface/onnxruntime isn't installed yet.
    print(
        f"[FaceID] Warning: could not initialize InsightFace ({e}) -- "
        f"face matching is DISABLED for this run (every worker keeps "
        f"their normal session ID). Make sure `pip install insightface "
        f"onnxruntime` has been run and that this machine had internet "
        f"access the first time (to download the buffalo_l model)."
    )

_recognizer_ready = False  # True once at least one embedding has been loaded


def _get_embedding(bgr_image):
    """
    Find the largest face in a BGR image and return its 512-d
    ArcFace embedding (L2-normalized, via InsightFace's own
    `.normed_embedding`). Returns None if no face is found, the image
    is empty, or InsightFace itself failed to initialize.
    """

    if not _FACE_DETECTION_AVAILABLE:
        return None

    if bgr_image is None or bgr_image.size == 0:
        return None

    faces = _face_app.get(bgr_image)

    if not faces:
        return None

    # Largest detected face by bbox area -- most likely the actual
    # subject rather than a smaller false positive elsewhere in the
    # crop (same reasoning as the old Haar-cascade version).
    def _area(face):
        x1, y1, x2, y2 = face.bbox
        return (x2 - x1) * (y2 - y1)

    face = max(faces, key=_area)

    return face.normed_embedding


def has_detectable_face(bgr_image):
    """
    True if at least one face can be found in this image. Used by
    registration.py to validate EACH captured enrollment photo the
    moment it's taken, instead of only discovering a bad shot (glare,
    bad angle, out of frame) much later when live_detection.py starts
    up and load_registered_faces() finds nothing usable -- by which
    point the person has usually left and has to be tracked down to
    re-register.
    """

    return _get_embedding(bgr_image) is not None


def _load_label_cache():
    """
    Load the local employee_id <-> integer-label mapping from disk (see
    the module docstring). Call this once at startup, before any fetch
    attempt, so labels stay stable across restarts even if the backend
    happens to be unreachable on THIS particular startup.
    """

    global _employee_meta, _label_to_employee, _next_label, _worker_names

    if os.path.exists(_LABEL_CACHE_FILE):

        with open(_LABEL_CACHE_FILE, "r") as f:
            _employee_meta = json.load(f)

        _label_to_employee = {meta["label"]: emp_id for emp_id, meta in _employee_meta.items()}
        _worker_names = {meta["label"]: meta["name"] for meta in _employee_meta.values()}
        _next_label = (max(meta["label"] for meta in _employee_meta.values()) + 1) if _employee_meta else 1

    else:

        _employee_meta = {}
        _label_to_employee = {}
        _worker_names = {}
        _next_label = 1


def _save_label_cache():

    with open(_LABEL_CACHE_FILE, "w") as f:
        json.dump(_employee_meta, f, indent=2)


def _get_or_create_label(employee_id, name):
    """
    Returns the SAME label for the same employee_id every time
    (persisted to disk), assigning a fresh one only the first time
    this employee_id is ever seen.
    """

    global _next_label

    if employee_id in _employee_meta:

        _employee_meta[employee_id]["name"] = name  # keep name fresh if it changed on the backend
        label = _employee_meta[employee_id]["label"]

    else:

        label = _next_label
        _next_label += 1
        _employee_meta[employee_id] = {"label": label, "name": name}
        _label_to_employee[label] = employee_id

    _worker_names[label] = name
    _save_label_cache()

    return label


def fetch_reference_photos():
    """
    Pull the current worker roster + reference photos from the backend
    (GET REFERENCE_PHOTOS_URL -- see Mahani's contract in config.py's
    comment). Each usable photo is cached locally to _CACHE_FOLDER, so
    a temporary backend/network outage on a LATER startup can still
    fall back to the last known-good copies (see load_registered_faces()).

    Returns a list of (label, name, embedding) tuples for every worker
    whose reference photo had a detectable face, or None if the
    backend itself couldn't be reached at all (distinct from "reached
    it, but a specific photo failed" -- that's handled per-worker
    below and still returns a list, just possibly a shorter one).
    """

    try:

        response = requests.get(REFERENCE_PHOTOS_URL, timeout=10)
        response.raise_for_status()
        roster = response.json()

    except Exception as e:

        print(
            f"[FaceID] Could not reach backend for the worker roster "
            f"({e}) -- will fall back to locally cached reference "
            f"photos from the last successful fetch, if any."
        )

        return None

    entries = []

    for record in roster:

        employee_id = record.get("employee_id")
        name = record.get("name")
        photo_url = record.get("reference_photo_url")

        if not employee_id or not photo_url:
            print(f"[FaceID] Skipping malformed roster entry: {record}")
            continue

        label = _get_or_create_label(employee_id, name)

        full_url = BACKEND_BASE_URL + photo_url
        cache_path = os.path.join(_CACHE_FOLDER, f"{employee_id}.jpg")

        image = None

        try:

            img_response = requests.get(full_url, timeout=10)
            img_response.raise_for_status()
            image_bytes = img_response.content

            # Cache immediately, before even trying to decode/detect a
            # face -- so a bad decode still leaves a copy on disk for
            # a human to inspect, and so the NEXT startup has this to
            # fall back to even if this photo itself never worked.
            with open(cache_path, "wb") as f:
                f.write(image_bytes)

            image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)

        except Exception as e:

            print(
                f"[FaceID] Could not download reference photo for "
                f"{employee_id} ({name}): {e} -- trying local cache."
            )

            if os.path.exists(cache_path):
                image = cv2.imread(cache_path)

        if image is None:
            print(f"[FaceID] No usable reference photo for {employee_id} ({name}) -- won't be matched.")
            continue

        embedding = _get_embedding(image)

        if embedding is None:
            print(f"[FaceID] Warning: no face detected in reference photo for {employee_id} ({name}) -- skipped.")
            continue

        entries.append((label, name, embedding))

    return entries


def _load_cached_entries():
    """
    Fallback used only when fetch_reference_photos() couldn't reach
    the backend at all: rebuild training entries from whatever's
    already sitting in _CACHE_FOLDER from a previous successful fetch,
    keyed off the persisted label cache (_employee_meta) so labels
    still line up correctly.
    """

    entries = []

    for employee_id, meta in _employee_meta.items():

        cache_path = os.path.join(_CACHE_FOLDER, f"{employee_id}.jpg")

        if not os.path.exists(cache_path):
            continue

        image = cv2.imread(cache_path)

        if image is None:
            continue

        embedding = _get_embedding(image)

        if embedding is None:
            continue

        entries.append((meta["label"], meta["name"], embedding))

    return entries


# label -> list of embeddings (a list, not a single vector, so a
# future multi-photo-per-worker roster only needs a small change here
# -- match_worker_face() already checks every embedding for a label
# and keeps the best score).
_label_embeddings = {}


def load_registered_faces():
    """
    (Re)build the embedding table from the backend's current worker
    roster. Call this once at startup, and again any time you want to
    pick up newly-registered workers mid-deployment (restart
    live_detection.py, or call this again before the next frame).

    If the backend is unreachable, falls back to locally cached
    reference photos from the last successful fetch (see
    fetch_reference_photos()) instead of disabling face matching
    outright -- a live site shouldn't lose ReID just because the
    backend had a brief network hiccup at startup.
    """

    global _label_embeddings, _recognizer_ready

    _load_label_cache()

    entries = fetch_reference_photos()

    if entries is None:

        entries = _load_cached_entries()

        if entries:
            print(
                f"[FaceID] Backend unreachable this startup -- using "
                f"{len(entries)} cached reference photo(s) from a "
                f"previous run instead."
            )

    if not entries:
        print("[FaceID] No usable reference photos (backend unreachable and no local cache) -- face matching disabled for now.")
        _label_embeddings = {}
        _recognizer_ready = False
        return

    _label_embeddings = {}

    for label, name, embedding in entries:
        _label_embeddings.setdefault(label, []).append(embedding)

    _recognizer_ready = True

    unique_labels = sorted(_label_embeddings.keys())

    print(
        f"[FaceID] Loaded {len(entries)} reference embedding(s) across "
        f"{len(unique_labels)} worker(s): "
        f"{[_label_to_employee.get(l, l) for l in unique_labels]}"
    )


def get_registered_name(worker_id):
    """
    Return the registered name for a worker_id, or None if this isn't
    a permanent (offset) ID, or no name is on file for it.

    worker_id here is the OFFSET id used as the `workers` dict key
    (e.g. 100001) -- this un-offsets it before looking it up, so
    callers can pass whatever key they already have without doing
    that math themselves.
    """

    if worker_id < PERMANENT_ID_OFFSET:
        return None

    return _worker_names.get(worker_id - PERMANENT_ID_OFFSET)


def match_worker_face(bgr_crop):
    """
    Try to match a worker's cropped image against enrolled faces.

    Returns the registered (un-offset) worker_id on a confident match,
    otherwise None -- callers should fall back to the normal session
    ID when this returns None.
    """

    if not _recognizer_ready:
        return None

    embedding = _get_embedding(bgr_crop)

    if embedding is None:
        # Distinct from "similarity too low" below -- this means
        # InsightFace couldn't find a face in the crop AT ALL this
        # frame (bad angle, too far from camera, motion blur).
        print("[FaceID] No face detected in this worker's crop this frame -- will retry.")
        return None

    best_label = None
    best_similarity = -1.0  # cosine similarity ranges [-1, 1]

    for label, embeddings in _label_embeddings.items():

        for candidate in embeddings:

            # Both embeddings are already L2-normalized, so the dot
            # product IS the cosine similarity -- no extra division
            # needed.
            similarity = float(np.dot(embedding, candidate))

            if similarity > best_similarity:
                best_similarity = similarity
                best_label = label

    # TEMPORARY diagnostic: print every attempt's actual similarity,
    # not just whether it passed -- MATCH_SIMILARITY_THRESHOLD is a
    # starting guess (see module docstring), and this shows the REAL
    # numbers InsightFace produces under actual conditions (pose,
    # expression, lighting), so the threshold can be set from evidence
    # instead of another guess. Remove once it's been calibrated.
    # NOTE: higher similarity = more confident match (opposite of the
    # old LBPH distance convention).
    result = "MATCH" if best_similarity >= MATCH_SIMILARITY_THRESHOLD else "no match"
    print(
        f"[FaceID] Closest candidate: worker {best_label} at similarity "
        f"{best_similarity:.3f} (threshold {MATCH_SIMILARITY_THRESHOLD}) -- {result}"
    )

    if best_similarity >= MATCH_SIMILARITY_THRESHOLD:
        return best_label

    return None


# Once a session-scoped ID has been confidently face-matched to a
# permanent registered identity, remember that mapping here -- so
# every later frame reuses the same permanent ID immediately, instead
# of re-running face detection every frame and risking a "matched this
# frame, missed the next" flap. A real face detector will NOT find a
# face in 100% of frames for one continuously-present person (head
# turns, partial occlusion, motion blur, lighting), and without this
# cache, a single missed-detection frame would silently revert the
# worker back to a plain session ID -- opening a SECOND, duplicate
# violation event for what is really the same ongoing incident.
#
# Known simplification: this cache is never pruned, so it grows for
# the life of the running process. Fine for a single test/demo
# session (it resets on every restart); would need a decay/expiry
# policy for a long-running unattended deployment.
_session_to_permanent = {}

# How many times we've attempted (and failed) to match each still-
# unmatched session ID -- used to throttle retries to once every
# FACE_MATCH_RETRY_EVERY_N_FRAMES instead of every single frame.
_unmatched_attempts = {}


def remap_to_permanent_ids(workers, frame, offset):
    """
    For each tracked worker, resolve their PERMANENT identity and use
    it as the dict key instead of their session-scoped ID -- either
    from the cache (a session ID already matched earlier this run) or
    by attempting a fresh face match right now. See PERMANENT_ID_OFFSET
    in config.py for why the offset exists. Everything downstream (PPE
    assignment, violation events, evidence, duration) keys off whatever
    ID is in this dict, so remapping here, right after
    stabilize_worker_ids and before assign_ppe, is enough to make the
    whole rest of the pipeline treat this as the worker's permanent
    identity -- no other file needs to know this happened.

    If no registered faces are loaded (nobody enrolled yet), every
    worker just passes through under their normal session ID -- this
    function is then a harmless no-op.

    Guards against two different session-tracked people somehow both
    resolving to the SAME registered identity in one frame (a
    false-positive risk, not the normal case): only the first claimant
    is remapped; any other keeps their original session ID rather than
    silently overwriting the first worker's entry under one shared key.

    Returns (remapped, newly_closed) -- newly_closed is a list of
    (event, "abandoned") tuples, one for each time migrate_open_event()
    below found the target permanent identity already had its own open
    event and had to close the session ID's orphaned duplicate instead
    of merging (see that function's docstring). Almost always empty --
    only non-empty in the same rare "same person got tracked under two
    different session IDs before either matched a face" case. Callers
    should report these to the backend exactly like any other
    transition (see resolve_stale_events(), same return shape), so the
    backend's record for the orphaned session ID gets marked closed
    instead of silently left "open" forever from its point of view.
    """

    remapped = {}
    claimed_permanent_ids = set()
    newly_closed = []

    for worker_id, info in workers.items():

        permanent_id = _session_to_permanent.get(worker_id)

        if permanent_id is None:

            attempts = _unmatched_attempts.get(worker_id, 0)
            _unmatched_attempts[worker_id] = attempts + 1

            # Fast, every-frame attempts while this is a brand-new
            # worker (covers the MIN_CONFIRMATION_FRAMES window before
            # a violation event can even open) -- then back off to
            # every Nth frame once it's clear this isn't matching
            # quickly, to avoid paying full detection + embedding cost
            # forever for someone who may never match.
            should_attempt = (
                attempts < FACE_MATCH_FAST_ATTEMPTS
                or attempts % FACE_MATCH_RETRY_EVERY_N_FRAMES == 0
            )

            if should_attempt:

                x1, y1, x2, y2 = info["bbox"]

                # Pass the FULL person crop, not just a head-region
                # sub-crop -- InsightFace's own detector (RetinaFace-
                # based) is robust enough to find a face anywhere
                # within a larger image, unlike the old Haar cascade,
                # which needed a tight head-only crop and still
                # clipped chins/mouths on some tracker boxes. Letting
                # the model find the face itself removes that whole
                # class of bug.
                person_crop = frame[y1:y2, x1:x2]

                registered_id = match_worker_face(person_crop)

                if registered_id is not None:

                    permanent_id = offset + registered_id
                    _session_to_permanent[worker_id] = permanent_id
                    _unmatched_attempts.pop(worker_id, None)

                    # A violation event (and/or presence tracking) may
                    # already exist under the session ID if it took a
                    # few frames to get this first match -- migrate
                    # that state over now instead of leaving it behind
                    # as an orphaned, never-resolving duplicate.
                    migrate_presence(worker_id, permanent_id)
                    closed = migrate_open_event(worker_id, permanent_id)

                    if closed is not None:
                        newly_closed.append(closed)

                    # Report the match to the backend so it can
                    # auto-link this tracking ID to the real employee
                    # profile -- the same POST /workers/link-tracker
                    # an admin's manual button already calls, per
                    # Mahani's contract. worker_id here is the RAW
                    # session/ByteTrack ID (what the backend calls
                    # "tracked_worker_id"), NOT the offset-shifted
                    # permanent_id -- the backend has no concept of
                    # PERMANENT_ID_OFFSET. Queued on the background
                    # thread (backend_worker.py) so a slow/unreachable
                    # backend never stalls the video loop.
                    employee_id = _label_to_employee.get(registered_id)

                    if employee_id:
                        queue_link_tracker(worker_id, employee_id)

        if permanent_id is None:
            # No cached mapping and no match this frame -- stays under
            # their session ID. Face matching will simply be retried
            # again on the next frame (cheap: it's just a cache miss,
            # not an error).
            remapped[worker_id] = info
            continue

        if permanent_id in claimed_permanent_ids:

            print(
                f"[FaceID] Worker {worker_id} also resolved to permanent "
                f"identity {permanent_id}, but that identity was already "
                f"claimed this frame -- keeping session ID {worker_id} "
                f"instead of merging two different tracked people."
            )

            remapped[worker_id] = info
            continue

        claimed_permanent_ids.add(permanent_id)
        remapped[permanent_id] = info

    return remapped, newly_closed
