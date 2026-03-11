#
# CoCo WEB_APP - Quick Start
# ============================
# Usage: .\WEB_APP\run.ps1
#

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

# Try venv311 first, then venv
$VenvDir = Join-Path $ProjectRoot "venv311"
if (-not (Test-Path $VenvDir)) {
    $VenvDir = Join-Path $ProjectRoot "venv"
}

$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
if (Test-Path $ActivateScript) {
    & $ActivateScript
} else {
    Write-Host "Error: Virtual environment not found. Run setup_windows.ps1 first." -ForegroundColor Red
    exit 1
}

Push-Location $ProjectRoot
python -m WEB_APP
Pop-Location
