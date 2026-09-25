$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "Starting LegacyLogger..." -ForegroundColor Cyan
Start-Process dotnet -ArgumentList 'run', '--project', '.\legacy\LegacyLogger' -WorkingDirectory $repoRoot

Write-Host "Starting attack simulator..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList '-ExecutionPolicy', 'Bypass', '-File', '.\simulator\AttackSim.ps1' -WorkingDirectory $repoRoot

Write-Host "Source systems launched." -ForegroundColor Green
