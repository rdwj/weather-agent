#!/usr/bin/env python3
"""
FastAPI REST API for Weather Agent.

This API provides endpoints for weather data retrieval, analysis,
and intelligent weather services.
"""

import os
import sys
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Body, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.weather_agent import WeatherAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global agent instance
weather_agent: Optional[WeatherAgent] = None


# Pydantic models for request/response
class WeatherRequest(BaseModel):
    """Weather request model."""
    location: str = Field(..., description="Location (e.g., 'Seattle, WA')")
    use_cache: bool = Field(default=True, description="Use cached data if available")


class WeatherAnalysisRequest(BaseModel):
    """Weather analysis request."""
    weather_data: Dict[str, Any] = Field(..., description="Weather data to analyze")
    analysis_type: str = Field(
        default="general",
        description="Type of analysis (general, safety, activity, travel)"
    )


class LocationComparisonRequest(BaseModel):
    """Location comparison request."""
    locations: List[str] = Field(
        ...,
        min_items=2,
        max_items=5,
        description="List of locations to compare"
    )


class ForecastRequest(BaseModel):
    """Forecast request model."""
    location: str = Field(..., description="Location for forecast")
    days: int = Field(
        default=5,
        ge=1,
        le=7,
        description="Number of days to forecast"
    )


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str = Field(..., description="User message")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Previous conversation messages"
    )


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    mcp_connected: bool
    llm_available: bool
    cache_stats: Dict[str, Any]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler for startup and shutdown.
    """
    global weather_agent

    # Startup
    logger.info("Starting Weather API...")

    # Create agent with MCP URL from environment or use default
    mcp_url = os.getenv(
        "MCP_URL",
        "https://mcp-server-weather-mcp.apps.cluster-sdzgj.sdzgj.sandbox319.opentlc.com/mcp/"
    )

    weather_agent = WeatherAgent(mcp_url=mcp_url)

    # Initialize agent
    initialized = await weather_agent.initialize()
    if initialized:
        logger.info("Weather agent initialized successfully")
    else:
        logger.warning("Weather agent initialized with limited capabilities")

    yield

    # Shutdown
    logger.info("Shutting down Weather API...")
    if weather_agent:
        await weather_agent.close()


# Create FastAPI app
app = FastAPI(
    title="Weather Agent API",
    description="Intelligent weather services with MCP integration",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns:
        Health status and component availability
    """
    if not weather_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    return HealthResponse(
        status="healthy",
        mcp_connected=weather_agent.is_mcp_connected(),
        llm_available=weather_agent.llm_client.is_available(),
        cache_stats=weather_agent.get_cache_stats()
    )


@app.get("/weather")
async def get_weather(
    location: str = Query(..., description="Location (e.g., 'Seattle, WA')"),
    use_cache: bool = Query(True, description="Use cached data if available")
):
    """
    Get current weather for a location.

    Args:
        location: Location string
        use_cache: Whether to use cached data

    Returns:
        Weather data or error
    """
    if not weather_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    result = await weather_agent.get_weather(location, use_cache)

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Weather lookup failed"))

    return result


@app.post("/weather")
async def get_weather_post(request: WeatherRequest):
    """
    Get current weather for a location (POST version).

    Args:
        request: Weather request with location

    Returns:
        Weather data or error
    """
    if not weather_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    result = await weather_agent.get_weather(
        request.location,
        request.use_cache
    )

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Weather lookup failed"))

    return result


@app.post("/weather/analyze")
async def analyze_weather(request: WeatherAnalysisRequest):
    """
    Analyze weather data using LLM.

    Args:
        request: Weather data and analysis type

    Returns:
        Analysis results
    """
    if not weather_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    result = await weather_agent.analyze_weather(
        request.weather_data,
        request.analysis_type
    )

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Analysis failed")
        )

    return result


@app.post("/weather/compare")
async def compare_locations(request: LocationComparisonRequest):
    """
    Compare weather between multiple locations.

    Args:
        request: List of locations to compare

    Returns:
        Comparison results
    """
    if not weather_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    result = await weather_agent.compare_locations(request.locations)

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Comparison failed")
        )

    return result


@app.get("/forecast")
async def get_forecast(
    location: str = Query(..., description="Location for forecast"),
    days: int = Query(5, ge=1, le=7, description="Number of days")
):
    """
    Get weather forecast for a location.

    Args:
        location: Location string
        days: Number of days to forecast

    Returns:
        Forecast data
    """
    if not weather_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    result = await weather_agent.get_forecast(location, days)

    if not result["success"]:
        raise HTTPException(
            status_code=404,
            detail=result.get("error", "Forecast lookup failed")
        )

    return result


@app.post("/forecast")
async def get_forecast_post(request: ForecastRequest):
    """
    Get weather forecast for a location (POST version).

    Args:
        request: Forecast request

    Returns:
        Forecast data
    """
    if not weather_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    result = await weather_agent.get_forecast(
        request.location,
        request.days
    )

    if not result["success"]:
        raise HTTPException(
            status_code=404,
            detail=result.get("error", "Forecast lookup failed")
        )

    return result


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Natural language chat interface for weather queries.

    Args:
        request: Chat message and optional history

    Returns:
        Agent response
    """
    if not weather_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    result = await weather_agent.chat(
        request.message,
        request.conversation_history
    )

    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Chat processing failed")
        )

    return result


@app.post("/cache/clear")
async def clear_cache():
    """
    Clear the weather cache.

    Returns:
        Success status
    """
    if not weather_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    await weather_agent.clear_cache()

    return {
        "success": True,
        "message": "Cache cleared successfully"
    }


@app.get("/cache/stats")
async def cache_stats():
    """
    Get cache statistics.

    Returns:
        Cache statistics
    """
    if not weather_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    return weather_agent.get_cache_stats()


@app.get("/tools")
async def list_tools():
    """
    List available MCP tools.

    Returns:
        List of available tools
    """
    if not weather_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    tools = await weather_agent.list_tools()
    return {"tools": tools}


@app.get("/prompts")
async def list_prompts():
    """
    List available MCP prompts.

    Returns:
        List of available prompts
    """
    if not weather_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    prompts = await weather_agent.list_prompts()
    return {"prompts": prompts}


@app.get("/resources")
async def list_resources():
    """
    List available MCP resources.

    Returns:
        List of available resources
    """
    if not weather_agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    resources = await weather_agent.list_resources()
    return {"resources": resources}


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn

    # Run the API
    uvicorn.run(
        "weather_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )