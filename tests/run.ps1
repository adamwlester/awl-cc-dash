<#
.SYNOPSIS
    Run the test suite (pytest) with the local .venv.

.DESCRIPTION
    Resolves the local .venv, then runs pytest against this tests/ directory.
    Console output is concise; a full DEBUG log is written to
    tests/log/<timestamped>.log (configured in conftest.py).

    Any extra arguments are passed straight through to pytest.

.EXAMPLE
    .\run.ps1                          # run everything in tests/
    .\run.ps1 -k mcp_sync              # run a single test by keyword
    .\run.ps1 -m "integration"         # run by marker
#>

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$repoRoot = Split-Path $here -Parent
$py = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "ERROR: venv python not found at $py" -ForegroundColor Red
    Write-Host "       Create it: python -m venv .venv; .venv\Scripts\python -m pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "=== Workspace Test Suite (pytest) ===" -ForegroundColor Cyan
Write-Host "  Python : $py"
Write-Host "  Time   : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "  Logs   : $(Join-Path $here 'log')"
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

& $py -m pytest $here @args
exit $LASTEXITCODE
