from fastapi import FastAPI
from backend.core.exceptions import (
    InspectionNotFoundError,
    CameraNotFoundError,
    ReportNotFoundError,
    inspection_not_found_handler,
    camera_not_found_handler,
    report_not_found_handler,
)


def register_exception_handlers(app: FastAPI):
    app.add_exception_handler(InspectionNotFoundError, inspection_not_found_handler)
    app.add_exception_handler(CameraNotFoundError, camera_not_found_handler)
    app.add_exception_handler(ReportNotFoundError, report_not_found_handler)
