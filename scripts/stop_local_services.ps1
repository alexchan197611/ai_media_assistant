$ErrorActionPreference = "SilentlyContinue"

$ports = @(8123, 8010, 5173)
$processIds = New-Object System.Collections.Generic.HashSet[int]

foreach ($port in $ports) {
    Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $port -State Listen |
        ForEach-Object { [void]$processIds.Add([int]$_.OwningProcess) }
}

Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match "workers\.render_worker\.main" -or
        ($_.CommandLine -match "uvicorn app\.main:app" -and $_.CommandLine -match "ai_media_assistant|apps/api") -or
        ($_.CommandLine -match "vite --host 127\.0\.0\.1" -and $_.CommandLine -match "ai_media_assistant") -or
        $_.CommandLine -match "concurrently.*api,web,worker"
    } |
    ForEach-Object { [void]$processIds.Add([int]$_.ProcessId) }

foreach ($processId in $processIds) {
    if ($processId -gt 0 -and $processId -ne $PID) {
        Stop-Process -Id $processId -Force
    }
}

Start-Sleep -Milliseconds 500
