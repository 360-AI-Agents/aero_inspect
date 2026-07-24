from fastapi import Request
from fastapi.responses import JSONResponse


class InspectionNotFoundError(Exception):
    def __init__(self, inspection_id: int):
        self.inspection_id = inspection_id


class CameraNotFoundError(Exception):
    def __init__(self, camera_id: int):
        self.camera_id = camera_id


class ReportNotFoundError(Exception):
    def __init__(self, inspection_id: int):
        self.inspection_id = inspection_id


async def inspection_not_found_handler(request: Request, exc: InspectionNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": f"Inspection {exc.inspection_id} not found"}
    )


async def camera_not_found_handler(request: Request, exc: CameraNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": f"Camera {exc.camera_id} not found"}
    )


async def report_not_found_handler(request: Request, exc: ReportNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": f"No report available for inspection {exc.inspection_id}"}
    )