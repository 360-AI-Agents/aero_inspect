"""
worker_manager.py

Maps PPE detections to individual workers
and calculates worker-wise violations.
"""

from config import PERSON_MIN_CONFIDENCE


def get_workers(results):
    """
    Create one worker for every detected Person that clears the
    stricter PERSON_MIN_CONFIDENCE bar (see config.py) -- this is
    separate from the general CONFIDENCE threshold already applied
    in model.track(), and exists to reject weak "person" hits on
    background clutter before they ever become a tracked worker.
    """

    workers = {}

    boxes = results[0].boxes
    names = results[0].names

    for box in boxes:

        cls = int(box.cls[0])
        label = names[cls]

        if label != "Person":
            continue

        if box.id is None:
            continue

        confidence = float(box.conf[0]) if box.conf is not None else 0.0

        if confidence < PERSON_MIN_CONFIDENCE:
            continue

        worker_id = int(box.id.item())

        x1, y1, x2, y2 = map(int, box.xyxy[0])

        workers[worker_id] = {
            "bbox": (x1, y1, x2, y2),
            "confidence": confidence,
            "helmet": False,
            "vest": False,
            "mask": False,
            "violations": []
        }

    return workers


# =====================================================
# Helper Functions
# =====================================================

def get_center(box):

    x1, y1, x2, y2 = box

    return (
        (x1 + x2) / 2,
        (y1 + y2) / 2
    )


def distance(box1, box2):

    x1, y1 = get_center(box1)

    x2, y2 = get_center(box2)

    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5


def box_area(box):

    x1, y1, x2, y2 = box

    return max(0, x2 - x1) * max(0, y2 - y1)


def point_in_box(px, py, box):

    x1, y1, x2, y2 = box

    return x1 <= px <= x2 and y1 <= py <= y2


def calculate_iou(boxA, boxB):

    ax1, ay1, ax2, ay2 = boxA
    bx1, by1, bx2, by2 = boxB

    xA = max(ax1, bx1)
    yA = max(ay1, by1)
    xB = min(ax2, bx2)
    yB = min(ay2, by2)

    inter = max(0, xB - xA) * max(0, yB - yA)

    areaA = (ax2 - ax1) * (ay2 - ay1)
    areaB = (bx2 - bx1) * (by2 - by1)

    union = areaA + areaB - inter

    if union == 0:
        return 0

    return inter / union


# =====================================================
# Duplicate Worker Filtering
#
# ByteTrack occasionally spawns a fresh ID for a person who
# was only briefly occluded, so the same physical worker shows
# up twice in one frame with two different IDs. We can't fix
# the tracker's ID-switching from here, but within a single
# frame we CAN detect "two boxes that are almost certainly the
# same person" -- their IoU will be very high -- and collapse
# them to one. We keep the lower (older/first-seen) ID, since
# it is more likely to be the track that has accumulated real
# presence/violation-event history already.
#
# Kept in sync with NMS_IOU_THRESHOLD in config.py -- this is a
# backstop for anything that slips past YOLO's own NMS, so both
# should move together. See config.py for why this was lowered
# from 0.45 to 0.35.
# =====================================================

DUPLICATE_IOU_THRESHOLD = 0.35


def deduplicate_workers(workers):
    """
    Merge worker boxes that overlap heavily enough (IoU above
    DUPLICATE_IOU_THRESHOLD) to almost certainly be the same
    physical person tracked under two IDs.
    """

    ids = list(workers.keys())
    to_remove = set()

    for i in range(len(ids)):

        for j in range(i + 1, len(ids)):

            id_i, id_j = ids[i], ids[j]

            if id_i in to_remove or id_j in to_remove:
                continue

            iou = calculate_iou(
                workers[id_i]["bbox"],
                workers[id_j]["bbox"]
            )

            if iou > DUPLICATE_IOU_THRESHOLD:

                # Keep the lower ID (first seen), drop the newer duplicate
                keep_id, drop_id = (id_i, id_j) if id_i < id_j else (id_j, id_i)
                to_remove.add(drop_id)

    for worker_id in to_remove:
        del workers[worker_id]

    return workers


# =====================================================
# Cross-Frame ID Continuity ("Track Stitching")
#
# This runs AFTER dedup/filtering but BEFORE PPE assignment, so
# that a worker who gets a new ByteTrack ID mid-scene keeps their
# original canonical ID -- which means their violation event stays
# one continuous record (one evidence photo, one start time) instead
# of fragmenting into worker_3, worker_79, worker_92...
# =====================================================

