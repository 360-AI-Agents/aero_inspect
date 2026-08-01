"""
roi.py

Region-of-Interest (ROI) and digital zoom support.

Why this exists:
Right now the camera monitors its entire field of view. On a real
site (and especially with wide CCTV or drone shots), the actual work
platform is often a small fraction of the frame -- the rest is sky,
walls, walkways, or other zones you don't want counted. This module
lets you:

  1. Define a monitoring zone (ROI) and ignore workers outside it.
  2. Draw that zone on screen so it's obvious what's being watched.
  3. Produce a digitally zoomed picture-in-picture inset of the zone,
     so small/distant workers are easier for a human operator to see
     -- without the cost of running a second YOLO pass.

This is deliberately NOT "zoomed re-detection" (cropping the ROI and
running the model on it again for higher accuracy on tiny, distant
workers). That's a heavier future optimization -- worth doing once
this is running on real wide-angle CCTV/drone footage where small
workers are actually being missed by the model. For a single nearby
webcam, the ROI + visual zoom below is the useful, cheap version.
"""

import cv2


def normalized_to_pixels(roi_normalized, frame_shape):
    """
    Convert a normalized ROI (x1, y1, x2, y2 as fractions of frame
    width/height, each 0.0-1.0) into pixel coordinates for the
    current frame size. Normalized coordinates are what let one ROI
    definition keep working no matter what resolution the camera
    feed actually is.
    """

    h, w = frame_shape[:2]
    nx1, ny1, nx2, ny2 = roi_normalized

    return (
        int(nx1 * w),
        int(ny1 * h),
        int(nx2 * w),
        int(ny2 * h)
    )


def draw_roi_overlay(frame, roi_pixels, label="Monitoring Zone"):
    """
    Draw the ROI rectangle and a label directly onto the frame so
    it's visually obvious what area is being monitored.
    """

    x1, y1, x2, y2 = roi_pixels

    # OpenCV colors are BGR, not RGB -- (0, 165, 255) is orange.
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 165, 255), 2)

    cv2.putText(
        frame,
        label,
        (x1, max(20, y1 - 10)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 165, 255),
        2
    )

    return frame


def is_inside_roi(bbox, roi_pixels):
    """
    True if a worker's box center falls inside the ROI.
    Using the center (not requiring the full box inside) means a
    worker standing at the edge of the zone, partially overlapping
    its boundary, is still counted -- only workers who are clearly
    elsewhere are excluded.
    """

    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2

    rx1, ry1, rx2, ry2 = roi_pixels

    return rx1 <= cx <= rx2 and ry1 <= cy <= ry2


def filter_workers_by_roi(workers, roi_pixels):
    """
    Keep only workers whose center falls inside the ROI -- e.g. so a
    person walking past in the background isn't scored for PPE
    compliance on the actual work platform.
    """

    return {
        worker_id: worker
        for worker_id, worker in workers.items()
        if is_inside_roi(worker["bbox"], roi_pixels)
    }


def get_zoomed_inset(frame, roi_pixels, zoom_factor=2.0, inset_width=260, max_height_ratio=0.6):
    """
    Produce a digitally zoomed crop of the ROI, sized for use as a
    picture-in-picture inset. zoom_factor > 1.0 magnifies the ROI's
    content relative to its footprint in the full frame.

    max_height_ratio caps the inset's height at that fraction of the
    frame's height. Without this cap, a tall/narrow ROI combined with
    a high zoom_factor can compute an inset taller than the frame
    itself -- which would then get silently rejected by
    overlay_inset() (it refuses to paste something that doesn't fit),
    making the zoom feature look "broken" when really it was just an
    oversized image quietly failing to be drawn. Here we shrink both
    dimensions together (preserving aspect ratio) so it always fits.
    """

    x1, y1, x2, y2 = roi_pixels

    crop = frame[y1:y2, x1:x2]

    if crop.size == 0:
        return None

    crop_h, crop_w = crop.shape[:2]

    if crop_w == 0 or crop_h == 0:
        return None

    scale = (inset_width / crop_w) * zoom_factor
    inset_h = max(1, int(crop_h * scale))

    frame_h = frame.shape[0]
    max_height = max(1, int(frame_h * max_height_ratio))

    if inset_h > max_height:
        shrink = max_height / inset_h
        inset_h = max_height
        inset_width = max(1, int(inset_width * shrink))

    zoomed = cv2.resize(
        crop,
        (inset_width, inset_h),
        interpolation=cv2.INTER_CUBIC
    )

    return zoomed


def overlay_inset(frame, inset, margin=10):
    """
    Paste the zoomed inset into the top-right corner of the frame,
    with a border so it's visually distinct from the main feed.
    """

    if inset is None:
        return frame

    h, w = frame.shape[:2]
    ih, iw = inset.shape[:2]

    if ih + margin * 2 > h or iw + margin * 2 > w:
        print(
            f"[Zoom] inset ({iw}x{ih}) doesn't fit in frame "
            f"({w}x{h}) -- skipping this frame. Lower ZOOM_FACTOR "
            f"or max_height_ratio in config.py."
        )
        return frame  # inset too big for this frame -- skip rather than crash

    x_offset = w - iw - margin
    y_offset = margin

    # Deliberately NOT the same orange as the ROI rectangle -- when
    # both are on screen at once they'd be visually indistinguishable
    # (that's exactly what made an earlier screenshot confusing).
    cv2.rectangle(
        frame,
        (x_offset - 3, y_offset - 3),
        (x_offset + iw + 3, y_offset + ih + 3),
        (0, 255, 0),
        2
    )

    frame[y_offset:y_offset + ih, x_offset:x_offset + iw] = inset

    return frame
