$ErrorActionPreference = "Stop"

$F5Root = "D:\Codex\workspaces\F5-TTS"
$Venv = Join-Path $F5Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"

if (-not (Test-Path $F5Root)) {
    git clone https://github.com/SWivid/F5-TTS.git $F5Root
}

Push-Location $F5Root
try {
    if (-not (Test-Path $Python)) {
        python -m venv $Venv
    }
    & $Python -m pip install --upgrade pip
    & $Python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
    & $Python -m pip install -e .
}
finally {
    Pop-Location
}

Write-Host "F5-TTS environment ready: $Python"
