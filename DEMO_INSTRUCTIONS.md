# Project Frankenstein 2.0 — Demo Instructions

## Prerequisites

- Windows + PowerShell
- .NET SDK
- Python 3.10+
- Chrome/Edge
- Repository root: `C:\PANW-L2\tc-Frankenstein`

## Setup

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

If VS Code shows `(.venv)` in the terminal, the virtual environment is already active.

## Run the Demo

Use 3 terminals.

### Terminal 1 — Legacy API

```powershell
dotnet run --project .\legacy\LegacyLogger
```

Runs on:

`http://127.0.0.1:5042`

### Terminal 2 — Attack Simulator

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\simulator\AttackSim.ps1
```

Generates live:

- Brute Force
- SQL Injection
- Port Scan
- Credential Stuffing

Events are written to `live_stream.log`.

### Terminal 3 — Analytics Bridge

```powershell
.\.venv\Scripts\python -m bridge.main
```

Runs on:

`http://127.0.0.1:8000`

### Open the Command Center

Open:

`http://127.0.0.1:8000/`

## What the Demo Does

The flow is:

```text
Legacy ASP.NET API ─────┐
                       ├──> Python Analytics Bridge ──> Threat Command Center
PowerShell Simulator ──┘
             live_stream.log
```

The bridge:

- ingests both sources
- normalizes events into one contract
- applies deterministic risk scoring
- maintains threat posture
- streams updates to the UI using SSE
- owns the mitigation control

## Demo Walkthrough

1. Start all 3 components.
2. Open the dashboard and let threats arrive.
3. Wait for a High/Critical event.
4. Select the incident and review the risk, origin, explanation, and recommended action.
5. Click **Mitigate Attack**.
6. The bridge terminates the real PowerShell simulator process.
7. The dashboard changes to **Threat Contained** and threat posture decreases as recent activity ages out.
8. Restart the simulator to demonstrate recovery and live events returning.

### Key Story

```text
Detect → Analyze → Escalate → Mitigate → Contain → Recover
```

## Useful Checks

```powershell
curl.exe http://127.0.0.1:5042/api/raw-logs
curl.exe http://127.0.0.1:8000/api/health
curl.exe http://127.0.0.1:8000/api/state
```

## Troubleshooting

If port `5042` or `8000` is already in use:

```powershell
netstat -ano | findstr ":5042"
netstat -ano | findstr ":8000"
```

Identify the owning PID before stopping it.

If the simulator exits unexpectedly, check for an older `AttackSim.ps1` process:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match "AttackSim.ps1" } |
  Select-Object ProcessId, CommandLine
```

