from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.db.models import Order

Decision = Literal["APPROVED", "DENIED", "ESCALATED", "NEEDS_INFO"]


@dataclass(frozen=True)
class PolicyEvaluation:
    decision: Decision
    triggered_rules: list[str]
    explanation_facts: list[str]
    risk_flags: list[str]
    requires_human_review: bool
    confidence: float


def evaluate_order_policy(
    order: Order | None,
    customer_email_matches: bool,
    today: date,
    fraud_risk: str | None = None,
) -> PolicyEvaluation:
    if order is None:
        return PolicyEvaluation(
            decision="NEEDS_INFO",
            triggered_rules=["R0_ORDER_REQUIRED"],
            explanation_facts=["A valid order ID is required before a refund decision can be made."],
            risk_flags=[],
            requires_human_review=False,
            confidence=0.99,
        )

    triggered: list[str] = []
    facts: list[str] = []
    risks: list[str] = []

    if not customer_email_matches:
        triggered.append("R6_ACCOUNT_MATCH_REQUIRED")
        facts.append("The provided email address does not match the account that placed this order.")
        risks.append("IDENTITY_MISMATCH")

    if order.status.lower() != "delivered":
        triggered.append("R7_ONLY_DELIVERED_ORDERS")
        facts.append(f"Order {order.id} is currently marked as {order.status}, so it is not refund-ready.")

    if order.category.lower() in {"digital", "gift_card"}:
        triggered.append("R5_DIGITAL_NONREFUNDABLE")
        facts.append("Digital goods and gift cards are non-refundable.")

    if order.final_sale:
        triggered.append("R2_FINAL_SALE")
        facts.append("The item was sold as final sale.")

    if order.returned:
        triggered.append("R3_ALREADY_REFUNDED")
        facts.append("The order has already been returned or refunded.")

    days_since_delivery = (today - order.delivery_date).days
    if days_since_delivery > 30:
        triggered.append("R1_WINDOW_30_DAYS")
        facts.append(f"The order was delivered {days_since_delivery} days ago, outside the 30-day refund window.")

    # Defensive: guard against None or empty condition_note
    condition_note = (order.condition_note or "").lower()
    if condition_note in {"damaged", "opened", "used"}:
        triggered.append("R8_CONDITION_REVIEW")
        facts.append("The item condition requires manual review before any refund can be issued.")

    hard_denials = {
        "R1_WINDOW_30_DAYS",
        "R2_FINAL_SALE",
        "R3_ALREADY_REFUNDED",
        "R5_DIGITAL_NONREFUNDABLE",
        "R6_ACCOUNT_MATCH_REQUIRED",
        "R7_ONLY_DELIVERED_ORDERS",
    }
    if any(rule in hard_denials for rule in triggered):
        return PolicyEvaluation(
            decision="DENIED",
            triggered_rules=triggered,
            explanation_facts=facts,
            risk_flags=risks,
            requires_human_review=False,
            confidence=0.98,
        )

    if order.price > 500:
        triggered.append("R4_ESCALATE_OVER_500")
        facts.append(f"The order value is ${order.price:.2f}, which is above the $500 automatic-refund limit.")
        return PolicyEvaluation(
            decision="ESCALATED",
            triggered_rules=triggered,
            explanation_facts=facts,
            risk_flags=risks,
            requires_human_review=True,
            confidence=0.97,
        )

    if "R8_CONDITION_REVIEW" in triggered:
        return PolicyEvaluation(
            decision="ESCALATED",
            triggered_rules=triggered,
            explanation_facts=facts,
            risk_flags=risks,
            requires_human_review=True,
            confidence=0.93,
        )

    # R10: HIGH fraud-risk customers on orders over $100 require human escalation.
    # This catches accounts with a pattern of fraudulent claims before auto-approving.
    if fraud_risk and fraud_risk.upper() == "HIGH" and order.price > 100:
        triggered.append("R10_HIGH_FRAUD_RISK")
        facts.append(
            f"This account is flagged as HIGH fraud-risk. "
            f"Refund requests over $100 require human review for such accounts."
        )
        risks.append("HIGH_FRAUD_RISK")
        return PolicyEvaluation(
            decision="ESCALATED",
            triggered_rules=triggered,
            explanation_facts=facts,
            risk_flags=risks,
            requires_human_review=True,
            confidence=0.91,
        )

    return PolicyEvaluation(
        decision="APPROVED",
        triggered_rules=["R9_ELIGIBLE_STANDARD_REFUND"],
        explanation_facts=[
            f"Order {order.id} is delivered, within the 30-day window, not final sale, and below the $500 escalation threshold."
        ],
        risk_flags=risks,
        requires_human_review=False,
        confidence=0.96,
    )
