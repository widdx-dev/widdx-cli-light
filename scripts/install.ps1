# WIDDX Nexus — Windows Installer
param(
    [switch]$Dev,
    [switch]$Api,
    [switch]$All
)

$ErrorActionPreference = "Stop"

Write-Host "=== WIDDX Nexus — Installer ===" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found. Install Python 3.10+ from https://python.org" -ForegroundColor Red
    exit 1
}

$pythonVersion = python --version 2>&1
Write-Host "Detected: $pythonVersion"

$pipArgs = @("install", "-e", ".")

if ($All) {
    $pipArgs = @("install", "-e", ".[all]")
} elseif ($Dev) {
    $pipArgs = @("install", "-e", ".[dev]")
} elseif ($Api) {
    $pipArgs = @("install", "-e", ".[api]")
}

Write-Host "Running: pip @pipArgs"
& python -m pip @pipArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "Installation failed. Check the errors above." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "WIDDX Nexus installed successfully." -ForegroundColor Green
Write-Host "Run: widdx        (CLI)"
Write-Host "      widdx-tui    (TUI)"
Write-Host "      widdx-web    (Web UI)"
Write-Host "      widdx-api    (API server)"
