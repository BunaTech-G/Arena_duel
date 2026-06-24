param(
    [string]$ServerHost = "165.232.108.225",
    [int]$Port = 27015,
    [string]$Scenario = "end-match",
    [int[]]$Durations = @(30, 45, 60, 90, 120, 180),
    [double]$Timeout = 8.0,
    [double]$MatchTimeout = 240.0,
    [string]$PseudoPrefix = "smoke",
    [switch]$StopOnFailure,
    [switch]$DryRun
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$toolPath = Join-Path $projectRoot "tools\test_online_client.py"

if (-not (Test-Path $toolPath)) {
    throw "Outil introuvable: $toolPath"
}

if (-not (Test-Path $pythonPath)) {
    $pythonPath = "python"
}

$results = New-Object System.Collections.Generic.List[object]

foreach ($duration in $Durations) {
    $pseudo = "{0}{1}" -f $PseudoPrefix, $duration
    $commandArgs = @(
        $toolPath,
        "--scenario", $Scenario,
        "--host", $ServerHost,
        "--port", "$Port",
        "--pseudo", $pseudo,
        "--timeout", "$Timeout",
        "--match-timeout", "$MatchTimeout",
        "--match-duration", "$duration"
    )

    $displayArgs = $commandArgs | ForEach-Object {
        if ($_ -match "\s") {
            '"{0}"' -f $_
        }
        else {
            $_
        }
    }

    Write-Host ""
    Write-Host ("=== Smoke {0}s ===" -f $duration)
    Write-Host ("{0} {1}" -f $pythonPath, ($displayArgs -join " "))

    if ($DryRun) {
        $results.Add([pscustomobject]@{
                Duration = $duration
                ExitCode = $null
                Status   = "dry-run"
            }) | Out-Null
        continue
    }

    & $pythonPath @commandArgs
    $exitCode = $LASTEXITCODE
    $status = if ($exitCode -eq 0) { "ok" } else { "failed" }

    $results.Add([pscustomobject]@{
            Duration = $duration
            ExitCode = $exitCode
            Status   = $status
        }) | Out-Null

    if ($exitCode -ne 0 -and $StopOnFailure) {
        Write-Host ""
        Write-Host "Arret sur premier echec."
        $results | Format-Table -AutoSize | Out-Host
        exit $exitCode
    }
}

Write-Host ""
$results | Format-Table -AutoSize | Out-Host

$failedResults = $results | Where-Object { $_.ExitCode -ne $null -and $_.ExitCode -ne 0 }
if ($failedResults.Count -gt 0) {
    exit 1
}

exit 0