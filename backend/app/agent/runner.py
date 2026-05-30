import json
import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agent.events import record_trace, serialize_trace_event
from app.agent.guardrails import scan_for_injection
from app.agent.providers import ExtractedIntent, get_provider, template_reply
from app.agent.tools import (
    create_escalation_case,
    evaluate_refund_policy,
    list_customer_orders,
    lookup_customer_by_email,
    lookup_order,
    read_refund_policy,
)
from app.db.models import Conversation, Message, RefundRequest, TraceEvent
from app.models.schemas import ChatRequest, ChatResponse, TraceEventOut


async def _safe_extract(message: str, customer_email: str | None, conversation_id: str, db: Session) -> ExtractedIntent:
    provider = get_provider()
    try:
        result = await provider.extract_intent(message, customer_email)
        extracted = result.value
        assert isinstance(extracted, ExtractedIntent)
        await record_trace(
            db,
            conversation_id,
            "llm.extract",
            f"Intent extracted with {result.provider}",
            extracted.model_dump(),
        )
        return extracted
    except Exception as exc:
        from app.agent.providers import _heuristic_extract

        extracted = _heuristic_extract(message, customer_email)
        await record_trace(
            db,
            conversation_id,
            "llm.fallback",
            "Provider failed; local extraction fallback used",
            {"error": str(exc), "extracted": extracted.model_dump()},
            "warning",
        )
        return extracted


async def _safe_compose(context: dict[str, Any], conversation_id: str, db: Session) -> str:
    provider = get_provider()
    try:
        result = await provider.compose_reply(context)
        assert isinstance(result.value, str)
        await record_trace(
            db,
            conversation_id,
            "llm.compose",
            f"Customer reply composed with {result.provider}",
            {"decision": context["decision"]},
        )
        return result.value
    except Exception as exc:
        await record_trace(
            db,
            conversation_id,
            "llm.fallback",
            "Provider failed; template response used",
            {"error": str(exc)},
            "warning",
        )
        return template_reply(context)


