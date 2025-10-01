"""MCP connection settings configuration."""

import os
from typing import Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class MCPSettings(BaseSettings):
    """MCP server connection settings."""

    # MCP Server Connection
    weather_mcp_url: str = Field(
        default="http://localhost:8080",
        description="Weather MCP server URL"
    )
    weather_mcp_token: Optional[str] = Field(
        default=None,
        description="Authentication token for MCP server"
    )
    mcp_transport: str = Field(
        default="http",
        description="Transport protocol (http or stdio)"
    )
    mcp_timeout: int = Field(
        default=30,
        description="MCP request timeout in seconds"
    )

    # Mock Mode for Testing
    mock_mcp_server: bool = Field(
        default=False,
        description="Use mock MCP server for testing"
    )

    # Retry Configuration
    mcp_max_retries: int = Field(
        default=3,
        description="Maximum number of retries for MCP calls"
    )
    mcp_retry_delay: float = Field(
        default=1.0,
        description="Delay between retries in seconds"
    )

    # Cache Settings for MCP Responses
    mcp_cache_enabled: bool = Field(
        default=True,
        description="Enable caching of MCP responses"
    )
    mcp_cache_ttl: int = Field(
        default=900,  # 15 minutes
        description="MCP response cache TTL in seconds"
    )

    @field_validator("mcp_transport")
    @classmethod
    def validate_transport(cls, v):
        """Validate transport protocol."""
        valid_transports = ["http", "stdio"]
        if v not in valid_transports:
            raise ValueError(f"Transport must be one of {valid_transports}")
        return v

    @field_validator("mcp_timeout")
    @classmethod
    def validate_timeout(cls, v):
        """Validate timeout value."""
        if v < 1 or v > 300:
            raise ValueError("Timeout must be between 1 and 300 seconds")
        return v

    class Config:
        """Pydantic config."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


class MCPToolConfig:
    """Configuration for specific MCP tools."""

    # Weather tool defaults
    DEFAULT_UNITS = "imperial"  # imperial or metric
    DEFAULT_FORECAST_DAYS = 5
    MAX_FORECAST_DAYS = 14

    # Location resolution
    LOCATION_CACHE_TTL = 3600  # 1 hour
    LOCATION_FUZZY_MATCH = True

    # Alert filtering
    ALERT_SEVERITIES = ["Moderate", "Severe", "Extreme"]
    ALERT_NOTIFY_SEVERITIES = ["Severe", "Extreme"]

    @staticmethod
    def get_tool_config(tool_name: str) -> Dict[str, Any]:
        """Get configuration for a specific tool.

        Args:
            tool_name: Name of the MCP tool

        Returns:
            Tool-specific configuration dictionary
        """
        configs = {
            "get_weather": {
                "cache_ttl": 900
            },
            "get_weather_from_coordinates": {
                "cache_ttl": 900
            },
            "geocode_location": {
                "cache_ttl": 3600
            }
        }
        return configs.get(tool_name, {})


# Global settings instance
mcp_settings = MCPSettings()


def get_mcp_config() -> MCPSettings:
    """Get MCP configuration singleton.

    Returns:
        MCP settings instance
    """
    return mcp_settings


def is_mock_mode() -> bool:
    """Check if running in mock MCP mode.

    Returns:
        True if mock mode is enabled
    """
    return mcp_settings.mock_mcp_server or os.getenv("TESTING", "false").lower() == "true"