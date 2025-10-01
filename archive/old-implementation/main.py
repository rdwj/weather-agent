"""Main FastAPI application with comprehensive middleware stack."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time

# Import logging configuration
from src.lib.logging_config import setup_logging, get_logger
from src.middleware.correlation import CorrelationIDMiddleware
from src.middleware.logging import LoggingMiddleware, AccessLogMiddleware

# Setup structured logging
setup_logging()
logger = get_logger(__name__)


class TimingMiddleware(BaseHTTPMiddleware):
    """Middleware to add request timing headers."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID for tracing."""

    async def dispatch(self, request: Request, call_next):
        import uuid
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle events."""
    # Startup
    logger.info("Starting Weather Agent API", version="1.0.0")

    # Initialize any required connections here
    # This will be expanded in later tasks for Redis, MCP connections etc.

    yield

    # Shutdown
    logger.info("Shutting down Weather Agent API")

    # Clean up connections here


# Create FastAPI app
app = FastAPI(
    title="Weather Agent API",
    version="1.0.0",
    description="Cloud-native weather agent with natural language processing",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configure CORS
allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time"]
)

# Add compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add trusted host middleware for production
if os.getenv("ENV") == "production":
    allowed_hosts = os.getenv("ALLOWED_HOSTS", "").split(",")
    if allowed_hosts and allowed_hosts[0]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# Add custom middleware (order matters - correlation ID should be early)
app.add_middleware(CorrelationIDMiddleware)
app.add_middleware(TimingMiddleware)
app.add_middleware(RequestIDMiddleware)

# Add logging middleware
log_requests = os.getenv("LOG_REQUESTS", "true").lower() == "true"
log_request_body = os.getenv("LOG_REQUEST_BODY", "true").lower() == "true"
log_response_body = os.getenv("LOG_RESPONSE_BODY", "false").lower() == "true"

if log_requests:
    app.add_middleware(
        LoggingMiddleware,
        log_request_body=log_request_body,
        log_response_body=log_response_body
    )

# Add lightweight access logging
if os.getenv("ACCESS_LOG", "true").lower() == "true":
    app.add_middleware(AccessLogMiddleware)

# Import and include routers
from src.api import system, chat, metrics
from src.api.error_handlers import register_error_handlers

# Register error handlers
register_error_handlers(app)

# Include system endpoints (no prefix needed)
app.include_router(system.router, tags=["System"])

# Include API v1 endpoints - simplified chat-focused API
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(metrics.router, prefix="/api/v1", tags=["Metrics"])