"""Typed event and state models for the analytics bridge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal


SourceSystem = Literal["attack_sim", "legacy_api"]
SourceType = Literal["simulator", "legacy"]
ThreatCategory = Literal["identity", "network", "application", "endpoint", "system", "unknown"]
ThreatStatus = Literal["active", "failed", "success", "denied", "mitigated"]
RiskLevel = Literal["low", "medium", "high", "critical"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_iso8601(value: datetime) -> str:
    return ensure_timezone(value).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ThreatEvent:
    id: str
    source_system: SourceSystem
    source_type: SourceType
    observed_at: datetime
    ingested_at: datetime
    title: str
    category: ThreatCategory
    origin: str
    status: ThreatStatus
    raw_severity: int | None
    risk_score: int
    risk_level: RiskLevel
    summary: str
    recommended_action: str
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_system": self.source_system,
            "source_type": self.source_type,
            "observed_at": to_iso8601(self.observed_at),
            "ingested_at": to_iso8601(self.ingested_at),
            "title": self.title,
            "category": self.category,
            "origin": self.origin,
            "status": self.status,
            "raw_severity": self.raw_severity,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "summary": self.summary,
            "recommended_action": self.recommended_action,
            "raw": self.raw,
        }


@dataclass(frozen=True, slots=True)
class SourceHealth:
    source: str
    available: bool
    status: str
    checked_at: datetime
    last_success_at: datetime | None
    last_error: str | None
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "available": self.available,
            "status": self.status,
            "checked_at": to_iso8601(self.checked_at),
            "last_success_at": to_iso8601(self.last_success_at) if self.last_success_at else None,
            "last_error": self.last_error,
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class ThreatPosture:
    global_risk_score: int
    global_threat_level: RiskLevel
    active_event_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "global_risk_score": self.global_risk_score,
            "global_threat_level": self.global_threat_level,
            "active_event_count": self.active_event_count,
        }
