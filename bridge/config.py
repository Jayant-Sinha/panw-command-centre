"""Small environment-based configuration for the bridge."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
RUNTIME_DIR = BASE_DIR / "runtime"


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be a number.") from exc


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer.") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    legacy_api_url: str
    legacy_poll_interval_seconds: float
    live_stream_path: Path
    attack_sim_pid_path: Path
    event_buffer_size: int
    http_timeout_seconds: float
    live_log_poll_interval_seconds: float
    live_log_stale_seconds: float
    posture_decay_seconds: float
    state_stream_interval_seconds: float
    host: str
    port: int
    static_dir: Path


def load_settings() -> Settings:
    return Settings(
        legacy_api_url=os.getenv("BRIDGE_LEGACY_API_URL", "http://localhost:5042/api/raw-logs"),
        legacy_poll_interval_seconds=_env_float("BRIDGE_LEGACY_POLL_INTERVAL", 5.0),
        live_stream_path=Path(os.getenv("BRIDGE_LIVE_STREAM_PATH", str(BASE_DIR / "live_stream.log"))),
        attack_sim_pid_path=Path(os.getenv("BRIDGE_ATTACK_SIM_PID_PATH", str(RUNTIME_DIR / "attack-sim.pid"))),
        event_buffer_size=_env_int("BRIDGE_EVENT_BUFFER_SIZE", 200),
        http_timeout_seconds=_env_float("BRIDGE_HTTP_TIMEOUT", 3.0),
        live_log_poll_interval_seconds=_env_float("BRIDGE_LOG_POLL_INTERVAL", 0.5),
        live_log_stale_seconds=_env_float("BRIDGE_LOG_STALE_SECONDS", 6.0),
        posture_decay_seconds=_env_float("BRIDGE_POSTURE_DECAY_SECONDS", 24.0),
        state_stream_interval_seconds=_env_float("BRIDGE_STATE_STREAM_INTERVAL", 2.0),
        host=os.getenv("BRIDGE_HOST", "127.0.0.1"),
        port=_env_int("BRIDGE_PORT", 8000),
        static_dir=STATIC_DIR,
    )


settings = load_settings()
