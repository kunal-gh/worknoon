import asyncio
import json
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import TraceEvent


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)

    def subscribe(self, conversation_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers[conversation_id].append(queue)
        return queue

    def unsubscribe(self, conversation_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        subscribers = self._subscribers.get(conversation_id, [])
        if queue in subscribers:
            subscribers.remove(queue)

    async def publish(self, conversation_id: str, payload: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(conversation_id, [])):
            await queue.put(payload)


event_bus = EventBus()


async def record_trace(
    db: Session,
    conversation_id: str,
    step: str,
    title: str,
    detail: dict[str, Any] | None = None,
    severity: str = "info",
) -> TraceEvent:
    event = TraceEvent(
        conversation_id=conversation_id,
        step=step,
        title=title,
        detail=json.dumps(detail or {}, default=str),
        severity=severity,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    await event_bus.publish(conversation_id, serialize_trace_event(event))
    return event


def serialize_trace_event(event: TraceEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "conversation_id": event.conversation_id,
        "step": event.step,
        "title": event.title,
        "detail": json.loads(event.detail or "{}"),
        "severity": event.severity,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }

