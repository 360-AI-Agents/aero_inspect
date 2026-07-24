import time
from starlette.middleware.base import BaseHTTPMiddleware
from backend.core.logger import logger


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = round((time.time() - start_time) * 1000, 2)

        logger.info(
            f"{request.method} {request.url.path} "
            f"-> {response.status_code} ({duration}ms)"
        )
        return response