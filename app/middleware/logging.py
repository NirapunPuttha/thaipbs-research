from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        client_ip = request.client.host if request.client else "unknown"
        if settings.DEBUG:
            logger.info(f"{request.method} {request.url.path} - IP: {client_ip}")
        
        response: Response = await call_next(request)
        
        # Log response time
        process_time = time.time() - start_time
        if settings.DEBUG:
            logger.info(
                f"{request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Time: {process_time:.3f}s"
            )
        
        # Add response time header
        response.headers["X-Process-Time"] = str(process_time)
        
        return response