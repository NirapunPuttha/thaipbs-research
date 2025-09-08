from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import uvicorn
import os
from dotenv import load_dotenv

from app.api.v1.api import api_router
from app.core.config import settings
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.logging import LoggingMiddleware
from startup import startup, shutdown

load_dotenv()

app = FastAPI(
    title="Thailand PBS Research Management System",
    description="A comprehensive research content management system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    on_startup=[startup],
    on_shutdown=[shutdown]
)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

# Trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.ENVIRONMENT == "development" else [
        "yourdomain.com",
        "thaipbs-research-333367812150.asia-southeast1.run.app",
        "*.run.app"
    ]
)

# Include API router
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "message": "Thailand PBS Research Management System API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=settings.ENVIRONMENT == "development",
        log_level="debug" if settings.DEBUG else "info"
    )