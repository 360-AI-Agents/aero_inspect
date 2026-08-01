# Revised Architecture

## Overview

The AeroInspect AI architecture has been redesigned from an image upload-based workflow to a real-time visual inspection platform for construction site safety monitoring.

Instead of relying on manually uploaded images, the system continuously processes live video streams from CCTV cameras, IP cameras, webcams, or recorded construction videos. The AI model performs real-time object detection and safety analysis, while the backend stores inspection data and provides dashboards, analytics, alerts, and reports.

---

## System Architecture


          CCTV / IP Camera / Webcam / Recorded Video
                           │
                           ▼
                OpenCV Video Stream Processing
                           │
                           ▼
             YOLOv8 Visual Inspection Engine
        ┌──────────────────────────────────────┐
        │ Detect Construction Objects          │
        │ • Workers                            │
        │ • Safety Helmets                     │
        │ • Safety Vests                       │
        │ • Machinery & Equipment              │
        │ • Construction Materials             │
        └──────────────────────────────────────┘
                           │
                           ▼
                 Safety Intelligence Engine
        ┌──────────────────────────────────────┐
        │ • Worker Count                       │
        │ • PPE Compliance                     │
        │ • Helmet Violations                  │
        │ • Vest Violations                    │
        │ • Safety Compliance Score            │
        └──────────────────────────────────────┘
                           │
                           ▼
                  FastAPI Backend Services
                           │
                           ▼
              SQLite / PostgreSQL Database
                           │
                           ▼
       Dashboard • Alerts • Reports • Analytics

-----------------------------------------------------------------------------------

## Workflow

1. Capture live video from a CCTV camera, webcam, IP camera, or recorded video.
2. Process every frame using the YOLOv8 object detection model.
3. Detect construction workers, PPE, machinery, and other supported objects.
4. Analyze detections using the safety rule engine.
5. Generate worker counts, PPE violations, and compliance scores.
6. Send structured inspection results to the FastAPI backend.
7. Store inspection records in the database.
8. Display live analytics, inspection history, alerts, and reports through the dashboard.

--------------------------------------------------------------------------------------

# Revised 4-Week Development Plan

## Week 1 – Real-Time Visual Inspection Pipeline

### Objective
Build the core real-time computer vision pipeline.

### Tasks
- Set up live video input using OpenCV.
- Train and optimize the YOLOv8 object detection model.
- Detect construction entities including:
  - Workers
  - Safety Helmets
  - Safety Vests
  - Machinery & Equipment
  - Construction Materials (where supported)
- Display real-time bounding boxes, labels, and confidence scores.
- Validate detection performance using construction site videos.

### Deliverable
A real-time visual inspection pipeline capable of detecting multiple construction site objects.

---

## Week 2 – AI Intelligence & Backend Integration

### Objective
Convert detections into actionable safety insights and integrate them with the backend.

### Tasks
- Convert YOLO detections into structured JSON.
- Implement the Safety Intelligence Engine.
- Calculate:
  - Worker Count
  - PPE Compliance
  - Helmet Violations
  - Vest Violations
  - Safety Compliance Score
- Integrate YOLO with the FastAPI backend.
- Store inspection records automatically in the database.

### Deliverable
A working AI pipeline integrated with the backend and database.

---

## Week 3 – Dashboard & End-to-End Integration

### Objective
Complete the AeroInspect AI workflow.

### Tasks
- Develop the dashboard displaying:
  - Live Worker Count
  - PPE Compliance
  - Safety Violations
  - Inspection History
  - Safety Analytics
- Optimize AI inference performance.
- Perform complete end-to-end integration:
  - Live Video
  - YOLO Detection
  - Safety Intelligence Engine
  - Backend
  - Database
  - Dashboard

### Deliverable
A complete AI-powered visual inspection platform.

---

## Week 4 – Testing & Final Demonstration

### Objective
Validate and finalize the MVP.

### Tasks
- End-to-end testing.
- Improve detection accuracy.
- Test using multiple construction site videos.
- Fix bugs and optimize performance.
- Prepare documentation and final demo.

### Deliverable
A working MVP capable of real-time construction site monitoring, automatic inspection recording, and live safety analytics.

--------------------------------------------------------------------------------------------------------------------

# Future Enhancements

- Edge deployment using Raspberry Pi or NVIDIA Jetson for low-latency inference.
- Cloud deployment using AWS for scalable processing and centralized monitoring.
- Multi-camera support for monitoring multiple construction zones.
- Real-time alerts for PPE violations and unsafe conditions.
- Automated inspection report generation.
- Construction progress tracking and site analytics.
- Worker tracking and zone-based safety monitoring.
- Historical trend analysis and compliance reporting.
- Integration with mobile applications for field supervisors.
- AI-powered predictive safety analytics and risk assessment.
