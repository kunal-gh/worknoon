import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import business_today
from app.db.models import Customer, Escalation, Order
from app.agent.policy import evaluate_order_policy


def customer_to_dict(customer: Customer | None) -> dict[str, Any] | None:
    if customer is None:
        return None
    return {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "loyalty_tier": customer.loyalty_tier,
        "account_age_days": customer.account_age_days,
        "total_spent": customer.total_spent,
        "fraud_risk": customer.fraud_risk,
    }


def order_to_dict(order: Order | None) -> dict[str, Any] | None:
    if order is None:
        return None
    return {
        "id": order.id,
        "customer_id": order.customer_id,
        "sku": order.sku,
        "item_name": order.item_name,
        "category": order.category,
        "price": order.price,
        "purchase_date": order.purchase_date.isoformat(),
        "delivery_date": order.delivery_date.isoformat(),
        "final_sale": order.final_sale,
        "returned": order.returned,
        "status": order.status,
        "condition_note": order.condition_note,
    }


def lookup_customer_by_email(db: Session, email: str | None) -> dict[str, Any] | None:
    if not email:
        return None
    customer = db.scalar(select(Customer).where(Customer.email == email.lower()))
    return customer_to_dict(customer)


def lookup_order(db: Session, order_id: str | None) -> dict[str, Any] | None:
    if not order_id:
        return None
    order = db.get(Order, order_id.upper())
    return order_to_dict(order)


def list_customer_orders(db: Session, email: str | None) -> list[dict[str, Any]]:
    if not email:
        return []
    customer = db.scalar(select(Customer).where(Customer.email == email.lower()))
    if not customer:
        return []
    return [order_to_dict(order) for order in customer.orders if order is not None]


def read_refund_policy() -> str:
    return Path(get_settings().policy_path).read_text(encoding="utf-8")


def evaluate_refund_policy(db: Session, order_id: str | None, customer_email: str | None) -> dict[str, Any]:
    order = db.get(Order, order_id.upper()) if order_id else None
    customer = db.scalar(select(Customer).where(Customer.email == customer_email.lower())) if customer_email else None
    customer_email_matches = bool(order and customer and order.customer_id == customer.id)
    # Pass fraud_risk so R10_HIGH_FRAUD_RISK can trigger for HIGH-risk accounts
    fraud_risk = customer.fraud_risk if customer else None
    evaluation = evaluate_order_policy(order, customer_email_matches, business_today(), fraud_risk=fraud_risk)
    return {
        "decision": evaluation.decision,
        "triggered_rules": evaluation.triggered_rules,
        "explanation_facts": evaluation.explanation_facts,
        "risk_flags": evaluation.risk_flags,
        "requires_human_review": evaluation.requires_human_review,
        "confidence": evaluation.confidence,
    }


def create_escalation_case(db: Session, conversation_id: str, order_id: str | None, reason: str) -> dict[str, Any]:
    escalation = Escalation(conversation_id=conversation_id, order_id=order_id, reason=reason)
    db.add(escalation)
    db.commit()
    db.refresh(escalation)
    return {"id": escalation.id, "order_id": order_id, "reason": reason, "created_at": escalation.created_at.isoformat()}


TOOL_DESCRIPTIONS = [
    {
        "name": "lookup_customer_by_email",
        "description": "Find a customer profile by verified email address.",
        "parameters": {"email": "string"},
    },
    {
        "name": "lookup_order",
        "description": "Find one order by order ID.",
        "parameters": {"order_id": "string"},
    },
    {
        "name": "list_customer_orders",
        "description": "List the known orders for a verified customer email.",
        "parameters": {"email": "string"},
    },
    {
        "name": "read_refund_policy",
        "description": "Read the current corporate refund policy text.",
        "parameters": {},
    },
    {
        "name": "evaluate_refund_policy",
        "description": "Run the deterministic refund policy engine.",
        "parameters": {"order_id": "string", "customer_email": "string"},
    },
    {
        "name": "create_escalation_case",
        "description": "Create a human review case for requests that require escalation.",
        "parameters": {"order_id": "string", "reason": "string"},
    },
]


def compact_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), default=str)

