$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$OutputRoot = "D:\Codex\outputs"
$DistPath = Join-Path $OutputRoot "ai_caption_video_exe"
$WorkPath = "D:\Codex\cache\tmp\ai_caption_video_pyinstaller"
$SpecPath = "D:\Codex\cache\tmp\ai_caption_video_spec"
$AncientFontPath = Join-Path $ProjectRoot "assets\fonts"
$AncientAssetsPath = Join-Path $ProjectRoot "assets\ancient"

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
        --add-data "$AncientFontPath;assets\fonts" `
        --add-data "$AncientAssetsPath;assets\ancient" `
        gui_entry.py

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }

    Copy-Item -Force -Path (Join-Path $ProjectRoot "input.txt") -Destination (Join-Path $DistPath "input.txt")
    $DistAssets = Join-Path $DistPath "assets"
    New-Item -ItemType Directory -Force -Path $DistAssets | Out-Null
    $BgmLibrary = Join-Path $ProjectRoot "assets\bgm_library"
    if (Test-Path $BgmLibrary) {
        Copy-Item -Recurse -Force -Path $BgmLibrary -Destination $DistAssets
    }
}
finally {
    Pop-Location
}

Write-Host "EXE generated at: $DistPath\ai_caption_video.exe"
