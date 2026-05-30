from dataclasses import dataclass


INJECTION_PATTERNS = (
    # Direct override attempts
    "ignore previous",
    "ignore all previous",
    "ignore instructions",
    "disregard all",
    "disregard previous",
    "forget everything",
    "forget all previous",
    "new instruction",
    # System prompt attacks
    "developer message",
    "system prompt",
    "jailbreak",
    # Policy bypass
    "override policy",
    "bypass policy",
    "refund everything",
    "approve no matter what",
    # Identity / authority spoofing
    "you are now",
    "act as admin",
    "i am the admin",
    "i am your administrator",
    "i am a developer",
    "i am worknoon staff",
    # Persona manipulation
    "pretend you are",
    "pretend to be",
    "roleplay as",
    "act as if",
    "new persona",
    # Hypothetical framing (common jailbreak technique)
    "hypothetically speaking",
    "for educational purposes",
    "in a fictional scenario",
    "imagine you had no restrictions",
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
