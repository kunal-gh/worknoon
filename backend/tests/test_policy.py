from datetime import date
from types import SimpleNamespace

from app.agent.policy import evaluate_order_policy


TODAY = date(2026, 6, 1)


def order(**overrides):
    defaults = {
        "id": "ORD-1001",
        "status": "delivered",
        "category": "apparel",
        "final_sale": False,
        "returned": False,
        "delivery_date": date(2026, 5, 22),
        "price": 89.0,
        "condition_note": "original",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_valid_refund_is_approved():
    result = evaluate_order_policy(order(), customer_email_matches=True, today=TODAY)

    assert result.decision == "APPROVED"
    assert "R9_ELIGIBLE_STANDARD_REFUND" in result.triggered_rules


def test_final_sale_is_denied():
    result = evaluate_order_policy(order(final_sale=True), customer_email_matches=True, today=TODAY)

    assert result.decision == "DENIED"
    assert "R2_FINAL_SALE" in result.triggered_rules


def test_high_value_order_is_escalated():
    result = evaluate_order_policy(order(price=720.0), customer_email_matches=True, today=TODAY)

    assert result.decision == "ESCALATED"
    assert result.requires_human_review is True
    assert "R4_ESCALATE_OVER_500" in result.triggered_rules


def test_old_order_is_denied():
    result = evaluate_order_policy(order(delivery_date=date(2026, 4, 18)), customer_email_matches=True, today=TODAY)

    assert result.decision == "DENIED"
    assert "R1_WINDOW_30_DAYS" in result.triggered_rules


def test_returned_order_is_denied():
    result = evaluate_order_policy(order(returned=True), customer_email_matches=True, today=TODAY)

    assert result.decision == "DENIED"
    assert "R3_ALREADY_REFUNDED" in result.triggered_rules


def test_digital_item_is_denied():
    result = evaluate_order_policy(order(category="digital"), customer_email_matches=True, today=TODAY)

    assert result.decision == "DENIED"
    assert "R5_DIGITAL_NONREFUNDABLE" in result.triggered_rules


def test_email_mismatch_is_denied():
    result = evaluate_order_policy(order(), customer_email_matches=False, today=TODAY)

    assert result.decision == "DENIED"
    assert "R6_ACCOUNT_MATCH_REQUIRED" in result.triggered_rules