def stabilize_worker_ids(
    workers,
    last_known_positions,
    current_time,
    max_gap_seconds,
    iou_threshold,
    max_center_distance
):
    """
    Re-map brand-new ByteTrack IDs back onto a recently-vanished
    canonical ID -- either because their box overlaps the old one
    (Pass 1: IoU), or because it doesn't overlap but landed nearby
    (Pass 2: center-distance fallback). The distance fallback matters
    because a worker who stepped back/forward or moved around near
    the camera during the gap won't have a box that overlaps their
    old position at all, even though it's obviously the same person.

    This is deliberately simple (spatial continuity, not appearance
    matching) -- it only works within max_gap_seconds and only if the
    person hasn't wandered further than max_center_distance. True
    re-identification (face/appearance embeddings) is future work.
    """

    raw_ids = list(workers.keys())

    stabilized = {}
    claimed_canonical_ids = set()

    def is_candidate(existing_id, info):
        if existing_id in claimed_canonical_ids:
            return False
        if existing_id in raw_ids:
            # That canonical ID is still active this frame under its
            # own number -- not a candidate.
            return False
        gap = current_time - info["last_seen"]
        return gap <= max_gap_seconds

    for raw_id in raw_ids:

        worker = workers[raw_id]

        if raw_id in last_known_positions:

            # ByteTrack kept the same ID this time -- nothing to stitch
            canonical_id = raw_id

        else:

            canonical_id = None

            # ---- Pass 1: box overlap with a recently-vanished worker ----
            best_iou = iou_threshold

            for existing_id, info in last_known_positions.items():

                if not is_candidate(existing_id, info):
                    continue

                iou = calculate_iou(info["bbox"], worker["bbox"])

                if iou > best_iou:
                    best_iou = iou
                    canonical_id = existing_id

            # ---- Pass 2: no overlap, but landed nearby ----
            if canonical_id is None:

                best_distance = max_center_distance

                for existing_id, info in last_known_positions.items():

                    if not is_candidate(existing_id, info):
                        continue

                    d = distance(info["bbox"], worker["bbox"])

                    if d < best_distance:
                        best_distance = d
                        canonical_id = existing_id

            if canonical_id is None:
                canonical_id = raw_id  # genuinely a new worker

        stabilized[canonical_id] = worker
        claimed_canonical_ids.add(canonical_id)

        last_known_positions[canonical_id] = {
            "bbox": worker["bbox"],
            "last_seen": current_time
        }

    # Prune canonical IDs that have been missing too long -- otherwise
    # this dict grows forever over a long-running camera process.
    stale_ids = [
        worker_id for worker_id, info in last_known_positions.items()
        if worker_id not in stabilized
        and (current_time - info["last_seen"]) > max_gap_seconds
    ]

    for worker_id in stale_ids:
        del last_known_positions[worker_id]

    return stabilized


# =====================================================
# Worker Bounding Box Sanity Filter
#
# Occasionally YOLO/ByteTrack outputs a "person" box that is
# far too large -- e.g. it merges two overlapping people into
# one box, or clips a huge chunk of background. Feeding that box
# into PPE assignment poisons the region-containment logic in
# assign_ppe(), since "head region" and "torso region" no longer
# line up with an actual head/torso. We reject boxes that are
# implausible relative to the frame or to a typical person's
# aspect ratio.
# =====================================================

MAX_BOX_AREA_RATIO = 0.85   # a person box shouldn't cover the whole frame
MIN_ASPECT_RATIO = 0.15     # width / height -- too wide is suspicious
MAX_ASPECT_RATIO = 1.8      # width / height -- too tall/thin is suspicious


def filter_worker_boxes(workers, frame_shape):
    """
    Drop worker boxes that are implausible in size or shape.
    frame_shape is the (height, width, channels) tuple from frame.shape.
    """

    frame_h, frame_w = frame_shape[0], frame_shape[1]
    frame_area = frame_h * frame_w

    valid_workers = {}

    for worker_id, worker in workers.items():

        x1, y1, x2, y2 = worker["bbox"]
        w = x2 - x1
        h = y2 - y1

        if w <= 0 or h <= 0:
            continue

        area_ratio = (w * h) / frame_area

        if area_ratio > MAX_BOX_AREA_RATIO:
            continue

        aspect_ratio = w / h

        if aspect_ratio < MIN_ASPECT_RATIO or aspect_ratio > MAX_ASPECT_RATIO:
            continue

        valid_workers[worker_id] = worker

    return valid_workers


