$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pidFile = Join-Path $projectRoot "data\qdrant-server\qdrant.pid"

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Output "Qdrant PID file does not exist; nothing to stop."
    exit 0
}

$qdrantPid = [int](Get-Content -LiteralPath $pidFile -Raw)
$process = Get-Process -Id $qdrantPid -ErrorAction SilentlyContinue
if ($process -and $process.ProcessName -eq "qdrant") {
    Stop-Process -Id $qdrantPid
    $process.WaitForExit(10000)
    Write-Output "Qdrant Server stopped, PID=$qdrantPid"
} else {
    Write-Output "Recorded Qdrant process is no longer running."
}

Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
