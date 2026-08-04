"""
registration.py

** NO LONGER USED BY live_detection.py. ** Worker registration now
lives entirely on the backend/UI side -- an admin registers a worker
there (employee_id, name, phone, company, role, site, shift, reference
photo), and face_id.py pulls that roster directly from the backend
(GET /workers/reference-photos/all) instead of reading a local
registry file built by this script. See face_id.py's docstring for the
current flow.

This file is kept around only as a standalone dev/testing utility --
useful if you want to capture a local test photo set without needing
the backend running -- but nothing in the live pipeline reads
worker_registry/registry.json anymore.

--- Original design notes below, for historical context ---

Worker enrollment -- the "register once before entering the site" step
from your mentor's feedback (the Aadhaar-card analogy): a worker stands
in front of a tablet/camera, their photo is taken, and they're assigned
a PERMANENT worker ID that persists across days, sessions, and
restarts -- unlike the ByteTrack/session IDs live_detection.py assigns
today, which reset to a fresh count every time the script runs.

Each worker is enrolled from MULTIPLE photos (varied angle/expression),
not just one -- a single photo gives face_id.py's LBPH recognizer too
little per-person variation to reliably tell 3+ different real people
apart, which showed up in testing as cross-identity mismatches once a
few people were enrolled. More training samples per person is the real
fix for that, not just adjusting the match threshold.

Usage:
    python registration.py                 -- enroll a new worker
    python registration.py remove <id>     -- remove a worker (registry
                                               entry + their photos)

Note: worker IDs are NEVER reused, even after removal -- see
load_registry()'s docstring for why. Removing worker 3 means the next
NEW enrollment still gets worker 4, not 3 again.
"""

import cv2
import json
import os
import sys
from datetime import datetime

from config import CAMERA_SOURCE, CAMERA_NAME, LOCATION
from face_id import has_detectable_face

REGISTRY_FOLDER = "worker_registry"
REGISTRY_FILE = os.path.join(REGISTRY_FOLDER, "registry.json")
WINDOW_NAME = "AeroInspect AI -- Worker Registration"

# How many photos to capture per worker. More samples = better LBPH
# discrimination between different enrolled people -- this is the
# actual fix for cross-identity confusion, not just threshold tuning.
PHOTOS_PER_WORKER = 5

os.makedirs(REGISTRY_FOLDER, exist_ok=True)


def load_registry():
    """
    Load the persistent registry, or start a fresh one on the very
    first-ever enrollment. next_id is tracked explicitly (not derived
    from len(workers)) so an ID is NEVER reused, even after a worker
    is removed via deregister_worker() below. This matters: if IDs
    were reused, a brand-new person enrolled as (the recycled) worker
    3 would inherit whatever violation_history, evidence photos, and
    repeat-offender status the PREVIOUS worker 3 had accumulated --
    silently misattributing someone else's record to them.
    """

    if not os.path.exists(REGISTRY_FILE):
        return {"next_id": 1, "workers": []}

    with open(REGISTRY_FILE, "r") as f:
        return json.load(f)


def save_registry(registry):

    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)


def find_by_name(registry, name):
    """
    Guard against accidentally re-enrolling the same person under a
    second, different permanent ID. This is a NAME match only, so it's
    a soft warning, not a hard block -- two different workers could
    legitimately share a name.
    """

    needle = name.strip().lower()

    return [
        w for w in registry["workers"]
        if w["name"].strip().lower() == needle
    ]