# =====================================================
# PPE classes are physically anchored to a body region.
# Helmets/masks only ever appear near the head; vests
# only ever appear on the torso. Restricting the search
# to that region is what stops a helmet detected on the
# person behind from being handed to the person in front.
# =====================================================

HEAD_LABELS = {"Hardhat", "NO-Hardhat", "Mask", "NO-Mask"}
TORSO_LABELS = {"Safety Vest", "NO-Safety Vest"}

# Fraction of the worker box height that counts as "head"
HEAD_REGION_RATIO = 0.4

# Torso region: skip the very top (head) and very bottom (legs)
TORSO_REGION_TOP_RATIO = 0.2
TORSO_REGION_BOTTOM_RATIO = 0.85


def region_for_label(label):

    if label in HEAD_LABELS:
        return "head"

    if label in TORSO_LABELS:
        return "torso"

    return None


def get_region_box(worker_box, region):
    """
    Shrink a worker's full bounding box down to the sub-region
    (head or torso) that a given PPE class can legally occupy.
    """

    x1, y1, x2, y2 = worker_box
    h = y2 - y1

    if region == "head":
        return (x1, y1, x2, y1 + int(h * HEAD_REGION_RATIO))

    if region == "torso":
        return (
            x1,
            y1 + int(h * TORSO_REGION_TOP_RATIO),
            x2,
            y1 + int(h * TORSO_REGION_BOTTOM_RATIO)
        )

    return worker_box


# =====================================================
# Assign PPE to the Correct Worker
# =====================================================

# If no worker's region contains the PPE box center, we fall
# back to nearest-center matching -- but only within this many
# pixels of "slack", otherwise stray detections attach to the
# nearest worker even when that worker is far away.
MAX_FALLBACK_DISTANCE = 250


def assign_ppe(results, workers):
    """
    Assign every PPE detection to the worker whose body region
    (head or torso) actually contains it.

    Why not nearest-center (the old approach)?
    Nearest-center always finds *a* worker, even when two people
    overlap in the frame -- so a helmet worn by the person in
    back can get handed to the person standing in front simply
    because their box centers are closer. Containment within the
    correct anatomical region removes that failure mode. If two
    workers' regions both contain the object (heavy overlap), we
    keep the smallest-area candidate, since a smaller box in an
    overlapping pair is almost always the nearer/foreground person.
    """

    boxes = results[0].boxes
    names = results[0].names

    for box in boxes:

        cls = int(box.cls[0])
        label = names[cls]

        # Skip Person detections
        if label == "Person":
            continue

        ox1, oy1, ox2, oy2 = map(int, box.xyxy[0])

        object_box = (ox1, oy1, ox2, oy2)
        cx, cy = get_center(object_box)

        region = region_for_label(label)

        # ---- Pass 1: containment within the correct body region ----
        candidates = []

        for worker_id, worker in workers.items():

            region_box = get_region_box(worker["bbox"], region) if region else worker["bbox"]

            if point_in_box(cx, cy, region_box):
                candidates.append((worker_id, worker))

        chosen = None

        if candidates:

            chosen = min(
                candidates,
                key=lambda kv: box_area(kv[1]["bbox"])
            )[1]

        else:

            # ---- Pass 2: distance fallback, capped by a max radius ----
            nearest_worker = None
            nearest_distance = float("inf")

            for worker in workers.values():

                d = distance(worker["bbox"], object_box)

                if d < nearest_distance:
                    nearest_distance = d
                    nearest_worker = worker

            if nearest_worker is not None and nearest_distance <= MAX_FALLBACK_DISTANCE:
                chosen = nearest_worker

        if chosen is None:
            continue

        if label == "Hardhat":
            chosen["helmet"] = True

        elif label == "Safety Vest":
            chosen["vest"] = True

        elif label == "Mask":
            chosen["mask"] = True

    return workers


# =====================================================
# Worker-wise Violations
# =====================================================

def calculate_worker_violations(workers):
    """
    Calculate violations for every worker.
    """

    for worker in workers.values():

        worker["violations"] = []

        if not worker["helmet"]:
            worker["violations"].append("Helmet Missing")

        if not worker["vest"]:
            worker["violations"].append("Safety Vest Missing")

        if not worker["mask"]:
            worker["violations"].append("Mask Missing")

    return workers
