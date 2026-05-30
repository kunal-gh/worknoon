from datetime import date

from app.core.config import get_settings


def business_today() -> date:
    return date.fromisoformat(get_settings().business_today)

