"""
tracker.py

Handles YOLO object tracking.
"""

from ultralytics import YOLO

from config import CONFIDENCE, NMS_IOU_THRESHOLD


def track_objects(model, frame):
    """
    Run YOLO tracking on a frame.
    """

    results = model.track(
        frame,
        persist=True,
        tracker="bytetrack.yaml",
        conf=CONFIDENCE,
        iou=NMS_IOU_THRESHOLD,
        verbose=False
    )

    return results