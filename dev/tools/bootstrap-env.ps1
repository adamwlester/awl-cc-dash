<#
.SYNOPSIS
    Bootstrap a Python virtual environment for a Claude Agent SDK project.

.DESCRIPTION
    Creates a venv named <project-folder>-env in the current directory,
    installs claude-agent-sdk (and any other standard packages), and
    verifies the installation. Safe to re-run -- skips creation if the
    venv already exists.

.USAGE
    cd C:\Users\lester\MeDocuments\AppData\Anthropic\my-project
    .\tools\bootstrap-env.ps1

    Or from anywhere:
    .\tools\bootstrap-env.ps1 -ProjectPath "C:\path\to\project"
    E.g.:
    .\tools\bootstrap-env.ps1 -ProjectPath "C:\Users\lester\MeDocuments\AppData\Anthropic\claude-code-sandbox"

.PARAMETER ProjectPath
    Optional. Defaults to the parent of the directory containing this script.

.PARAMETER Force
    If set, deletes and recreates the venv even if it already exists.
#>

param(
    [string]$ProjectPath = (Split-Path $PSScriptRoot -Parent),
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -- Resolve project name and venv path --
$ProjectPath = (Resolve-Path $ProjectPath).Path
$ProjectName = (Split-Path $ProjectPath -Leaf)
$EnvName     = "$ProjectName-env"
$EnvPath     = Join-Path $ProjectPath $EnvName
$ActivatePS  = Join-Path $EnvPath "Scripts\Activate.ps1"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Claude Agent SDK -- Environment Bootstrap" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Project : $ProjectName" -ForegroundColor White
Write-Host "  Path    : $ProjectPath" -ForegroundColor White
Write-Host "  Env     : $EnvName" -ForegroundColor White
Write-Host ""

# -- Check for uv (preferred) or fall back to python -m venv --
$useUv = $null -ne (Get-Command uv -ErrorAction SilentlyContinue)

# -- Handle existing venv --
if (Test-Path $EnvPath) {
    if ($Force) {
        Write-Host "  [~] Removing existing venv (--Force)..." -ForegroundColor Yellow
        Remove-Item $EnvPath -Recurse -Force
    } else {
        Write-Host "  [OK] Venv already exists: $EnvName" -ForegroundColor Green
        Write-Host "       Use -Force to recreate from scratch." -ForegroundColor DarkGray
        Write-Host ""
    }
}

# -- Create venv --
if (-not (Test-Path $EnvPath)) {
    if ($useUv) {
        Write-Host "  [1/3] Creating venv with uv..." -ForegroundColor Cyan
        uv venv $EnvPath --python python3.12
    } else {
        Write-Host "  [1/3] Creating venv with python -m venv..." -ForegroundColor Cyan
        python -m venv $EnvPath
    }

    if (-not (Test-Path $ActivatePS)) {
        Write-Host "  [FAIL] Venv creation failed -- Activate.ps1 not found." -ForegroundColor Red
        exit 1
    }
    Write-Host "  [OK] Venv created: $EnvName" -ForegroundColor Green
} else {
    Write-Host "  [1/3] Skipped (venv exists)" -ForegroundColor DarkGray
}

# -- Install packages --
Write-Host "  [2/3] Installing packages..." -ForegroundColor Cyan

# Activate the venv for this session
& $ActivatePS

# Read packages from requirements.txt in project root
$reqFile = Join-Path $ProjectPath "requirements.txt"

if (-not (Test-Path $reqFile)) {
    Write-Host "  [FAIL] requirements.txt not found at: $reqFile" -ForegroundColor Red
    Write-Host "         Create one with package names, one per line." -ForegroundColor Yellow
    exit 1
}

Write-Host "  Reading: requirements.txt" -ForegroundColor DarkGray

if ($useUv) {
    uv pip install -r $reqFile
} else {
    pip install --upgrade pip | Out-Null
    pip install -r $reqFile
}

Write-Host "  [OK] Packages installed" -ForegroundColor Green

# -- Verify installation via temp script --
Write-Host "  [3/3] Verifying..." -ForegroundColor Cyan

$verifyPy = Join-Path $ProjectPath "_verify_env.py"

@'
import sys
import importlib
import shutil

print("  Python  : " + sys.version.split()[0])
print("  Prefix  : " + sys.prefix)

try:
    sdk = importlib.import_module("claude_agent_sdk")
    ver = getattr(sdk, "__version__", "installed (no __version__ attr)")
    print("  SDK ver : " + str(ver))
except ImportError as e:
    print("  SDK     : IMPORT FAILED - " + str(e))
    sys.exit(1)

cli = shutil.which("claude")
print("  claude  : " + (cli if cli else "(not on PATH)"))
'@ | Set-Content -Path $verifyPy -Encoding UTF8

python $verifyPy
$verifyExit = $LASTEXITCODE

Remove-Item $verifyPy -Force -ErrorAction SilentlyContinue

if ($verifyExit -ne 0) {
    Write-Host "  [FAIL] Verification failed." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "  [OK] All good! Environment ready." -ForegroundColor Green
Write-Host ""
Write-Host "  To activate in a new terminal:" -ForegroundColor White
Write-Host "    cd `"$ProjectPath`"" -ForegroundColor Yellow
Write-Host "    .\$EnvName\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host ""