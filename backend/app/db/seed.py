import json
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import Base, engine
from app.db.models import Customer, Order


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def seed_if_empty(db: Session) -> None:
    existing = db.scalar(select(Customer).limit(1))
    if existing:
        return

    settings = get_settings()
    payload = json.loads(Path(settings.seed_data_path).read_text(encoding="utf-8"))

    for row in payload["customers"]:
        db.add(
            Customer(
                id=row["id"],
                name=row["name"],
                email=row["email"],
                loyalty_tier=row["loyalty_tier"],
                account_age_days=row["account_age_days"],
                total_spent=row["total_spent"],
                fraud_risk=row["fraud_risk"],
            )
        )

    for row in payload["orders"]:
        db.add(
            Order(
                id=row["id"],
                customer_id=row["customer_id"],
                sku=row["sku"],
                item_name=row["item_name"],
                category=row["category"],
                price=row["price"],
                purchase_date=date.fromisoformat(row["purchase_date"]),
                delivery_date=date.fromisoformat(row["delivery_date"]),
                final_sale=row["final_sale"],
                returned=row["returned"],
                status=row["status"],
                condition_note=row["condition_note"],
            )
        )

    db.commit()

