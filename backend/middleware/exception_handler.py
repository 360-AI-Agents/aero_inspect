from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from backend.core.exceptions import (
    InspectionNotFoundError,
    CameraNotFoundError,
    ReportNotFoundError,
    inspection_not_found_handler,
    camera_not_found_handler,
    report_not_found_handler,
)


async def _debug_unhandled_exception_handler(request: Request, exc: Exception):
    # TEMP DEBUG: surface the real traceback instead of a bare 500.
    import traceback
    return JSONResponse(
        status_code=500,
        content={"error": repr(exc), "traceback": traceback.format_exc()},
    )


def register_exception_handlers(app: FastAPI):
    app.add_exception_handler(InspectionNotFoundError, inspection_not_found_handler)
    app.add_exception_handler(CameraNotFoundError, camera_not_found_handler)
    app.add_exception_handler(ReportNotFoundError, report_not_found_handler)
    app.add_exception_handler(Exception, _debug_unhandled_exception_handler)