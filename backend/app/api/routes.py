import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agent.events import event_bus, serialize_trace_event
from app.agent.providers import get_provider
from app.agent.runner import latest_decision_for_conversation, run_refund_agent
from app.core.config import get_settings
from app.db.database import get_db
from app.db.models import Conversation, TraceEvent
from app.models.schemas import ChatRequest, ChatResponse, ConversationDetail, ConversationSummary, HealthResponse

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    provider = get_provider()
    return HealthResponse(
        status="ok",
        database=settings.database_url,
        llm_provider=provider.name,
        provider_configured=provider.name == "local-heuristic" or provider.configured(),
        business_today=settings.business_today,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    return await run_refund_agent(db, request)


@router.get("/conversations", response_model=list[ConversationSummary])
def conversations(db: Session = Depends(get_db)) -> list[ConversationSummary]:
    rows = db.scalars(select(Conversation).order_by(Conversation.updated_at.desc()).limit(25)).all()
    return [
        ConversationSummary(
            id=row.id,
            customer_email=row.customer_email,
            status=row.status,
            latest_message=row.latest_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
            decision=latest_decision_for_conversation(db, row.id),  # type: ignore[arg-type]
        )
        for row in rows
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation_detail(conversation_id: str, db: Session = Depends(get_db)) -> ConversationDetail:
    row = db.scalar(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages), selectinload(Conversation.trace_events))
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = sorted(row.messages, key=lambda item: item.id)
    events = sorted(row.trace_events, key=lambda item: item.id)
    return ConversationDetail(
        id=row.id,
        customer_email=row.customer_email,
        status=row.status,
        latest_message=row.latest_message,
        messages=messages,
        trace=[serialize_trace_event(event) for event in events],  # type: ignore[list-item]
    )


@router.get("/conversations/{conversation_id}/events")
async def conversation_events(conversation_id: str, db: Session = Depends(get_db)) -> StreamingResponse:
    existing = db.scalars(
        select(TraceEvent).where(TraceEvent.conversation_id == conversation_id).order_by(TraceEvent.id)
    ).all()

    async def stream() -> AsyncGenerator[str, None]:
        for event in existing:
            yield f"event: trace\ndata: {json.dumps(serialize_trace_event(event))}\n\n"

        queue = event_bus.subscribe(conversation_id)
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"event: trace\ndata: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield "event: heartbeat\ndata: {}\n\n"
        finally:
            event_bus.unsubscribe(conversation_id, queue)

    return StreamingResponse(stream(), media_type="text/event-stream")

