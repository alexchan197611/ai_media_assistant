Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== AI Media Assistant Web 2.0 setup =="

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw "未找到 Python。请先安装 Python 3.11+，并勾选 Add python.exe to PATH。"
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "未找到 Node.js/npm。请先安装 Node.js 20+。"
}

$pythonVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "Python: $pythonVersion"
Write-Host "Node: $(node -v)"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  Write-Host "Creating Python virtual environment..."
  python -m venv .venv
}

Write-Host "Installing Python dependencies..."
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -e ".[dev]"

Write-Host "Installing Node dependencies..."
npm install
if (Test-Path "apps\web\package.json") {
  npm --prefix apps/web install
}

Write-Host "Building Web UI..."
npm run build

Write-Host "Preparing local storage directories..."
New-Item -ItemType Directory -Force -Path storage\projects, storage\uploads, storage\outputs, storage\resources | Out-Null

Write-Host "Upgrading SQLite database..."
npm run db:upgrade

Write-Host ""
Write-Host "Setup complete. Run scripts\start_windows.ps1 to start the app."
