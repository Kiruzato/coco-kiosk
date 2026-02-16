#
# CoCo Quick Start Script (Windows)
# ==================================
# Activates the virtual environment and starts the server.
#
# Usage: .\run.ps1
#

$ErrorActionPreference = "Stop"

# Get script directory (project root)
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Join-Path $ProjectRoot "campus_rag_chatbot"

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  CoCo Campus Kiosk - Starting Server" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# Find virtual environment (prefer venv311)
$VenvDir = $null
$Venv311 = Join-Path $ProjectRoot "venv311"
$Venv = Join-Path $ProjectRoot "venv"

if (Test-Path $Venv311) {
    $VenvDir = $Venv311
    Write-Host "Using Python 3.11 virtual environment (venv311)"
} elseif (Test-Path $Venv) {
    $VenvDir = $Venv
    Write-Host "Using virtual environment (venv)"
} else {
    Write-Host "Error: No virtual environment found." -ForegroundColor Red
    Write-Host ""
    Write-Host "Run the setup script first:"
    Write-Host "  .\win-setup.ps1"
    exit 1
}

# Get Python executable
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Error: Python not found in virtual environment." -ForegroundColor Red
    Write-Host "Run the setup script to recreate:"
    Write-Host "  .\win-setup.ps1"
    exit 1
}

# Check .env file
$EnvFile = Join-Path $AppDir ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Host "Warning: .env file not found." -ForegroundColor Yellow
    Write-Host "Copy .env.example to .env and configure your API keys."
    Write-Host ""
}

# Change to app directory and start
Write-Host ""
Write-Host "Starting server..."
Write-Host "  Access: http://localhost:8000/"
Write-Host "  Admin:  http://localhost:8000/admin"
Write-Host "  Dev:    http://localhost:8000/dev"
Write-Host ""
Write-Host "Press Ctrl+C to stop the server"
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

Push-Location $AppDir
try {
    & $VenvPython app.py
} finally {
    Pop-Location
}
