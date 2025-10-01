"""Chat models for weather agent conversations."""

from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Individual chat message."""
    role: Literal["user", "assistant", "system"] = Field(description="Message sender role")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata like weather data, location")


class ModelParameters(BaseModel):
    """Model generation parameters."""
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Controls randomness in generation")
    top_k: int = Field(default=50, ge=1, le=100, description="Limits vocabulary to top K tokens")
    top_p: float = Field(default=0.9, ge=0.0, le=1.0, description="Nucleus sampling threshold")
    max_tokens: int = Field(default=500, ge=50, le=2000, description="Maximum response length")


class ChatRequest(BaseModel):
    """Chat request from user."""
    message: str = Field(description="User's message/question")
    session_id: Optional[str] = Field(default=None, description="Session ID for conversation continuity")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context (e.g., user location)")
    model_params: Optional[ModelParameters] = Field(default=None, description="Model generation parameters")


class ChatResponse(BaseModel):
    """Chat response from assistant."""
    response: str = Field(description="Assistant's response")
    session_id: str = Field(description="Session ID for this conversation")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Weather data, locations, etc.")
    suggestions: Optional[List[str]] = Field(default=None, description="Suggested follow-up questions")


class ChatSession(BaseModel):
    """Chat session information."""
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = Field(description="User identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    messages: List[ChatMessage] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict, description="Session context (locations, preferences)")
    active: bool = Field(default=True)


class SessionListResponse(BaseModel):
    """Response for listing sessions."""
    sessions: List[Dict[str, Any]] = Field(description="List of session summaries")
    total: int = Field(description="Total number of sessions")


class SessionDetailResponse(BaseModel):
    """Response for session details."""
    session_id: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessage]
    context: Dict[str, Any]
    message_count: int