from dataclasses import dataclass


INJECTION_PATTERNS = (
    "ignore previous",
    "ignore all previous",
    "ignore instructions",
    "developer message",
    "system prompt",
    "jailbreak",
    "override policy",
    "bypass policy",
    "you are now",
    "act as admin",
    "i am the admin",
    "i am your administrator",
    "refund everything",
    "approve no matter what",
)


@dataclass(frozen=True)
class InjectionScan:
    detected: bool
    patterns: list[str]
    risk: str


def scan_for_injection(message: str) -> InjectionScan:
    lowered = message.lower()
    matches = [pattern for pattern in INJECTION_PATTERNS if pattern in lowered]
    if len(matches) >= 2:
        risk = "HIGH"
    elif matches:
        risk = "MEDIUM"
    else:
        risk = "LOW"
    return InjectionScan(detected=bool(matches), patterns=matches, risk=risk)

