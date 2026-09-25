# Project Frankenstein 2.0

Project Frankenstein 2.0 is a small integration demo for a technical challenge. The goal is to bridge a legacy ASP.NET raw-log source and a PowerShell attack simulator into a Python analytics layer that drives a live threat dashboard and a real containment control.

## Architecture

- `legacy/LegacyLogger`: intentionally simple ASP.NET Minimal API that exposes `GET /api/raw-logs`.
- `simulator/AttackSim.ps1`: external live threat generator that appends one JSON event per line to `live_stream.log` using UTF-8 encoding and writes its process ID to `runtime/attack-sim.pid`.
- `bridge/`: Python analytics bridge that ingests source data, normalizes and scores events, serves the UI, streams state with SSE, and owns the mitigation control path.
- `scripts/start-demo.ps1`: convenience launcher for local demo setup.

## Current Status

The current implementation includes the source systems, the analytics bridge, the live dashboard, and the Sales Edge mitigation control.

## Start The Legacy Service

From the repository root:

```powershell
dotnet run --project .\legacy\LegacyLogger
```

The service exposes:

- `GET http://localhost:5042/api/raw-logs`

## Start The Simulator

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\simulator\AttackSim.ps1
```

By default, the simulator writes newline-delimited JSON to `./live_stream.log` at the repository root using UTF-8 without BOM so the Python analytics bridge can read it reliably.

The simulator also writes its PowerShell process ID to `./runtime/attack-sim.pid` so the bridge can identify and stop the correct process during mitigation.

## Bridge Role

The Python bridge:

- watches `live_stream.log`
- polls the legacy API
- normalizes both inputs into a single event contract
- scores threat severity deterministically
- exposes real-time data to the frontend
- provides a control endpoint that stops the simulator process for the live demo

## Start The Bridge

After creating the local virtual environment and installing dependencies:

```powershell
.\.venv\Scripts\python -m bridge.main
```

The bridge exposes:

- `GET http://127.0.0.1:8000/api/health`
- `GET http://127.0.0.1:8000/api/state`
- `GET http://127.0.0.1:8000/api/events`
- `GET http://127.0.0.1:8000/api/events/stream`
- `POST http://127.0.0.1:8000/api/control/mitigate`

## Sales Edge: Mitigate Attack

The command center includes a real containment control.

- The dashboard does not stop the simulator directly.
- The browser calls `POST /api/control/mitigate` on the analytics bridge.
- The bridge reads `runtime/attack-sim.pid`, verifies the running process looks like `AttackSim.ps1`, and terminates that process.
- The PID file is cleaned up.
- The dashboard then reflects the simulator as mitigated and the threat posture falls naturally as recent attack events age out of the posture window.

The legacy ASP.NET source remains online during mitigation.

## Demo Sequence

1. Start the legacy API.
2. Start the attack simulator.
3. Start the Python bridge.
4. Open `http://127.0.0.1:8000/` and wait for several threats.
5. Allow a high or critical event to appear in the feed.
6. Select the incident and click `Mitigate Attack`.
7. Observe the simulator terminate, the simulator source change to `Mitigated`, and the containment status appear.
8. Observe threat posture decay over the next several seconds as recent attack activity ages out.
9. Restart the simulator to demonstrate recovery and live attack activity returning.

## Prerequisites

- .NET SDK (for the legacy ASP.NET demo)
- Python 3.10+ (virtualenv recommended)
- PowerShell (for running the simulator)

## Setup

Create a local virtual environment and install Python dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

## Run (recommended terminal layout)

Terminal 1 — Legacy API:

```powershell
dotnet run --project .\legacy\LegacyLogger
```

Terminal 2 — Simulator:

```powershell
powershell -ExecutionPolicy Bypass -File .\simulator\AttackSim.ps1
```

Terminal 3 — Analytics Bridge:

```powershell
.\.venv\Scripts\python -m bridge.main
```

Browser:

[http://127.0.0.1:8000](http://127.0.0.1:8000/)

## Architecture Decisions (brief)

- Python / FastAPI bridge: lightweight ingestion, normalization, deterministic scoring, and SSE streaming to keep the demo self-contained.
- Deterministic scoring: ensures repeatable demo behavior and predictable escalation.
- SSE: simple server-push model for the live dashboard without complex realtime infra.
- In-memory state: sufficient for a demo and simplifies the recovery/containment flow.
- Normalized event contract: keeps UI rendering consistent across legacy and live simulator inputs.

## Sales Edge

Mitigation is a real control path: `POST /api/control/mitigate` causes the bridge to read `runtime/attack-sim.pid`, validate the target process, terminate it, and remove the PID file. This demonstrates an end-to-end containment action in the demo.
