param(
  [string]$Version = "v2.0.0",
  [string]$OutputDir = "D:\Codex\outputs"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$PackageName = "ai-media-assistant"
$StageRoot = Join-Path $OutputDir $PackageName
$ZipPath = Join-Path $OutputDir "ai-media-assistant.zip"

Set-Location $Root

Write-Host "Building Web UI..."
npm run build

if (Test-Path $StageRoot) {
  Remove-Item -LiteralPath $StageRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $StageRoot | Out-Null
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$excludeDirs = @(
  ".git",
  ".venv",
  ".pytest_cache",
  "__pycache__",
  "node_modules",
  "apps\web\node_modules",
  "apps\web\.vite",
  "apps\web\dist\.vite",
  "ai_media_assistant.egg-info",
  "apps\api\app\__pycache__",
  "apps\api\app\api\routes\__pycache__",
  "apps\api\app\db\__pycache__",
  "apps\api\app\services\__pycache__",
  "packages\media_core\src\media_core\__pycache__",
  "workers\__pycache__",
  "workers\render_worker\__pycache__",
  "storage\projects",
  "storage\uploads",
  "storage\outputs",
  "models",
  "checkpoints"
)

$excludeFiles = @(
  "*.pyc",
  "*.pyo",
  "*.tsbuildinfo",
  "*.sqlite3",
  "*.db",
  "*.log",
  "*.mp4",
  "*.safetensors",
  "*.ckpt",
  "*.pt",
  "*.pth",
  "*.bin",
  "*.onnx"
)

Write-Host "Copying release files..."
robocopy $Root $StageRoot /E /XD $excludeDirs /XF $excludeFiles /NFL /NDL /NJH /NJS /NC /NS | Out-Null
$code = $LASTEXITCODE
if ($code -ge 8) {
  throw "robocopy failed with exit code $code"
}

New-Item -ItemType Directory -Force -Path `
  (Join-Path $StageRoot "storage\projects"), `
  (Join-Path $StageRoot "storage\uploads"), `
  (Join-Path $StageRoot "storage\outputs"), `
  (Join-Path $StageRoot "storage\resources") | Out-Null

New-Item -ItemType File -Force -Path `
  (Join-Path $StageRoot "storage\projects\.gitkeep"), `
  (Join-Path $StageRoot "storage\uploads\.gitkeep"), `
  (Join-Path $StageRoot "storage\outputs\.gitkeep") | Out-Null

Get-ChildItem -LiteralPath $StageRoot -Recurse -Filter "*.sh" | ForEach-Object {
  $content = [System.IO.File]::ReadAllText($_.FullName)
  $content = $content -replace "`r`n", "`n"
  [System.IO.File]::WriteAllText($_.FullName, $content, [System.Text.UTF8Encoding]::new($false))
}

if (Test-Path $ZipPath) {
  Remove-Item -LiteralPath $ZipPath -Force
}

Write-Host "Creating zip: $ZipPath"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$zip = [System.IO.Compression.ZipFile]::Open($ZipPath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
  Get-ChildItem -LiteralPath $StageRoot -Recurse -File | ForEach-Object {
    $relativePath = $_.FullName.Substring($StageRoot.Length).TrimStart("\", "/")
    $entryName = (Join-Path $PackageName $relativePath).Replace("\", "/")
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
      $zip,
      $_.FullName,
      $entryName,
      [System.IO.Compression.CompressionLevel]::Optimal
    ) | Out-Null
  }
}
finally {
  $zip.Dispose()
}

Write-Host "Release package ready:"
Write-Host $ZipPath