async def run_refund_agent(db: Session, request: ChatRequest) -> ChatResponse:
    conversation_id = request.conversation_id or str(uuid.uuid4())
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        conversation = Conversation(id=conversation_id, customer_email=str(request.customer_email) if request.customer_email else None)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    conversation.customer_email = str(request.customer_email or conversation.customer_email or "") or None
    conversation.latest_message = request.message
    db.add(Message(conversation_id=conversation_id, role="user", content=request.message))
    db.commit()

    await record_trace(db, conversation_id, "intake", "Customer message received", {"message_length": len(request.message)})

    injection = scan_for_injection(request.message)
    await record_trace(
        db,
        conversation_id,
        "safety.scan",
        "Prompt-injection scan completed",
        {"detected": injection.detected, "risk": injection.risk, "patterns": injection.patterns},
        "warning" if injection.detected else "info",
    )

    extracted = await _safe_extract(request.message, str(request.customer_email) if request.customer_email else conversation.customer_email, conversation_id, db)
    customer_email = (str(request.customer_email) if request.customer_email else extracted.customer_email or conversation.customer_email)
    customer_email = customer_email.lower() if customer_email else None
    order_id = extracted.order_id.upper() if extracted.order_id else None

    policy_preview = read_refund_policy()
    await record_trace(db, conversation_id, "tool.read_refund_policy", "Refund policy loaded", {"characters": len(policy_preview)})

    customer = lookup_customer_by_email(db, customer_email)
    await record_trace(db, conversation_id, "tool.lookup_customer_by_email", "Customer lookup completed", {"email": customer_email, "found": bool(customer)})

    order = lookup_order(db, order_id)
    await record_trace(db, conversation_id, "tool.lookup_order", "Order lookup completed", {"order_id": order_id, "found": bool(order)})

    missing_fields: list[str] = []
    if not order_id:
        missing_fields.append("order_id")
    if not customer_email:
        missing_fields.append("customer_email")

    if customer_email and not order_id:
        orders = list_customer_orders(db, customer_email)
        await record_trace(db, conversation_id, "tool.list_customer_orders", "Known customer orders listed", {"count": len(orders)})

    if missing_fields or not order:
        if not order and order_id:
            missing_fields.append("valid_order_id")
        context = {
            "decision": "NEEDS_INFO",
            "order_id": order_id,
            "customer_email": customer_email,
            "missing_fields": missing_fields,
            "triggered_rules": ["R0_ORDER_REQUIRED"],
            "explanation_facts": ["The agent needs verified customer and order details before applying the refund policy."],
            "injection_detected": injection.detected,
        }
        reply = await _safe_compose(context, conversation_id, db)
        db.add(Message(conversation_id=conversation_id, role="assistant", content=reply))
        conversation.status = "NEEDS_INFO"
        conversation.latest_message = reply
        db.commit()
        return _chat_response(db, conversation_id, reply, "NEEDS_INFO", ["R0_ORDER_REQUIRED"], False, injection.detected)

    evaluation = evaluate_refund_policy(db, order_id, customer_email)
    await record_trace(db, conversation_id, "tool.evaluate_refund_policy", "Deterministic policy engine completed", evaluation)

    if evaluation["decision"] == "ESCALATED":
        escalation = create_escalation_case(db, conversation_id, order_id, "; ".join(evaluation["explanation_facts"]))
        await record_trace(db, conversation_id, "tool.create_escalation_case", "Human escalation case created", escalation, "warning")

    await record_trace(
        db,
        conversation_id,
        "guardrail.lock",
        "Backend safety gate locked the final decision",
        {"decision": evaluation["decision"], "model_cannot_override": True},
    )

    context = {
        "decision": evaluation["decision"],
        "order_id": order_id,
        "customer_email": customer_email,
        "customer": customer,
        "order": order,
        "triggered_rules": evaluation["triggered_rules"],
        "explanation_facts": evaluation["explanation_facts"],
        "risk_flags": evaluation["risk_flags"],
        "requires_human_review": evaluation["requires_human_review"],
        "injection_detected": injection.detected,
    }
    reply = await _safe_compose(context, conversation_id, db)

    db.add(Message(conversation_id=conversation_id, role="assistant", content=reply))
    db.add(
        RefundRequest(
            conversation_id=conversation_id,
            customer_id=customer["id"] if customer else None,
            order_id=order_id,
            decision=evaluation["decision"],
            reason="; ".join(evaluation["explanation_facts"]),
        )
    )
    conversation.status = evaluation["decision"]
    conversation.latest_message = reply
    db.commit()

    await record_trace(db, conversation_id, "final", "Final response returned", {"decision": evaluation["decision"]})
    return _chat_response(
        db,
        conversation_id,
        reply,
        evaluation["decision"],
        evaluation["triggered_rules"],
        evaluation["requires_human_review"],
        injection.detected,
    )


def _chat_response(
    db: Session,
    conversation_id: str,
    reply: str,
    decision: str,
    triggered_rules: list[str],
    needs_escalation: bool,
    injection_detected: bool,
) -> ChatResponse:
    events = db.scalars(
        select(TraceEvent).where(TraceEvent.conversation_id == conversation_id).order_by(TraceEvent.id)
    ).all()
    return ChatResponse(
        conversation_id=conversation_id,
        assistant_message=reply,
        decision=decision,  # type: ignore[arg-type]
        triggered_rules=triggered_rules,
        needs_escalation=needs_escalation,
        injection_detected=injection_detected,
        trace=[TraceEventOut(**serialize_trace_event(event)) for event in events],
    )


def latest_decision_for_conversation(db: Session, conversation_id: str) -> str | None:
    refund = db.scalar(
        select(RefundRequest)
        .where(RefundRequest.conversation_id == conversation_id)
        .order_by(desc(RefundRequest.created_at))
        .limit(1)
    )
    return refund.decision if refund else None

