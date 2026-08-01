"""
evidence.py

Save cropped, annotated evidence images for workers with safety
violations. Each saved image is self-documenting: it carries the
worker ID, camera name, timestamp and violation list burned into
the pixels, so the file is still meaningful if it's ever viewed
outside the app (e.g. attached to an incident report).
"""

import cv2
import os
import numpy as np
from datetime import datetime

from config import CAMERA_NAME

# Folder where violation images will be stored
SAVE_FOLDER = "violations"

os.makedirs(SAVE_FOLDER, exist_ok=True)

HEADER_LINE_HEIGHT = 22
HEADER_PADDING = 10


def save_violation_image(frame, worker_id, bbox, violations, camera_name=CAMERA_NAME):
    """
    Save a cropped image of the violating worker with a red border
    and a text header (worker ID, camera, timestamp, violations).

    Args:
        frame: Current video frame
        worker_id: ByteTrack worker ID
        bbox: (x1, y1, x2, y2)
        violations: list of violation strings, e.g. ["Helmet Missing"]
        camera_name: which camera captured this frame

    Returns:
        Path of saved image, or None if the crop was empty.
    """

    x1, y1, x2, y2 = bbox

    # Make sure coordinates are within image boundaries
    height, width = frame.shape[:2]

    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(width, x2)
    y2 = min(height, y2)

    if x2 <= x1 or y2 <= y1:
        return None

    # Crop only the worker (copy so we don't draw on the live frame)
    crop = frame[y1:y2, x1:x2].copy()

    if crop.size == 0:
        return None

    # Red border around the whole crop -- visually flags "violation"
    cv2.rectangle(
        crop,
        (0, 0),
        (crop.shape[1] - 1, crop.shape[0] - 1),
        (0, 0, 255),
        3
    )

    now = datetime.now()
    timestamp_display = now.strftime("%Y-%m-%d %H:%M:%S")
    timestamp_file = now.strftime("%Y%m%d_%H%M%S")

    header_lines = [
        f"Worker ID: {worker_id}",
        f"Camera: {camera_name}",
        f"Time: {timestamp_display}",
        f"Violations: {', '.join(violations) if violations else 'None'}"
    ]

    header_height = HEADER_LINE_HEIGHT * len(header_lines) + HEADER_PADDING

    annotated = np.zeros(
        (crop.shape[0] + header_height, crop.shape[1], 3),
        dtype=np.uint8
    )

    annotated[header_height:, :] = crop

    for i, line in enumerate(header_lines):

        cv2.putText(
            annotated,
            line,
            (5, 20 + i * HEADER_LINE_HEIGHT),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1,
            cv2.LINE_AA
        )

    filename = f"worker_{worker_id}_{timestamp_file}.jpg"

    filepath = os.path.join(SAVE_FOLDER, filename)

    cv2.imwrite(filepath, annotated)

    return filepath