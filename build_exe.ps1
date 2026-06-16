$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$OutputRoot = "D:\Codex\outputs"
$DistPath = Join-Path $OutputRoot "ai_caption_video_exe"
$WorkPath = "D:\Codex\cache\tmp\ai_caption_video_pyinstaller"
$SpecPath = "D:\Codex\cache\tmp\ai_caption_video_spec"

New-Item -ItemType Directory -Force -Path $OutputRoot, $WorkPath, $SpecPath | Out-Null
Remove-Item -Recurse -Force -Path $DistPath -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $DistPath | Out-Null

Push-Location $ProjectRoot
try {
    python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name ai_caption_video `
        --distpath $DistPath `
        --workpath $WorkPath `
        --specpath $SpecPath `
        --hidden-import imageio_ffmpeg `
        --copy-metadata imageio `
        --copy-metadata moviepy `
        gui_entry.py

    Copy-Item -Force -Path (Join-Path $ProjectRoot "input.txt") -Destination (Join-Path $DistPath "input.txt")
    Copy-Item -Recurse -Force -Path (Join-Path $ProjectRoot "assets") -Destination $DistPath
}
finally {
    Pop-Location
}

Write-Host "EXE generated at: $DistPath\ai_caption_video.exe"
