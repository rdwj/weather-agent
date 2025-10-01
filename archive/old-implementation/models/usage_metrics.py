"""UsageMetrics model."""

from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class UsageMetrics(BaseModel):
    """System performance and usage tracking."""
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime  # Rounded to minute granularity
    request_count: int = Field(0, ge=0)
    error_count: int = Field(0, ge=0)
    cache_hit_count: int = Field(0, ge=0)
    avg_response_time_ms: float = Field(0.0, ge=0)
    p95_response_time_ms: float = Field(0.0, ge=0)
    active_sessions: int = Field(0, ge=0)
    rate_limit_hits: int = Field(0, ge=0)

    @field_validator("timestamp")
    @classmethod
    def round_to_minute(cls, v):
        """Round timestamp to minute granularity."""
        return v.replace(second=0, microsecond=0)

    @field_validator("request_count", "error_count", "cache_hit_count", "active_sessions", "rate_limit_hits")
    @classmethod
    def validate_non_negative(cls, v):
        """Ensure counts are non-negative."""
        if v < 0:
            raise ValueError("Count values must be non-negative")
        return v

    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        if self.request_count == 0:
            return 0.0
        return self.error_count / self.request_count

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.request_count == 0:
            return 0.0
        return self.cache_hit_count / self.request_count


class MetricsResponse(BaseModel):
    """Response model for metrics endpoint."""
    period_start: datetime
    period_end: datetime
    total_requests: int
    cache_hit_rate: float
    avg_response_time_ms: float
    p95_response_time_ms: float
    error_rate: float