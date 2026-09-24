# WIDDX Nexus — Windows Uninstaller
$ErrorActionPreference = "Continue"

Write-Host "=== WIDDX Nexus — Uninstaller ===" -ForegroundColor Cyan

pip uninstall widdx-nexus -y

if ($LASTEXITCODE -eq 0) {
    Write-Host "WIDDX Nexus uninstalled successfully." -ForegroundColor Green
} else {
    Write-Host "Uninstall completed (may have been already uninstalled)." -ForegroundColor Yellow
}
