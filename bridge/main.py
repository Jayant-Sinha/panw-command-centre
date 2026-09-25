"""FastAPI entry point for the analytics bridge."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from bridge.config import settings
from bridge.control import stop_attack_simulator
from bridge.ingest_legacy import poll_legacy_source
from bridge.ingest_live_log import watch_live_log
from bridge.state import BridgeState


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    bridge_state = BridgeState(
        event_buffer_size=settings.event_buffer_size,
        posture_decay_seconds=settings.posture_decay_seconds,
    )
    stop_event = asyncio.Event()
    tasks = [
        asyncio.create_task(watch_live_log(settings, bridge_state, stop_event), name="watch-live-log"),
        asyncio.create_task(poll_legacy_source(settings, bridge_state, stop_event), name="poll-legacy-source"),
    ]

    app.state.bridge_state = bridge_state
    app.state.stop_event = stop_event
    app.state.background_tasks = tasks

    yield

    stop_event.set()
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="Project Frankenstein Analytics Bridge", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
INDEX_FILE = Path(settings.static_dir) / "index.html"


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    return FileResponse(INDEX_FILE)


@app.get("/api/health")
async def health(request: Request) -> JSONResponse:
    bridge_state: BridgeState = request.app.state.bridge_state
    source_health = await bridge_state.get_health_snapshot()
    return JSONResponse(
        {
            "bridge": {"status": "online"},
            "sources": source_health,
        }
    )


@app.get("/api/state")
async def state(request: Request) -> JSONResponse:
    bridge_state: BridgeState = request.app.state.bridge_state
    return JSONResponse(await bridge_state.get_state())


@app.get("/api/events")
async def events(request: Request) -> JSONResponse:
    bridge_state: BridgeState = request.app.state.bridge_state
    return JSONResponse({"events": await bridge_state.get_events()})


@app.get("/api/events/stream")
async def event_stream(request: Request) -> StreamingResponse:
    bridge_state: BridgeState = request.app.state.bridge_state
    subscriber = await bridge_state.subscribe()

    async def stream() -> AsyncIterator[str]:
        try:
            initial_state = await bridge_state.get_state()
            yield _format_sse("state", initial_state)

            while True:
                if await request.is_disconnected():
                    break

                try:
                    message = await asyncio.wait_for(
                        subscriber.get(),
                        timeout=settings.state_stream_interval_seconds,
                    )
                except asyncio.TimeoutError:
                    yield _format_sse("state", await bridge_state.get_state())
                    continue

                yield _format_sse(message["event"], message["data"])
        finally:
            await bridge_state.unsubscribe(subscriber)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _format_sse(event_name: str, payload: dict[str, object]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"


@app.post("/api/control/mitigate")
async def mitigate_attack(request: Request) -> JSONResponse:
    bridge_state: BridgeState = request.app.state.bridge_state
    current_status = await bridge_state.get_source_status("attack_sim")
    result = stop_attack_simulator(settings, current_status=current_status)

    if result.simulator_status == "mitigated":
        await bridge_state.mark_source_mitigated(
            "attack_sim",
            result.message,
            details={"pid": result.pid, "action": result.action},
        )
    elif result.simulator_status in {"offline", "waiting"}:
        await bridge_state.record_source_health(
            "attack_sim",
            available=False,
            status=result.simulator_status,
            error=result.message,
            details={"pid": result.pid, "action": result.action},
        )

    return JSONResponse(result.to_dict())


def main() -> None:
    uvicorn.run(
        "bridge.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
