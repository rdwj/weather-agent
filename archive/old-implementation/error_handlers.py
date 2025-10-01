"""Global error handlers for the FastAPI application."""

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError as PydanticValidationError
import structlog
from typing import Any, Dict, Optional

from src.lib.exceptions import (
    WeatherAgentException,
    ValidationError,
    ErrorCode,
    handle_external_error
)
from src.middleware.correlation import get_correlation_id, get_request_id

logger = structlog.get_logger(__name__)


def create_error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """
    Create a standardized error response.

    Args:
        request: The request that caused the error
        status_code: HTTP status code
        error_code: Application error code
        message: Human-readable error message
        details: Additional error details

    Returns:
        JSONResponse with error information
    """
    # Get correlation and request IDs
    correlation_id = get_correlation_id(request)
    request_id = get_request_id(request)

    # Build error response
    error_response = {
        "error": {
            "code": error_code,
            "message": message,
            "correlation_id": correlation_id,
            "request_id": request_id
        }
    }

    # Add details if provided
    if details:
        error_response["error"]["details"] = details

    # Log the error
    log_data = {
        "status_code": status_code,
        "error_code": error_code,
        "message": message,
        "correlation_id": correlation_id,
        "request_id": request_id,
        "path": request.url.path,
        "method": request.method
    }

    if details:
        log_data["details"] = details

    if status_code >= 500:
        logger.error("server_error", **log_data)
    else:
        logger.warning("client_error", **log_data)

    return JSONResponse(
        status_code=status_code,
        content=error_response,
        headers={
            "X-Correlation-ID": correlation_id or "",
            "X-Request-ID": request_id or ""
        }
    )


async def weather_agent_exception_handler(
    request: Request,
    exc: WeatherAgentException
) -> JSONResponse:
    """
    Handle WeatherAgentException instances.

    Args:
        request: The request that caused the exception
        exc: The WeatherAgentException instance

    Returns:
        JSONResponse with error information
    """
    return create_error_response(
        request=request,
        status_code=exc.status_code,
        error_code=exc.error_code.value,
        message=exc.message,
        details=exc.details
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors.

    Args:
        request: The request that caused the validation error
        exc: The RequestValidationError instance

    Returns:
        JSONResponse with validation error details
    """
    # Format validation errors
    errors = []
    for error in exc.errors():
        error_detail = {
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        }
        errors.append(error_detail)

    return create_error_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code=ErrorCode.VALIDATION_ERROR.value,
        message="Validation failed",
        details={"validation_errors": errors}
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException
) -> JSONResponse:
    """
    Handle FastAPI HTTPException instances.

    Args:
        request: The request that caused the exception
        exc: The HTTPException instance

    Returns:
        JSONResponse with error information
    """
    # Map status codes to error codes
    error_code_map = {
        400: ErrorCode.INVALID_REQUEST,
        401: ErrorCode.AUTHENTICATION_FAILED,
        403: ErrorCode.AUTHORIZATION_DENIED,
        404: ErrorCode.RESOURCE_NOT_FOUND,
        429: ErrorCode.RATE_LIMIT_EXCEEDED,
        500: ErrorCode.INTERNAL_ERROR,
        503: ErrorCode.SERVICE_UNAVAILABLE
    }

    error_code = error_code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)

    # Handle detail that might be a dict or string
    if isinstance(exc.detail, dict):
        message = exc.detail.get("message", str(exc.detail))
        details = exc.detail
    else:
        message = str(exc.detail)
        details = None

    return create_error_response(
        request=request,
        status_code=exc.status_code,
        error_code=error_code.value,
        message=message,
        details=details
    )


async def starlette_http_exception_handler(
    request: Request,
    exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handle Starlette HTTPException instances.

    Args:
        request: The request that caused the exception
        exc: The StarletteHTTPException instance

    Returns:
        JSONResponse with error information
    """
    # Convert to FastAPI exception and handle
    fastapi_exc = HTTPException(status_code=exc.status_code, detail=exc.detail)
    return await http_exception_handler(request, fastapi_exc)


async def general_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handle all unhandled exceptions.

    Args:
        request: The request that caused the exception
        exc: The exception instance

    Returns:
        JSONResponse with generic error message
    """
    # Log the full exception
    correlation_id = get_correlation_id(request)
    request_id = get_request_id(request)

    logger.error(
        "unhandled_exception",
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        correlation_id=correlation_id,
        request_id=request_id,
        path=request.url.path,
        method=request.method,
        exc_info=True
    )

    # Don't expose internal error details in production
    import os
    if os.getenv("ENV", "development") == "production":
        message = "An internal error occurred"
        details = None
    else:
        message = f"Internal server error: {str(exc)}"
        details = {"exception_type": type(exc).__name__}

    return create_error_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code=ErrorCode.INTERNAL_ERROR.value,
        message=message,
        details=details
    )


def register_error_handlers(app):
    """
    Register all error handlers with the FastAPI app.

    Args:
        app: The FastAPI application instance
    """
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    # Register custom exception handler
    app.add_exception_handler(WeatherAgentException, weather_agent_exception_handler)

    # Register validation error handler
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(PydanticValidationError, validation_error_handler)

    # Register HTTP exception handlers
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)

    # Register general exception handler (catches everything)
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("Error handlers registered")


class ErrorResponseMiddleware:
    """
    Middleware to ensure consistent error responses.

    This middleware catches any errors that slip through
    and ensures they return proper JSON error responses.
    """

    def __init__(self, app):
        """Initialize the middleware."""
        self.app = app

    async def __call__(self, scope, receive, send):
        """Process the request."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            """Wrap send to intercept error responses."""
            # Check if this is an error status code
            if message["type"] == "http.response.start":
                status = message.get("status", 200)
                if status >= 400:
                    # Ensure content-type is JSON for errors
                    headers = message.get("headers", [])
                    has_content_type = False
                    for header in headers:
                        if header[0].lower() == b"content-type":
                            has_content_type = True
                            break

                    if not has_content_type:
                        headers.append((b"content-type", b"application/json"))
                        message["headers"] = headers

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            # This shouldn't happen if our handlers are working,
            # but it's a safety net
            logger.error(
                "unhandled_middleware_error",
                error=str(exc),
                exc_info=True
            )

            # Send error response
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [(b"content-type", b"application/json")]
            })
            await send({
                "type": "http.response.body",
                "body": b'{"error": {"code": "INTERNAL_ERROR", "message": "An internal error occurred"}}'
            })