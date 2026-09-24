#Requires -Version 5.1
<#
.SYNOPSIS
    Runs the WIDDX test suite in small, isolated batches with a hard timeout.

.DESCRIPTION
    Every batch is a separate `python` process. If a batch hangs, its entire
    process tree is killed and the run continues, so one stuck test can never
    freeze the session or force a restart.

    Results are written to .widdx\test_batches.json after each batch, so an
    interrupted run can be continued with -Resume.

.PARAMETER BatchSize
    Number of test files per batch. Default 10.

.PARAMETER TimeoutSec
    Hard timeout per batch in seconds. Default 420 (7 min).

.PARAMETER Resume
    Skip batches that already passed in a previous run.

.PARAMETER ListOnly
    Print the batch plan and exit without running anything.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\run_tests_batched.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\run_tests_batched.ps1 -Resume
#>
[CmdletBinding()]
param(
    [ValidateRange(1, 50)][int]$BatchSize = 10,
    [ValidateRange(30, 3600)][int]$TimeoutSec = 420,
    [string]$ProjectRoot = '',
    [switch]$Resume,
    [switch]$ListOnly
)

$ErrorActionPreference = 'Stop'

# $PSScriptRoot is not available in param() defaults on Windows PowerShell 5.1
if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}

$testDir   = Join-Path $ProjectRoot 'tests'
$stateFile = Join-Path $ProjectRoot '.widdx\test_batches.json'
$logDir    = Join-Path $env:TEMP 'widdx-test-batches'

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $stateFile) | Out-Null

$files = @(Get-ChildItem -Path $testDir -Filter 'test_*.py' |
    Sort-Object Name | ForEach-Object { $_.FullName })

if ($files.Count -eq 0) { throw "No test_*.py files under $testDir" }

$batches = @()
for ($i = 0; $i -lt $files.Count; $i += $BatchSize) {
    $end = [Math]::Min($i + $BatchSize, $files.Count)
    $batches += , @($files[$i..($end - 1)])
}

Write-Host ("Test files : {0}" -f $files.Count)
Write-Host ("Batches    : {0} (size {1})" -f $batches.Count, $BatchSize)
Write-Host ("Timeout    : {0}s per batch" -f $TimeoutSec)
Write-Host ("Logs       : {0}" -f $logDir)
Write-Host ''

if ($ListOnly) {
    for ($b = 0; $b -lt $batches.Count; $b++) {
        $names = ($batches[$b] | ForEach-Object { Split-Path -Leaf $_ }) -join ', '
        Write-Host ("[{0,2}] {1}" -f ($b + 1), $names)
    }
    return
}

$alreadyPassed = @{}
if ($Resume -and (Test-Path -LiteralPath $stateFile)) {
    try {
        $raw = Get-Content -LiteralPath $stateFile -Raw
        $prev = $raw | ConvertFrom-Json
        foreach ($r in @($prev)) {
            if ($r.status -eq 'passed') { $alreadyPassed[$r.key] = $true }
        }
        Write-Host ("Resume    : {0} batch(es) already passed" -f $alreadyPassed.Count)
    } catch {
        Write-Host 'Resume    : previous state unreadable, starting fresh'
    }
    Write-Host ''
}

$results   = @()
$failCount = 0
$timeouts  = 0
$overall   = [Diagnostics.Stopwatch]::StartNew()