def capture_photo_set(num_photos=PHOTOS_PER_WORKER):
    """
    Open the camera once and capture multiple photos in one sitting --
    SPACE to capture each one, 'f' to finish early once at least one
    photo is captured, 'q' to cancel the whole registration. Returns a
    list of BGR frames (possibly shorter than num_photos if finished
    early), or an empty list if cancelled before capturing anything.
    """

    cap = cv2.VideoCapture(CAMERA_SOURCE)

    if not cap.isOpened():
        print("Error: Could not access camera.")
        return []

    captured_frames = []

    print(f"\nWe'll take up to {num_photos} photos -- vary your angle")
    print("slightly between each one (straight on, slight left/right turn,")
    print("chin up/down a little). More variety here = better recognition later.")
    print("SPACE: capture this photo   F: finish early   Q: cancel\n")

    try:

        while len(captured_frames) < num_photos:

            ret, frame = cap.read()

            if not ret:
                print("Error: Could not read from camera.")
                break

            display = frame.copy()

            cv2.putText(
                display,
                f"Photo {len(captured_frames) + 1}/{num_photos} -- "
                f"SPACE: capture   F: finish   Q: cancel",
                (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

            cv2.imshow(WINDOW_NAME, display)

            key = cv2.waitKey(1) & 0xFF

            if key == ord(" "):

                # Validate THIS shot immediately -- no face detectable
                # (glare, bad angle, out of frame, motion blur) means
                # it would silently train on nothing later. Reject it
                # here and let them retake the same slot, instead of
                # only finding out at live_detection.py startup.
                if not has_detectable_face(frame):

                    print(
                        "No face detected in that shot -- try again "
                        "(face the camera directly, check for glare on "
                        "glasses, make sure your face isn't cut off)."
                    )

                    # Visual cue too -- easy to miss the console print
                    # while watching the camera window, not the terminal.
                    rejected = frame.copy()

                    cv2.putText(
                        rejected,
                        "NO FACE DETECTED -- RETRY",
                        (20, 60),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 0, 255),
                        2
                    )

                    cv2.imshow(WINDOW_NAME, rejected)
                    cv2.waitKey(700)

                    continue

                captured_frames.append(frame.copy())

                print(f"Captured {len(captured_frames)}/{num_photos}.")

                if len(captured_frames) < num_photos:
                    print("Change your angle slightly for the next one...")

            elif key == ord("f"):

                if captured_frames:
                    print(f"Finishing early with {len(captured_frames)} photo(s).")
                    break

                print("Capture at least one photo before finishing.")

            elif key == ord("q"):

                print("Registration cancelled.")
                captured_frames = []
                break

    finally:

        cap.release()
        cv2.destroyAllWindows()

    return captured_frames


def register_worker():

    registry = load_registry()

    print("\n===== AeroInspect AI: Worker Registration =====\n")

    name = input("Enter worker's full name: ").strip()

    if not name:
        print("Name cannot be empty. Registration cancelled.")
        return

    existing = find_by_name(registry, name)

    if existing:

        existing_ids = [w["worker_id"] for w in existing]

        print(
            f"\nWarning: {len(existing)} worker(s) already registered "
            f"with this name (ID(s): {existing_ids}). If this is the SAME "
            f"person, cancel now (Ctrl+C) and use their existing ID "
            f"instead of creating a duplicate enrollment.\n"
        )

        proceed = input("Continue and register as a NEW worker anyway? (y/n): ").strip().lower()

        if proceed != "y":
            print("Registration cancelled.")
            return

    captured_frames = capture_photo_set()

    if not captured_frames:
        return

    worker_id = registry["next_id"]

    safe_name = "".join(c if c.isalnum() else "_" for c in name.lower())

    photo_paths = []

    for i, frame in enumerate(captured_frames, start=1):

        photo_filename = f"worker_{worker_id}_{safe_name}_{i}.jpg"
        photo_path = os.path.join(REGISTRY_FOLDER, photo_filename)

        cv2.imwrite(photo_path, frame)
        photo_paths.append(photo_path)

    record = {
        "worker_id": worker_id,
        "name": name,
        # Back-compat single-photo field (some older code paths may
        # expect one representative photo) -- always the first shot.
        "photo_path": photo_paths[0],
        # Full set used for LBPH training -- see face_id.py.
        "photo_paths": photo_paths,
        "registered_at": datetime.now().isoformat(),
        "site": LOCATION,
        "camera_name": CAMERA_NAME
    }

    registry["workers"].append(record)
    registry["next_id"] = worker_id + 1

    save_registry(registry)

    print("\nRegistered successfully.")
    print(f"Worker ID    : {worker_id}")
    print(f"Name         : {name}")
    print(f"Photos saved : {len(photo_paths)} ({', '.join(photo_paths)})")
    print(f"Registry     : {REGISTRY_FILE}")
    print(
        "\nRestart live_detection.py (or it'll pick this up next time it "
        "starts) to have this worker recognized by face during monitoring."
    )


def deregister_worker(worker_id, delete_photos=True):
    """
    Remove a worker's registry entry (and, by default, their enrollment
    photos from disk) -- the supported way to undo a registration,
    instead of manually deleting the photo file and leaving a dangling
    entry in registry.json (which is what caused the "registered photo
    missing" warning on startup).

    Does NOT free up worker_id for reuse -- see load_registry()'s
    docstring for why IDs are never recycled. The next new enrollment
    still gets the next never-used number.
    """

    registry = load_registry()

    match = next((w for w in registry["workers"] if w["worker_id"] == worker_id), None)

    if match is None:
        print(f"No registered worker with ID {worker_id} found -- nothing to remove.")
        return

    registry["workers"] = [w for w in registry["workers"] if w["worker_id"] != worker_id]
    save_registry(registry)

    if delete_photos:

        paths = match.get("photo_paths") or [match.get("photo_path")]

        for path in paths:

            if path and os.path.exists(path):

                os.remove(path)

                print(f"Deleted photo: {path}")

    print(f"Removed worker {worker_id} ({match['name']}) from the registry.")
    print(
        f"Note: worker ID {worker_id} will NOT be reused -- the next new "
        f"enrollment will get worker {registry['next_id']}."
    )


if __name__ == "__main__":

    if len(sys.argv) >= 3 and sys.argv[1] == "remove":

        try:
            target_id = int(sys.argv[2])
        except ValueError:
            print(f"'{sys.argv[2]}' isn't a valid worker ID.")
            sys.exit(1)

        deregister_worker(target_id)

    else:

        register_worker()
