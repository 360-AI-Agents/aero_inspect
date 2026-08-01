# AeroInspect AI - Plan

## MVP Deliverables

### AI Features

* Helmet Detection
* Safety Vest Detection
* Construction Component Detection
* Basic Progress Tracking

### Platform Features

* Image & Video Upload
* Compliance Dashboard
* Inspection History
* Analytics & Reporting
* Alert System

### Deployment

* Dockerized Application
* AWS Hosted MVP

---

## System Architecture

Image/Video Upload

↓

YOLOv8 Detection Engine

↓

FastAPI Backend

↓

PostgreSQL Database

↓

Analytics & Reporting Layer

↓

React Dashboard

---

## Technology Stack & Purpose

### AI / Computer Vision Layer

**Technologies:** Python, PyTorch, YOLOv8, OpenCV

**Purpose:**

* Detect helmets and safety vests (PPE compliance)
* Identify construction components
* Analyze images and videos from construction sites
* Generate inspection results and safety metrics

---

### Backend Layer

**Technologies:** FastAPI, REST APIs

**Purpose:**

* Receive image/video uploads
* Communicate with the AI detection engine
* Manage projects, users, and inspections
* Generate reports and serve analytics data

---

### Database Layer

**Technology:** PostgreSQL

**Purpose:**

* Store inspection records
* Store compliance and violation history
* Manage project and user information
* Maintain report and audit logs

---

### Frontend / Dashboard Layer

**Technology:** React

**Purpose:**

* Display inspection results
* Visualize compliance metrics
* Track construction progress
* View reports, alerts, and analytics

---

### Storage Layer

**Technology:** AWS S3

**Purpose:**

* Store uploaded images and videos
* Store generated reports
* Maintain inspection history

---

### Deployment Layer

**Technologies:** Docker, AWS

**Purpose:**

* Containerize application services
* Deploy backend and dashboard
* Enable scalable cloud hosting

---

## Device & Input Sources

### MVP

* Uploaded Images
* Uploaded Videos
* Mobile Phone Cameras
* Tablet-Based Site Inspections

### Future Integrations

* CCTV Cameras
* IP Cameras
* Drones / UAVs
* Raspberry Pi Devices
* NVIDIA Jetson Edge Devices

### Future Edge AI Layer

**Technologies:** ONNX, TensorRT

**Purpose:**

* Optimize AI models for edge deployment
* Enable real-time inference on CCTV and drone feeds
* Reduce latency and cloud dependency

---

## Project Timeline

### Week 1 (June 17 – June 22)

* Domain Research
* Competitor Analysis
* User Stories & Customer Discovery
* Portal Design
* Architecture Design
* Technology Stack Finalization
* Dataset Research

### Week 2

* Dataset Collection & Preparation
* PPE Detection Pipeline Setup
* YOLOv8 Environment Setup

### Week 3

* Model Training & Evaluation
* Detection Service Development
* FastAPI Backend Foundation

### Week 4

* PostgreSQL Integration
* Dashboard Development
* Image & Video Upload Workflows

### Week 5

* Compliance Analytics
* Automated Report Generation
* Rule-Based Alert Engine

### Week 6

* End-to-End Integration
* Dockerization
* AWS Deployment
* Testing & Validation

### Week 7 (Final Week)

* Performance Optimization
* Bug Fixes
* Documentation
* Final Demo Preparation

---

## Dependencies

* Suitable datasets for PPE and construction component detection
* Cloud resources for deployment and testing
* Sample construction site images/videos for validation

---

## Potential Challenges

* Finding datasets that closely match real construction site conditions
* Handling different lighting conditions, camera angles, and crowded scenes
* Balancing model accuracy with the internship timeline
* Ensuring smooth integration between AI, backend, and dashboard components

---

## Our Approach

To reduce risk, we plan to start with a focused MVP and build incrementally. We will leverage pretrained YOLOv8 models, validate each module independently, and prioritize delivering a complete end-to-end working system before adding advanced features.

---

## Long-Term Vision

* Drone-Based Inspections
* CCTV Monitoring
* Edge AI Deployment
* Predictive Safety Analytics
* Multi-Site Monitoring Platform
* AI Safety Copilot for Construction Teams
