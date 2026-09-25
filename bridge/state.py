"""In-memory state and event fan-out for the bridge."""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Any

from bridge.models import RiskLevel, SourceHealth, ThreatEvent, ThreatPosture, ensure_timezone, utc_now


ACTIVE_STATUSES = {"active", "failed", "denied"}


class BridgeState:
    def __init__(self, event_buffer_size: int, posture_decay_seconds: float) -> None:
        self._event_buffer_size = event_buffer_size
        self._posture_decay_seconds = posture_decay_seconds
        self._events: deque[ThreatEvent] = deque(maxlen=event_buffer_size)
        self._source_health: dict[str, SourceHealth] = {}
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()

    async def add_event(self, event: ThreatEvent) -> None:
        async with self._lock:
            self._events.append(event)
            state_snapshot = self._build_state_locked()
            subscribers = list(self._subscribers)

        await self._publish(subscribers, "event", event.to_dict())
        await self._publish(subscribers, "state", state_snapshot)

    async def get_events(self) -> list[dict[str, Any]]:
        async with self._lock:
            return [event.to_dict() for event in reversed(self._events)]

    async def get_state(self) -> dict[str, Any]:
        async with self._lock:
            return self._build_state_locked()

    async def get_health_snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return {
                name: health.to_dict()
                for name, health in sorted(self._source_health.items())
            }

    async def record_source_health(
        self,
        source: str,
        *,
        available: bool,
        status: str,
        error: str | None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        now = utc_now()

        async with self._lock:
            previous = self._source_health.get(source)
            last_success_at = now if available else previous.last_success_at if previous else None
            effective_status = status
            effective_error = error

            if (
                source == "attack_sim"
                and previous is not None
                and previous.status == "mitigated"
            ):
                activity_resumed = bool(details.get("activity_resumed"))
                if not (available and status == "online" and activity_resumed):
                    effective_status = "mitigated"
                    effective_error = previous.last_error

            self._source_health[source] = SourceHealth(
                source=source,
                available=available,
                status=effective_status,
                checked_at=now,
                last_success_at=last_success_at,
                last_error=effective_error,
                details=details,
            )
            state_snapshot = self._build_state_locked()
            subscribers = list(self._subscribers)

        await self._publish(subscribers, "state", state_snapshot)

    async def mark_source_mitigated(self, source: str, message: str, details: dict[str, Any] | None = None) -> None:
        details = details or {}
        now = utc_now()

        async with self._lock:
            previous = self._source_health.get(source)
            self._source_health[source] = SourceHealth(
                source=source,
                available=False,
                status="mitigated",
                checked_at=now,
                last_success_at=previous.last_success_at if previous else None,
                last_error=message,
                details={**details, "mitigated_at": now.isoformat()},
            )
            state_snapshot = self._build_state_locked()
            subscribers = list(self._subscribers)

        await self._publish(subscribers, "state", state_snapshot)

    async def get_source_status(self, source: str) -> str | None:
        async with self._lock:
            health = self._source_health.get(source)
            return health.status if health else None

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=50)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    def _build_state_locked(self) -> dict[str, Any]:
        posture = self._calculate_posture_locked()
        return {
            "events": [event.to_dict() for event in reversed(self._events)],
            "global_risk_score": posture.global_risk_score,
            "global_threat_level": posture.global_threat_level,
            "active_event_count": posture.active_event_count,
            "event_count": len(self._events),
            "source_health": {
                name: health.to_dict()
                for name, health in sorted(self._source_health.items())
            },
        }

    def _calculate_posture_locked(self) -> ThreatPosture:
        if not self._events:
            return ThreatPosture(global_risk_score=0, global_threat_level="low", active_event_count=0)

        recent_events = list(self._events)[-20:]
        weighted_scores = [event.risk_score * self._event_recency_weight(event) for event in recent_events]
        active_scores = [score for score in weighted_scores if score > 0]

        if not active_scores:
            return ThreatPosture(global_risk_score=0, global_threat_level="low", active_event_count=0)

        average_score = sum(active_scores) / len(active_scores)
        peak_score = max(active_scores)

        # Weighted toward the hottest event so the posture reacts to spikes,
        # while still considering the average of the recent stream. Each event's
        # contribution decays over time so containment reduces posture naturally.
        global_risk_score = round((peak_score * 0.6) + (average_score * 0.4))

        level = self._risk_level_for_score(global_risk_score)

        active_event_count = sum(
            1
            for event in self._events
            if event.status in ACTIVE_STATUSES and self._event_recency_weight(event) > 0.1
        )
        return ThreatPosture(
            global_risk_score=global_risk_score,
            global_threat_level=level,
            active_event_count=active_event_count,
        )

    def _event_recency_weight(self, event: ThreatEvent) -> float:
        event_time = ensure_timezone(event.ingested_at)
        age_seconds = max((utc_now() - event_time).total_seconds(), 0)
        if age_seconds >= self._posture_decay_seconds:
            return 0.0
        return max(0.0, 1 - (age_seconds / self._posture_decay_seconds))

    def _risk_level_for_score(self, score: int) -> RiskLevel:
        if score >= 75:
            return "critical"
        if score >= 50:
            return "high"
        if score >= 25:
            return "medium"
        return "low"

    async def _publish(
        self,
        subscribers: list[asyncio.Queue[dict[str, Any]]],
        event_name: str,
        payload: dict[str, Any],
    ) -> None:
        message = {"event": event_name, "data": payload}
        for subscriber in subscribers:
            if subscriber.full():
                try:
                    subscriber.get_nowait()
                except asyncio.QueueEmpty:
                    pass

            try:
                subscriber.put_nowait(message)
            except asyncio.QueueFull:
                continue
