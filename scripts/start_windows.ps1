Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  throw "未找到 .venv。请先运行 scripts\setup_windows.ps1。"
}

if (-not (Test-Path "apps\web\dist\index.html")) {
  Write-Host "Web build not found. Building Web UI..."
  npm run build
}

Write-Host "Stopping existing local services..."
powershell -ExecutionPolicy Bypass -File scripts\stop_local_services.ps1

Write-Host "Starting AI Media Assistant..."
Write-Host "Open http://127.0.0.1:8123 in your browser."
npm run serve
