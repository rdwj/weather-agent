"""Weather API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
import uuid as uuid_module
import structlog

from src.models.weather_query import WeatherQueryRequest, WeatherQueryResponse
from src.models.weather_alert import WeatherAlert, AlertSeverity
from src.services.weather_agent import WeatherAgent as WeatherAgentService
from src.services.session_service import SessionStorageService as SessionService
from src.services.rate_limiter import TokenBucketRateLimiter as RateLimiter
from src.services.cache_service import CacheService
from src.workflows.weather_workflow import WeatherWorkflow

logger = structlog.get_logger(__name__)

router = APIRouter()


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None
    request_id: Optional[str] = None


class RateLimitResponse(BaseModel):
    """Rate limit exceeded response."""
    error: str = "Rate limit exceeded"
    retry_after: int  # Seconds until retry
    remaining: int = 0  # Remaining requests in window


class WeatherAlertsResponse(BaseModel):
    """Response containing weather alerts for monitored locations."""
    alerts: List[Dict[str, Any]]
    locations_monitored: int
    last_check: datetime


async def get_current_user(request: Request) -> str:
    """Extract current user from request context."""
    # In production, this would validate OAuth token
    # For now, return a default user or from header
    user_id = request.headers.get("X-User-ID", "anonymous")
    return user_id


async def check_rate_limit(user_id: str, rate_limiter: RateLimiter) -> None:
    """Check rate limit for user."""
    allowed, retry_after = await rate_limiter.check_limit(user_id)
    if not allowed:
        logger.warning("Rate limit exceeded", user_id=user_id, retry_after=retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "Rate limit exceeded", "retry_after": retry_after, "remaining": 0}
        )


@router.post("/weather/query", response_model=WeatherQueryResponse)
async def query_weather(
    request: Request,
    query_request: WeatherQueryRequest,
    user_id: str = Depends(get_current_user)
) -> WeatherQueryResponse:
    """
    Process natural language weather query.

    This endpoint accepts natural language queries about weather conditions
    and returns structured weather information along with any relevant alerts.
    """
    request_id = getattr(request.state, "request_id", None)
    logger.info(
        "Weather query received",
        user_id=user_id,
        query=query_request.query,
        request_id=request_id
    )

    try:
        # Initialize services
        rate_limiter = RateLimiter()
        cache_service = CacheService()
        session_service = SessionService()
        # workflow will be initialized after we get session_id

        # Check rate limit
        await check_rate_limit(user_id, rate_limiter)

        # Get or create session
        session_id = str(query_request.session_id) if query_request.session_id else None
        if not session_id:
            session = await session_service.create_session(user_id)
            session_id = str(session.id)
        else:
            session = await session_service.get_session(session_id)
            if not session:
                logger.warning("Invalid session ID", session_id=session_id)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid session ID"
                )

        # Check cache for recent identical query
        cache_key = f"weather_query:{user_id}:{query_request.query}"
        cached_response = await cache_service.get(cache_key)
        if cached_response:
            logger.info("Cache hit for weather query", cache_key=cache_key)
            cached_response["cache_hit"] = True
            return WeatherQueryResponse(**cached_response)

        # Process query through workflow (workflow needs to be initialized with session and user)
        workflow_instance = WeatherWorkflow(session_id=session_id, user_id=user_id)
        result = await workflow_instance.process_query(
            query=query_request.query  # Note: method expects 'query' not 'query_text'
        )

        # Build response - map workflow result to API response
        metadata = result.get("metadata", {})
        weather_data = result.get("state_summary", {}).get("weather_data")

        response = WeatherQueryResponse(
            query_id=metadata.get("query_id", str(uuid_module.uuid4())),
            response=result.get("response", "Unable to process weather query"),
            weather_data=weather_data,
            data_freshness=metadata.get("data_freshness") or datetime.utcnow(),
            cache_hit=False,
            alerts=weather_data.get("alerts", []) if weather_data else []
        )

        # Cache the response
        await cache_service.set(
            cache_key,
            response.model_dump(mode="json"),
            ttl=900  # 15 minutes
        )

        logger.info(
            "Weather query processed successfully",
            query_id=response.query_id,
            cache_hit=response.cache_hit,
            alerts_count=len(response.alerts)
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to process weather query",
            error=str(e),
            user_id=user_id,
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Weather service temporarily unavailable"
        )


@router.get("/weather/alerts", response_model=WeatherAlertsResponse)
async def get_weather_alerts(
    request: Request,
    user_id: str = Depends(get_current_user)
) -> WeatherAlertsResponse:
    """
    Get weather alerts for monitored locations.

    Returns active weather alerts for all locations the user has
    queried during their current session.
    """
    request_id = getattr(request.state, "request_id", None)
    logger.info(
        "Weather alerts requested",
        user_id=user_id,
        request_id=request_id
    )

    try:
        # Initialize services
        session_service = SessionService()
        cache_service = CacheService()

        # Get user's active sessions
        sessions = await session_service.get_user_sessions(user_id)
        if not sessions:
            logger.info("No active sessions found", user_id=user_id)
            return WeatherAlertsResponse(
                alerts=[],
                locations_monitored=0,
                last_check=datetime.utcnow()
            )

        # Collect all monitored locations from sessions
        monitored_locations = []
        for session in sessions:
            if session.location_history:
                monitored_locations.extend(session.location_history)

        # Remove duplicates based on location coordinates
        unique_locations = {}
        for loc in monitored_locations:
            key = f"{loc.get('latitude', 0)},{loc.get('longitude', 0)}"
            unique_locations[key] = loc

        # Check cache for alerts
        cache_key = f"weather_alerts:{user_id}"
        cached_alerts = await cache_service.get(cache_key)
        if cached_alerts:
            logger.info("Cache hit for weather alerts", cache_key=cache_key)
            return WeatherAlertsResponse(**cached_alerts)

        # Fetch alerts for each unique location
        all_alerts = []
        for location in unique_locations.values():
            try:
                # Here we would call the MCP weather service to get alerts
                # For now, returning empty as MCP integration happens in other tasks
                location_alerts = []  # await weather_service.get_alerts(location)
                all_alerts.extend(location_alerts)
            except Exception as e:
                logger.error(
                    "Failed to fetch alerts for location",
                    location=location,
                    error=str(e)
                )
                continue

        # Filter for severe and extreme alerts only
        filtered_alerts = [
            alert for alert in all_alerts
            if alert.get("severity") in ["Severe", "Extreme"]
        ]

        response = WeatherAlertsResponse(
            alerts=filtered_alerts,
            locations_monitored=len(unique_locations),
            last_check=datetime.utcnow()
        )

        # Cache the response
        await cache_service.set(
            cache_key,
            response.model_dump(mode="json"),
            ttl=300  # 5 minutes for alerts
        )

        logger.info(
            "Weather alerts retrieved",
            user_id=user_id,
            alerts_count=len(filtered_alerts),
            locations_monitored=len(unique_locations)
        )

        return response

    except Exception as e:
        logger.error(
            "Failed to retrieve weather alerts",
            error=str(e),
            user_id=user_id,
            request_id=request_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Alert service temporarily unavailable"
        )