for ($b = 0; $b -lt $batches.Count; $b++) {

    $batch = $batches[$b]
    $key   = ($batch | ForEach-Object { Split-Path -Leaf $_ }) -join '|'
    $label = 'batch {0}/{1}' -f ($b + 1), $batches.Count
    $names = ($batch | ForEach-Object { Split-Path -Leaf $_ }) -join ', '

    if ($alreadyPassed.ContainsKey($key)) {
        Write-Host ('[SKIP] {0} — {1}' -f $label, $names)
        $results += [pscustomobject]@{
            batch = $b + 1; key = $key; status = 'passed'; exit = 0
            seconds = 0; log = ''
        }
        continue
    }

    $outFile = Join-Path $logDir ('batch_{0:d2}.out.txt' -f ($b + 1))
    $errFile = Join-Path $logDir ('batch_{0:d2}.err.txt' -f ($b + 1))
    $codeFile = Join-Path $logDir ('batch_{0:d2}.code.txt' -f ($b + 1))
    if (Test-Path -LiteralPath $codeFile) { Remove-Item -LiteralPath $codeFile -Force }

    $sw = [Diagnostics.Stopwatch]::StartNew()

    # A .cmd shim writes pytest's exit code to a file. Reading it from disk is
    # far more reliable than Start-Process .ExitCode on Windows PowerShell 5.1.
    $shim = Join-Path $logDir ('batch_{0:d2}.cmd' -f ($b + 1))
    $quoted = ($batch | ForEach-Object { '"' + $_ + '"' }) -join ' '
    $shimBody = "@echo off`r`n" +
        "cd /d `"$ProjectRoot`"`r`n" +
        "python -m pytest $quoted -q --no-cov -p no:cacheprovider`r`n" +
        "echo %ERRORLEVEL% > `"$codeFile`"`r`n"
    Set-Content -LiteralPath $shim -Value $shimBody -Encoding ascii

    $proc = Start-Process -FilePath $shim -NoNewWindow -PassThru `
        -RedirectStandardOutput $outFile -RedirectStandardError $errFile

    $exited = $proc.WaitForExit($TimeoutSec * 1000)
    $sw.Stop()
    $status = 'passed'
    $code   = 0

    if (-not $exited) {
        $status  = 'timeout'
        $timeouts++
        $code    = -1
        # taskkill writes to stderr; suppress so it does not abort the script
        cmd /c "taskkill /PID $($proc.Id) /T /F" 2>$null | Out-Null
        try { $proc.WaitForExit(15000) | Out-Null } catch { }
        Write-Host ('[TIME ] {0} ({1,5:N0}s) — {2}' -f $label, $sw.Elapsed.TotalSeconds, $names)
        Write-Host ('        process tree killed; log: {0}' -f $outFile)
    } else {
        $code = 1
        if (Test-Path -LiteralPath $codeFile) {
            $raw = (Get-Content -LiteralPath $codeFile -Raw).Trim()
            $parsed = 0
            if ([int]::TryParse($raw, [ref]$parsed)) { $code = $parsed }
        }
        if ($code -eq 0) {
            $status = 'passed'
        } else {
            $status  = 'failed'
            $failCount++
        }

        $summary = ''
        if (Test-Path -LiteralPath $outFile) {
            $summary = Get-Content -LiteralPath $outFile |
                Where-Object { $_ -match '(passed|failed|error|no tests ran).*in\s' } |
                Select-Object -Last 1
        }
        if ($summary) {
            Write-Host ('[{0,-5}] {1} ({2,5:N0}s) — {3}' -f $status.ToUpper(), $label, $sw.Elapsed.TotalSeconds, $summary.Trim())
        } else {
            Write-Host ('[{0,-5}] {1} ({2,5:N0}s) — {3}' -f $status.ToUpper(), $label, $sw.Elapsed.TotalSeconds, $names)
        }
        if ($status -eq 'failed') {
            Write-Host ('        log: {0}' -f $outFile)
        }
    }

    $results += [pscustomobject]@{
        batch   = $b + 1
        key     = $key
        status  = $status
        exit    = $code
        seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1)
        log     = $outFile
    }

    # persist after every batch so an interrupted run can resume
    ($results | ConvertTo-Json -Depth 4) |
        Out-File -LiteralPath $stateFile -Encoding ascii
}

$overall.Stop()
$passCount = @($results | Where-Object { $_.status -eq 'passed' }).Count

Write-Host ''
Write-Host '================ SUMMARY ================'
Write-Host ('batches : {0}' -f $results.Count)
Write-Host ('passed  : {0}' -f $passCount)
Write-Host ('failed  : {0}' -f $failCount)
Write-Host ('timeout : {0}' -f $timeouts)
Write-Host ('elapsed : {0:N0}s' -f $overall.Elapsed.TotalSeconds)
Write-Host ('state   : {0}' -f $stateFile)
if ($failCount -gt 0 -or $timeouts -gt 0) {
    Write-Host ''
    Write-Host 'Failing batches:'
    $results | Where-Object { $_.status -ne 'passed' } |
        ForEach-Object { Write-Host ('  batch {0}: {1} — {2}' -f $_.batch, $_.status, $_.log) }
}

if ($failCount -gt 0 -or $timeouts -gt 0) { exit 1 }
exit 0
