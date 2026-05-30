from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


DecisionStatus = Literal["APPROVED", "DENIED", "ESCALATED", "NEEDS_INFO"]


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    customer_email: str | None = Field(default=None, max_length=320)


class TraceEventOut(BaseModel):
    id: int
    conversation_id: str
    step: str
    title: str
    detail: dict[str, Any]
    severity: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatResponse(BaseModel):
    conversation_id: str
    assistant_message: str
    decision: DecisionStatus
    triggered_rules: list[str]
    needs_escalation: bool
    injection_detected: bool
    trace: list[TraceEventOut]


class ConversationSummary(BaseModel):
    id: str
    customer_email: str | None
    status: str
    latest_message: str
    created_at: datetime
    updated_at: datetime
    decision: DecisionStatus | None = None

    model_config = ConfigDict(from_attributes=True)


class ConversationDetail(BaseModel):
    id: str
    customer_email: str | None
    status: str
    latest_message: str
    messages: list[MessageOut]
    trace: list[TraceEventOut]


class HealthResponse(BaseModel):
    status: str
    database: str
    llm_provider: str
    provider_configured: bool
    business_today: str
