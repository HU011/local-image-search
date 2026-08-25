$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$qdrantExe = Join-Path $projectRoot "tools\qdrant\bin\qdrant.exe"
$configPath = Join-Path $projectRoot "config\qdrant-server.yaml"
$runtimeDir = Join-Path $projectRoot "data\qdrant-server"
$logDir = Join-Path $projectRoot "logs"
$pidFile = Join-Path $runtimeDir "qdrant.pid"
$importDir = Join-Path $runtimeDir "import"

function Get-DotEnvValue {
    param(
        [string]$Name,
        [string]$DefaultValue
    )

    $processValue = [Environment]::GetEnvironmentVariable($Name, "Process")
    if (-not [string]::IsNullOrWhiteSpace($processValue)) {
        return $processValue
    }

    $envPath = Join-Path $projectRoot ".env"
    if (Test-Path -LiteralPath $envPath) {
        $line = Get-Content -LiteralPath $envPath -Encoding UTF8 |
            Where-Object { $_ -match "^\s*$Name\s*=" } |
            Select-Object -Last 1
        if ($line) {
            $value = ($line -split "=", 2)[1].Trim()
            return $value.Trim('"').Trim("'")
        }
    }

    return $DefaultValue
}

$collectionName = Get-DotEnvValue -Name "QDRANT_COLLECTION" -DefaultValue "local_image_search_images"
$storageCollection = Join-Path $runtimeDir "storage\collections\$collectionName"

if (-not (Test-Path -LiteralPath $qdrantExe)) {
    throw "Qdrant executable not found: $qdrantExe"
}

$listener = Get-NetTCPConnection -LocalPort 6335 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Write-Output "Qdrant Server is already listening on 127.0.0.1:6335"
    exit 0
}

New-Item -ItemType Directory -Path $runtimeDir, $logDir -Force | Out-Null
$stdoutLog = Join-Path $logDir "qdrant-server.stdout.log"
$stderrLog = Join-Path $logDir "qdrant-server.stderr.log"
$arguments = @("--config-path", $configPath, "--disable-telemetry")
$restoringSnapshot = $false

if (-not (Test-Path -LiteralPath $storageCollection)) {
    $snapshot = Get-ChildItem -LiteralPath $importDir -File -Filter "*.snapshot" -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($snapshot) {
        $relativeSnapshot = "data/qdrant-server/import/$($snapshot.Name)"
        $arguments += @("--snapshot", "$relativeSnapshot`:$collectionName")
        $restoringSnapshot = $true
        Write-Output "First run: restoring Qdrant snapshot $($snapshot.Name) into $collectionName"
    } else {
        Write-Output "No existing Qdrant collection or snapshot found; starting with empty storage."
    }
}

$process = Start-Process `
    -FilePath $qdrantExe `
    -ArgumentList $arguments `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

Set-Content -LiteralPath $pidFile -Value $process.Id -Encoding ascii

$maxAttempts = if ($restoringSnapshot) { 600 } else { 30 }
for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    try {
        $response = Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "http://127.0.0.1:6335/healthz" `
            -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            if (-not $restoringSnapshot) {
                Write-Output "Qdrant Server started, PID=$($process.Id)"
                exit 0
            }
            try {
                $collection = Invoke-RestMethod `
                    -Uri "http://127.0.0.1:6335/collections/$collectionName" `
                    -TimeoutSec 5
                if ($collection.result.points_count -gt 0) {
                    Write-Output "Qdrant snapshot restored, collection=$collectionName, points=$($collection.result.points_count), PID=$($process.Id)"
                    exit 0
                }
            } catch {
                # Qdrant is healthy while snapshot recovery is still in progress.
            }
        }
    } catch {
        Start-Sleep -Seconds 1
    }

    if ($process.HasExited) {
        throw "Qdrant Server exited during startup. See $stderrLog"
    }
}

throw "Qdrant Server did not become ready within $maxAttempts seconds."
