#
# CoCo Windows Setup Script
# =========================
# This script sets up the CoCo campus information kiosk on Windows.
#
# Usage: .\win-setup.ps1
#
# Note: Run PowerShell as Administrator if you encounter permission issues.
#

# Stop on error
$ErrorActionPreference = "Stop"

# Colors for output
function Write-Success { param($msg) Write-Host $msg -ForegroundColor Green }
function Write-Warning { param($msg) Write-Host $msg -ForegroundColor Yellow }
function Write-Error { param($msg) Write-Host $msg -ForegroundColor Red }
function Write-Info { param($msg) Write-Host $msg -ForegroundColor Cyan }

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  CoCo Campus Kiosk - Windows Setup" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory (project root)
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Join-Path $ProjectRoot "campus_rag_chatbot"

Write-Host "Project root: $ProjectRoot"
Write-Host "App directory: $AppDir"
Write-Host ""

# Step 1: Check Python version
Write-Warning "[1/6] Checking Python version..."

$PythonCmd = $null
$PythonVersion = $null

# Try Python 3.11 first (preferred for Piper TTS)
try {
    $py311 = & py -3.11 --version 2>&1
    if ($py311 -match "Python 3\.11") {
        $PythonCmd = "py -3.11"
        $PythonVersion = $py311
        Write-Success "Python 3.11 found ($PythonVersion) - recommended for Piper TTS"
    }
} catch {}

# Fall back to python command
if (-not $PythonCmd) {
    try {
        $pyVer = & python --version 2>&1
        if ($pyVer -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 8) {
                $PythonCmd = "python"
                $PythonVersion = $pyVer
                Write-Warning "$PythonVersion found (3.11 recommended for Piper TTS)"
            }
        }
    } catch {}
}

# Try py launcher as last resort
if (-not $PythonCmd) {
    try {
        $pyVer = & py --version 2>&1
        if ($pyVer -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 8) {
                $PythonCmd = "py"
                $PythonVersion = $pyVer
                Write-Warning "$PythonVersion found (3.11 recommended for Piper TTS)"
            }
        }
    } catch {}
}

if (-not $PythonCmd) {
    Write-Error "Error: Python 3.8+ required but not found."
    Write-Host "Please install Python 3.11 from https://www.python.org/downloads/"
    exit 1
}

Write-Host ""

# Step 2: Create virtual environment
Write-Warning "[2/6] Creating virtual environment..."
$VenvDir = Join-Path $ProjectRoot "venv"

if (Test-Path $VenvDir) {
    Write-Host "Virtual environment already exists at $VenvDir"
    $recreate = Read-Host "Recreate it? (y/N)"
    if ($recreate -eq "y" -or $recreate -eq "Y") {
        Remove-Item -Recurse -Force $VenvDir
        & $PythonCmd -m venv $VenvDir
        Write-Success "Virtual environment recreated"
    } else {
        Write-Host "Using existing virtual environment"
    }
} else {
    & $PythonCmd -m venv $VenvDir
    Write-Success "Virtual environment created at $VenvDir"
}

Write-Host ""

# Step 3: Activate virtual environment and install dependencies
Write-Warning "[3/6] Installing dependencies..."

$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
if (-not (Test-Path $ActivateScript)) {
    Write-Error "Error: Could not find virtual environment activation script"
    exit 1
}

# Activate venv
& $ActivateScript

# Upgrade pip
Write-Host "Upgrading pip..."
& python -m pip install --upgrade pip

# Install requirements
$RequirementsFile = Join-Path $AppDir "requirements_py311.txt"
if (Test-Path $RequirementsFile) {
    Write-Host "Installing from requirements_py311.txt..."
    & pip install -r $RequirementsFile
} else {
    $RequirementsFile = Join-Path $AppDir "requirements.txt"
    Write-Host "Installing from requirements.txt..."
    & pip install -r $RequirementsFile
}

# Install Windows-specific package for libmagic
Write-Host "Installing python-magic-bin for Windows..."
& pip install python-magic-bin

Write-Success "Dependencies installed"
Write-Host ""

# Step 4: Setup environment file
Write-Warning "[4/6] Setting up environment file..."
$EnvFile = Join-Path $AppDir ".env"
$EnvExample = Join-Path $AppDir ".env.example"

if (Test-Path $EnvFile) {
    Write-Host ".env file already exists"
    $overwrite = Read-Host "Overwrite with template? (y/N)"
    if ($overwrite -eq "y" -or $overwrite -eq "Y") {
        Copy-Item $EnvExample $EnvFile -Force
        Write-Success ".env file created from template"
    } else {
        Write-Host "Keeping existing .env file"
    }
} else {
    Copy-Item $EnvExample $EnvFile
    Write-Success ".env file created from template"
}

# Generate admin API key
$AdminKey = [guid]::NewGuid().ToString()

Write-Host ""
Write-Host "==============================================" -ForegroundColor Yellow
Write-Warning "IMPORTANT: Configure your API keys"
Write-Host "==============================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "Edit the .env file:"
Write-Host "  notepad $EnvFile"
Write-Host ""
Write-Host "Required settings:"
Write-Host "  OPENAI_API_KEY=sk-your-key-here"
Write-Host "  ADMIN_API_KEY=$AdminKey"
Write-Host ""
Write-Host "(The admin key above was auto-generated for you)"
Write-Host ""

Read-Host "Press Enter when you have configured your .env file..."
Write-Host ""

# Step 5: Ingest documents
Write-Warning "[5/6] Ingesting documents..."
Push-Location $AppDir

$DocsDir = "documents_to_ingest"
$VectorStore = Join-Path $AppDir "vector_store"

if (Test-Path $VectorStore) {
    Write-Host "Vector store already exists"
    $reingest = Read-Host "Re-ingest documents? (y/N)"
    if ($reingest -eq "y" -or $reingest -eq "Y") {
        & python admin.py ingest "$DocsDir/"
    } else {
        Write-Host "Skipping document ingestion"
    }
} else {
    Write-Host "Ingesting documents from $DocsDir/..."
    & python admin.py ingest "$DocsDir/"
}

Write-Success "Document ingestion complete"
Write-Host ""

# Step 6: Test startup
Write-Warning "[6/6] Testing application startup..."
Write-Host "Starting server for quick test..."

# Start server
$job = Start-Job -ScriptBlock {
    param($appDir)
    Set-Location $appDir
    & python app.py
} -ArgumentList $AppDir

# Wait for startup
Start-Sleep -Seconds 5

# Test health endpoint
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Success "Server started successfully!"
    }
} catch {
    Write-Warning "Server may still be starting..."
}

# Stop test server
Stop-Job $job -ErrorAction SilentlyContinue
Remove-Job $job -ErrorAction SilentlyContinue

Pop-Location

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Success "  Setup Complete!"
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start the server:"
Write-Host "  cd $ProjectRoot"
Write-Host "  .\venv\Scripts\Activate.ps1"
Write-Host "  cd campus_rag_chatbot"
Write-Host "  python app.py"
Write-Host ""
Write-Host "Access the kiosk at:"
Write-Host "  http://localhost:8000/"
Write-Host ""
Write-Host "==============================================" -ForegroundColor Yellow
Write-Warning "Notes for Windows:"
Write-Host "==============================================" -ForegroundColor Yellow
Write-Host "- Voice TTS will use Edge-TTS (cloud) if Piper fails"
Write-Host "- Install ffmpeg for audio conversion: https://ffmpeg.org/download.html"
Write-Host "- Layout-aware PDF parsing may be limited without poppler"
Write-Host ""
