"""Polling ingestion for the legacy ASP.NET raw log API."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any

import httpx

from bridge.config import Settings
from bridge.models import utc_now
from bridge.normalize import normalize_legacy_event
from bridge.scoring import score_event
from bridge.state import BridgeState


logger = logging.getLogger(__name__)


def build_legacy_dedupe_key(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()


async def poll_legacy_source(settings: Settings, state: BridgeState, stop_event: asyncio.Event) -> None:
    seen_records: set[str] = set()
    timeout = httpx.Timeout(settings.http_timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout) as client:
        while not stop_event.is_set():
            try:
                response = await client.get(settings.legacy_api_url)
                response.raise_for_status()
                payload = response.json()

                if not isinstance(payload, list):
                    raise ValueError("Legacy API response must be a JSON array.")

                new_records = 0
                for item in payload:
                    if not isinstance(item, dict):
                        logger.warning("Ignoring legacy record that is not an object: %s", item)
                        continue

                    dedupe_key = build_legacy_dedupe_key(item)
                    if dedupe_key in seen_records:
                        continue

                    seen_records.add(dedupe_key)
                    event = score_event(normalize_legacy_event(item, ingested_at=utc_now()))
                    await state.add_event(event)
                    new_records += 1

                await state.record_source_health(
                    "legacy_api",
                    available=True,
                    status="online",
                    error=None,
                    details={
                        "url": settings.legacy_api_url,
                        "known_records": len(seen_records),
                        "new_records": new_records,
                    },
                )
            except Exception as exc:  # pragma: no cover - runtime network guard.
                logger.warning("Legacy API poll failed: %s", exc)
                await state.record_source_health(
                    "legacy_api",
                    available=False,
                    status="offline",
                    error=str(exc),
                    details={"url": settings.legacy_api_url},
                )

            await _wait_for_next_cycle(stop_event, settings.legacy_poll_interval_seconds)


async def _wait_for_next_cycle(stop_event: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        return
