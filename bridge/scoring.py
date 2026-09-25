"""Deterministic threat scoring for normalized events."""

from __future__ import annotations

from dataclasses import replace

from bridge.models import RiskLevel, ThreatCategory, ThreatEvent, ThreatStatus


CATEGORY_WEIGHTS: dict[ThreatCategory, int] = {
    "identity": 10,
    "network": 12,
    "application": 18,
    "endpoint": 14,
    "system": 8,
    "unknown": 5,
}

TITLE_WEIGHTS: dict[str, int] = {
    "SQL Injection": 20,
    "Credential Stuffing": 18,
    "Brute Force": 14,
    "Port Scan": 8,
    "SSH Connection": 10,
    "File Access": 12,
    "Login Attempt": 4,
}

STATUS_ADJUSTMENTS: dict[ThreatStatus, int] = {
    "active": 18,
    "failed": 12,
    "success": -20,
    "denied": 8,
    "mitigated": -30,
}

ACTION_BY_CATEGORY: dict[ThreatCategory, str] = {
    "identity": "Review authentication activity and consider blocking the source IP.",
    "network": "Inspect firewall rules and validate whether the source IP should be blocked.",
    "application": "Inspect exposed application endpoints and block the source if the pattern persists.",
    "endpoint": "Review the affected host or file access controls for suspicious activity.",
    "system": "Inspect the impacted system and verify host-level protections.",
    "unknown": "Monitor the source and collect more evidence before taking action.",
}


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def _risk_level_for_score(score: int) -> RiskLevel:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def _build_summary(event: ThreatEvent, risk_level: RiskLevel) -> str:
    return f"{risk_level.capitalize()} risk {event.title} observed from {event.origin} ({event.status})."


def _recommended_action(event: ThreatEvent, risk_level: RiskLevel) -> str:
    base_action = ACTION_BY_CATEGORY.get(event.category, ACTION_BY_CATEGORY["unknown"])
    if risk_level == "critical":
        return f"Immediate response recommended. {base_action}"
    if risk_level == "high":
        return f"Escalate for analyst review. {base_action}"
    return base_action


def score_event(event: ThreatEvent) -> ThreatEvent:
    # The scoring model is intentionally small and explainable.
    #
    # 1. Severity contributes the largest share when the source provides it.
    # 2. Event category and event title add deterministic context.
    # 3. Status adjusts risk to reflect whether the action succeeded, failed,
    #    was denied, or is still active.
    # 4. The final score is clamped into the 0-100 range and translated into a
    #    simple risk level for downstream UI consumers.
    severity_component = event.raw_severity * 6 if event.raw_severity is not None else 25
    category_component = CATEGORY_WEIGHTS.get(event.category, CATEGORY_WEIGHTS["unknown"])
    title_component = TITLE_WEIGHTS.get(event.title, 6)
    status_component = STATUS_ADJUSTMENTS.get(event.status, 0)

    risk_score = _clamp(
        severity_component + category_component + title_component + status_component,
        0,
        100,
    )
    risk_level = _risk_level_for_score(risk_score)

    return replace(
        event,
        risk_score=risk_score,
        risk_level=risk_level,
        summary=_build_summary(event, risk_level),
        recommended_action=_recommended_action(event, risk_level),
    )
