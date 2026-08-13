from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
import os

from backend.config import settings
from backend.database import Base, engine, SessionLocal

from backend.models.camera import Camera
from backend.models.inspection import Inspection
from backend.models.violation import Violation
from backend.models.report import Report
from backend.models.user import User
from backend.models.settings import Settings
from backend.models.safety_manual import SafetyManual
from backend.models.safety_rule import SafetyRule
from backend.models.site_assignment import SiteAssignment
from backend.models.worker_violation import WorkerViolation
from backend.models.worker import Worker

from backend.routers.v1 import (
    health_routes,
    inspection_routes,
    dashboard_routes,
    report_routes,
    camera_routes,
    user_routes,
    settings_routes,
    alert_routes,
    safety_manual_routes,
    safety_rule_routes,
    auth_routes,
    search_routes,
    site_assignment_routes,
    live_detection_routes,
    worker_routes,
    export_routes,
    digest_routes,
)

from backend.services.daily_digest_service import DailyDigestService

from backend.middleware.request_logger import RequestLoggerMiddleware
from backend.middleware.exception_handler import register_exception_handlers

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggerMiddleware)
register_exception_handlers(app)

scheduler = BackgroundScheduler()


def run_hourly_digest_job():
    db = SessionLocal()
    try:
        result = DailyDigestService.send_hourly_digests(db)
        print(f"[Scheduled Hourly Digest] Sent: {result['sent']}, Skipped: {result['skipped_no_email']}")
    finally:
        db.close()

_startup_error = None


@app.on_event("startup")
def on_startup():
    global _startup_error
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        import traceback
        _startup_error = traceback.format_exc()
        print(f"[startup] create_all failed: {e}")

    os.makedirs("backend/uploads/evidence", exist_ok=True)
    os.makedirs("backend/uploads/worker_photos", exist_ok=True)
    os.makedirs("backend/uploads/clips", exist_ok=True)
    os.makedirs("backend/uploads/stream", exist_ok=True)

    scheduler.add_job(run_hourly_digest_job, "cron", minute=0, id="hourly_digest_job")
    scheduler.start()


@app.on_event("shutdown")
def on_shutdown():
    scheduler.shutdown()


@app.get("/debug/startup_error")
def debug_startup_error():
    return {"error": _startup_error}


app.mount("/evidence", StaticFiles(directory="backend/uploads/evidence"), name="evidence")
app.mount("/worker_photos", StaticFiles(directory="backend/uploads/worker_photos"), name="worker_photos")
app.mount("/clips", StaticFiles(directory="backend/uploads/clips"), name="clips")
app.mount("/stream", StaticFiles(directory="backend/uploads/stream"), name="stream")

app.include_router(health_routes.router)
app.include_router(inspection_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(report_routes.router)
app.include_router(camera_routes.router)
app.include_router(user_routes.router)
app.include_router(settings_routes.router)
app.include_router(alert_routes.router)
app.include_router(safety_manual_routes.router)
app.include_router(safety_rule_routes.router)
app.include_router(auth_routes.router)
app.include_router(search_routes.router)
app.include_router(site_assignment_routes.router)
app.include_router(live_detection_routes.router)
app.include_router(worker_routes.router)
app.include_router(export_routes.router)
app.include_router(digest_routes.router)