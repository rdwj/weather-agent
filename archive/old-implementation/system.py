"""System health and readiness endpoints."""

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from typing import Dict, Any, Optional
import os
import structlog
from src.lib.redis_client import RedisConnectionManager as RedisClient
from src.lib.mcp_client import MCPClient, MCPConfig
from src.utilities.llm_client import get_llm_client
from src.utilities.call_model import CallModel

logger = structlog.get_logger(__name__)

router = APIRouter()


class HealthStatus(BaseModel):
    """Health status response model."""
    status: str
    version: str = "1.0.0"
    service: str = "weather-agent"


class ReadinessStatus(BaseModel):
    """Readiness check response with component status."""
    ready: bool
    checks: Dict[str, bool]
    details: Dict[str, Any]


class APIInfo(BaseModel):
    """API information response."""
    service: str
    version: str
    description: str
    endpoints: Dict[str, str]
    status: str


class LLMTestResponse(BaseModel):
    """LLM test response model."""
    success: bool
    message: str
    llm_response: Optional[str] = None
    error: Optional[str] = None
    model: Optional[str] = None


@router.get("/", response_model=APIInfo, tags=["System"])
async def root() -> APIInfo:
    """
    Root endpoint with API information.

    Returns API information and available endpoints.
    """
    return APIInfo(
        service="weather-agent",
        version="1.0.0",
        description="Cloud-native conversational weather assistant",
        endpoints={
            "health": "/health - Health check endpoint",
            "ready": "/ready - Readiness check with dependency status",
            "docs": "/docs - Interactive API documentation",
            "test_llm": "/test-llm - Test LLM connectivity",
            "test_llm_schema": "POST /test-llm-with-schema - Test LLM with schema validation",
            "chat": "POST /api/v1/chat - Send a chat message",
            "sessions": "GET /api/v1/sessions - List chat sessions",
            "session_detail": "GET /api/v1/sessions/{id} - Get session history",
            "create_session": "POST /api/v1/sessions - Create new session",
            "delete_session": "DELETE /api/v1/sessions/{id} - Delete session"
        },
        status="healthy"
    )


@router.get("/health", response_model=HealthStatus, tags=["System"])
async def health_check() -> HealthStatus:
    """
    Health check endpoint.

    Returns basic health status without checking dependencies.
    Used by Kubernetes liveness probe.
    """
    logger.debug("Health check requested")
    return HealthStatus(
        status="healthy",
        version="1.0.0",
        service="weather-agent"
    )


@router.get("/ready", response_model=ReadinessStatus, tags=["System"])
async def readiness_check(response: Response) -> ReadinessStatus:
    """
    Readiness check endpoint.

    Checks all critical dependencies and returns readiness status.
    Used by Kubernetes readiness probe.
    """
    logger.debug("Readiness check requested")

    checks = {
        "redis": False,
        "mcp": False
    }

    details = {}
    all_ready = True

    # Check Redis connectivity
    try:
        redis_client = RedisClient()
        if await redis_client.ping():
            checks["redis"] = True
            details["redis"] = "Connected"
        else:
            all_ready = False
            details["redis"] = "Ping failed"
    except Exception as e:
        all_ready = False
        details["redis"] = str(e)
        logger.error("Redis readiness check failed", error=str(e))

    # Check MCP connectivity
    try:
        mcp_url = os.getenv("MCP_URL", "https://mcp-server-weather-mcp-3.apps.cluster-nl55d.nl55d.sandbox1207.opentlc.com")
        mcp_config = MCPConfig(
            url=mcp_url,
            token=os.getenv("MCP_TOKEN"),
            timeout=30
        )
        mcp_client = MCPClient(mcp_config)
        if await mcp_client.check_connection():
            checks["mcp"] = True
            details["mcp"] = "Connected"
        else:
            all_ready = False
            details["mcp"] = "Connection check failed"
    except Exception as e:
        all_ready = False
        details["mcp"] = str(e)
        logger.error("MCP readiness check failed", error=str(e))

    # Set response status based on readiness
    if not all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.warning("Service not ready", checks=checks, details=details)
    else:
        logger.info("Service ready", checks=checks)

    return ReadinessStatus(
        ready=all_ready,
        checks=checks,
        details=details
    )


@router.get("/test-llm", response_model=LLMTestResponse, tags=["System"])
async def test_llm() -> LLMTestResponse:
    """
    Test LLM connectivity and functionality.

    This endpoint tests the LLM configuration and ensures it can process requests.
    """
    logger.info("LLM test requested")

    try:
        # Get the LLM client
        llm_client = get_llm_client()

        # Check if configured
        if not llm_client.is_available():
            return LLMTestResponse(
                success=False,
                message="LLM client not configured",
                error="Missing LLM_URL or LLM_API_KEY environment variables"
            )

        # Test with a simple prompt
        test_prompt = "Please respond with: 'LLM connection successful'"

        # Call the LLM
        response = llm_client.invoke_with_metadata(
            prompt=test_prompt,
            temperature=0.1,
            max_tokens=50
        )

        llm_response = response.get('content', '')
        model_used = response.get('model', 'unknown')

        logger.info("LLM test successful", model=model_used, response_preview=llm_response[:100])

        return LLMTestResponse(
            success=True,
            message="LLM test completed successfully",
            llm_response=llm_response,
            model=model_used
        )

    except Exception as e:
        logger.error("LLM test failed", error=str(e), exc_info=True)
        return LLMTestResponse(
            success=False,
            message="LLM test failed",
            error=str(e)
        )


@router.post("/test-llm-with-schema", response_model=LLMTestResponse, tags=["System"])
async def test_llm_with_schema() -> LLMTestResponse:
    """
    Test LLM with schema validation using CallModel.

    This endpoint tests the LLM's ability to generate structured JSON responses.
    """
    logger.info("LLM schema test requested")

    try:
        # Get the LLM client
        llm_client = get_llm_client()

        if not llm_client.is_available():
            return LLMTestResponse(
                success=False,
                message="LLM client not configured",
                error="Missing LLM_URL or LLM_API_KEY environment variables"
            )

        # Initialize CallModel
        call_model = CallModel(llm_client)

        # Define a simple schema for weather response
        test_schema = {
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "temperature": {"type": "number"},
                "conditions": {"type": "string"}
            },
            "required": ["location", "temperature", "conditions"]
        }

        # Test prompt
        test_prompt = "Generate sample weather data for Seattle with temperature around 55°F and rainy conditions"

        # Call with schema validation
        result, history, success = await call_model.call(
            prompt=test_prompt,
            schema=test_schema,
            temperature=0.3
        )

        if success and result:
            logger.info("LLM schema test successful", result=result)
            return LLMTestResponse(
                success=True,
                message="LLM schema validation test successful",
                llm_response=str(result),
                model="with schema validation"
            )
        else:
            logger.warning("LLM schema test failed", history=history)
            return LLMTestResponse(
                success=False,
                message="LLM failed to generate valid schema-compliant response",
                error="Schema validation failed after retries"
            )

    except Exception as e:
        logger.error("LLM schema test failed", error=str(e), exc_info=True)
        return LLMTestResponse(
            success=False,
            message="LLM schema test failed",
            error=str(e)
        )