# AeroInspect AI

AeroInspect AI is a construction-site safety monitoring system that watches a live camera feed, detects workers and their PPE (helmet, safety vest, mask) in real time, tracks violations as they start and resolve, identifies *who* is in violation against a registered worker roster, and reports everything — including evidence photos, short video clips, and a live stream — to a backend dashboard.

This repository is the **AI module**: detection, tracking, worker identity, violation logic, and everything that talks to the backend. The backend and dashboard are owned separately (see `backend/`, `frontend/` — currently placeholders in this repo, actively developed in the team's backend repo) and consumed here only through the API contract described below.

## Team

- Jatavath Ajay — AI module (this repository)
- Mahani Kunche — Backend & dashboard

## What it does

- **Detects workers and PPE** every frame using a custom-trained YOLOv8 model (`best.pt`), tracked across frames with a tuned ByteTrack config (`bytetrack_custom.yaml`) so each worker keeps a stable ID as they move.
- **Scores compliance** per worker (helmet / vest / mask present or missing) and restricts monitoring to a configurable Region of Interest, with an optional digital zoom inset for small/distant workers.
- **Recognizes individual workers** by face (InsightFace / ArcFace embeddings) against a roster and reference photos pulled from the backend, and automatically links a tracking session to the correct employee record — no local registration step; the backend/UI owns enrollment.
- **Tracks violations as real incidents, not frame counts.** A violation opens exactly one event, stays open while it continues, and resolves or is marked abandoned when the worker leaves — with one evidence photo and one short pre-roll video clip captured per incident, not per frame.
- **Streams live video** to the dashboard via an ffmpeg-driven HLS relay, decoupled from the full-resolution frames YOLO analyzes, so the live view never affects detection performance.
- **Reports everything to the backend** (detection events, evidence photos, violation clips, stream segments, worker-identity links) through a background job queue, so a slow or temporarily unreachable backend never blocks or stutters the video feed — failed sends retry automatically.

## How it fits together

```
Camera (cv2.VideoCapture)
   │
   ├─► YOLOv8 + ByteTrack ──► PPE assignment ──► ROI filter ──► Face ID match
   │                                                                  │
   │                                                    permanent worker identity
   │                                                                  │
   │                                              violation event lifecycle (open/update/resolve)
   │                                                                  │
   ├─► ffmpeg HLS relay ──► background uploader ──┐                  │
   ├─► violation clip buffer ──► background encoder ─┤                  │
   └─────────────────────────────────────────────────┴─► background job queue ──► backend API
```

## Setup

1. **Python environment**
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **ffmpeg** (required for live streaming — detection itself works without it)
   Install a static build, add its `bin/` folder to your PATH, then open a **new** terminal and confirm with `ffmpeg -version`. If ffmpeg isn't found, live streaming disables itself automatically and prints a warning; detection, violations, and backend reporting are unaffected.

3. **Model weights** — `best.pt` is included in this repo.

4. **Configure `config.py`** — at minimum:
   - `CAMERA_SOURCE` — webcam index or RTSP URL
   - `BACKEND_BASE_URL` — the backend's current LAN address (this changes whenever the backend machine's IP changes — keep this in sync with whoever's running the backend)
   - `ROI` — the monitored zone, as a fraction of frame size

5. **Run it:**
   ```
   python live_detection.py
   ```
   Press `q` to quit, `r` to toggle ROI filtering, `z` to toggle the zoom inset.

## Repository layout

| File | Purpose |
|---|---|
| `live_detection.py` | Main loop — camera capture, detection, drawing, orchestrates everything below |
| `config.py` | All tunable settings, each documented with the evidence behind its current value |
| `detector.py` | YOLOv8 model loading and inference |
| `worker_manager.py` | Assigns PPE detections to worker boxes, tracks per-worker violation state |
| `roi.py` | Region-of-interest filtering and digital zoom |
| `face_id.py` | Worker identity — fetches the roster from the backend, matches faces via InsightFace, auto-links tracking sessions to employees |
| `violations.py` | Violation event lifecycle (open → update → resolve/abandon), ID-continuity handling |
| `memory.py` | Worker presence tracking (first seen / last seen) |
| `evidence.py` | Evidence photo capture |
| `clip_recorder.py` | Pre-roll violation clip buffering and encoding |
| `streaming.py` | ffmpeg HLS relay and push-upload to the backend |
| `backend_client.py` | Builds and sends payloads (detections, evidence, clips, stream files, identity links) to the backend API |
| `backend_worker.py` | Background thread + job queue so backend I/O never blocks the video loop |
| `registration.py` | Deprecated — local worker enrollment, superseded by backend-driven registration. Kept as a standalone dev/testing utility only |

## Current status

**Working and validated through live testing:** person/PPE detection and tracking, ROI filtering, violation event lifecycle, worker identity matching and auto-linking, evidence photo and clip capture/upload, live HLS streaming end-to-end, background reporting with retry-on-failure.

**Known limitations, not yet resolved:**
- The detection model occasionally misclassifies fabric/clothing-textured background clutter (hanging jackets, fabric piles) as a person. Mitigated by a confidence floor and ROI filtering, but not eliminated — the real fix is retraining with hard-negative examples of this kind of clutter.
- Face matching needs a clear, front-facing frame to identify a worker; identity briefly lags behind detection while a worker is moving into frame, though PPE/violation tracking itself is unaffected.
- All testing so far has been on a single webcam in one room — validation against a real wide-angle site camera hasn't happened yet.
- Hourly checkpoint photos (a mentor-requested feature) are deferred, not yet built.
- Evidence photos and video clips are currently committed to this repo unencrypted; whether that's appropriate for a public repository is still an open decision, not yet finalized.

## Project background

See [Context.md](./Context.md) and [Plan.md](./Plan.md) / [REVISEDplan.md](./REVISEDplan.md) for the original problem statement, market research, and architecture planning that this module was built from, and [Skill.md](./Skill.md) for team roles and responsibilities.
