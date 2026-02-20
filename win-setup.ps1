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
function Write-Warn { param($msg) Write-Host $msg -ForegroundColor Yellow }
function Write-Err { param($msg) Write-Host $msg -ForegroundColor Red }
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

# ============================================
# Step 1: Check Python version
# ============================================
Write-Warn "[1/7] Checking Python version..."

$PythonCmd = $null
$PythonVersion = $null
$UsePython311 = $false

# Try Python 3.11 first (preferred for Piper TTS)
try {
    $py311 = & py -3.11 --version 2>&1
    if ($py311 -match "Python 3\.11") {
        $PythonCmd = "py -3.11"
        $PythonVersion = $py311
        $UsePython311 = $true
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
                if ($minor -eq 11) { $UsePython311 = $true }
                Write-Warn "$PythonVersion found (3.11 recommended for Piper TTS)"
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
                if ($minor -eq 11) { $UsePython311 = $true }
                Write-Warn "$PythonVersion found (3.11 recommended for Piper TTS)"
            }
        }
    } catch {}
}

if (-not $PythonCmd) {
    Write-Err "Error: Python 3.8+ required but not found."
    Write-Host "Please install Python 3.11 from https://www.python.org/downloads/"
    exit 1
}

Write-Host ""

# ============================================
# Step 2: Create virtual environment
# ============================================
Write-Warn "[2/7] Creating virtual environment..."

# Use venv311 for Python 3.11, venv otherwise
if ($UsePython311) {
    $VenvDir = Join-Path $ProjectRoot "venv311"
    Write-Host "Using venv311 directory for Python 3.11"
} else {
    $VenvDir = Join-Path $ProjectRoot "venv"
    Write-Host "Using venv directory"
}

if (Test-Path $VenvDir) {
    Write-Host "Virtual environment already exists at $VenvDir"
    $recreate = Read-Host "Recreate it? (y/N)"
    if ($recreate -eq "y" -or $recreate -eq "Y") {
        Remove-Item -Recurse -Force $VenvDir
        if ($PythonCmd -eq "py -3.11") {
            & py -3.11 -m venv $VenvDir
        } elseif ($PythonCmd -eq "python") {
            & python -m venv $VenvDir
        } else {
            & py -m venv $VenvDir
        }
        Write-Success "Virtual environment recreated"
    } else {
        Write-Host "Using existing virtual environment"
    }
} else {
    if ($PythonCmd -eq "py -3.11") {
        & py -3.11 -m venv $VenvDir
    } elseif ($PythonCmd -eq "python") {
        & python -m venv $VenvDir
    } else {
        & py -m venv $VenvDir
    }
    Write-Success "Virtual environment created at $VenvDir"
}

Write-Host ""

# ============================================
# Step 3: Install dependencies
# ============================================
Write-Warn "[3/7] Installing dependencies..."

$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
if (-not (Test-Path $ActivateScript)) {
    Write-Err "Error: Could not find virtual environment activation script"
    exit 1
}

# Activate venv
& $ActivateScript

# Get the venv python path for explicit use
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

# Upgrade pip
Write-Host "Upgrading pip..."
& $VenvPython -m pip install --upgrade pip

# Install requirements
$RequirementsFile = Join-Path $AppDir "requirements.txt"
Write-Host "Installing from requirements.txt..."
& $VenvPip install -r $RequirementsFile

# Install edge-tts for cloud TTS fallback
Write-Host "Installing edge-tts for cloud TTS..."
& $VenvPip install edge-tts

Write-Success "Dependencies installed"
Write-Host ""

# ============================================
# Step 4: Setup environment file
# ============================================
Write-Warn "[4/7] Setting up environment file..."
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
Write-Warn "IMPORTANT: Configure your API keys"
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

# ============================================
# Step 5: Download voice models (optional)
# ============================================
Write-Warn "[5/7] Voice model setup..."

$VoiceScript = Join-Path $ProjectRoot "download-voice-models.ps1"
if (Test-Path $VoiceScript) {
    $downloadVoice = Read-Host "Download voice models for offline STT/TTS? (~135MB) (y/N)"
    if ($downloadVoice -eq "y" -or $downloadVoice -eq "Y") {
        & $VoiceScript
    } else {
        Write-Host "Skipping voice model download"
        Write-Warn "Note: Voice will use cloud fallback (edge-tts) if models not present"
    }
} else {
    Write-Warn "Voice model download script not found. Skipping..."
}
Write-Host ""

# ============================================
# Step 6: Verify or ingest documents
# ============================================
Write-Warn "[6/7] Document setup..."
Push-Location $AppDir

$VectorStore = Join-Path $AppDir "vector_store"
$DocsDir = Join-Path $AppDir "documents_to_ingest"

if (Test-Path $VectorStore) {
    # Check for essential files
    $IndexFaiss = Join-Path $VectorStore "index.faiss"
    $IndexPkl = Join-Path $VectorStore "index.pkl"

    if ((Test-Path $IndexFaiss) -and (Test-Path $IndexPkl)) {
        Write-Success "Vector store found and valid"
        $reingest = Read-Host "Re-ingest documents? (y/N)"
        if ($reingest -eq "y" -or $reingest -eq "Y") {
            & $VenvPython admin.py ingest "$DocsDir/"
        } else {
            Write-Host "Using existing vector store"
        }
    } else {
        Write-Warn "Vector store incomplete. Running ingestion..."
        & $VenvPython admin.py ingest "$DocsDir/"
    }
} else {
    Write-Host "No vector store found. Running document ingestion..."
    if (Test-Path $DocsDir) {
        & $VenvPython admin.py ingest "$DocsDir/"
        Write-Success "Document ingestion complete"
    } else {
        Write-Err "Error: documents_to_ingest directory not found"
        Write-Host "Create the directory and add documents, then run:"
        Write-Host "  python admin.py ingest documents_to_ingest/"
    }
}

Pop-Location
Write-Host ""

# ============================================
# Step 7: Test startup
# ============================================
Write-Warn "[7/7] Testing application startup..."
Write-Host "Starting server for quick test..."

Push-Location $AppDir

# Start server as a background process
$ServerProcess = Start-Process -FilePath $VenvPython -ArgumentList "app.py" -PassThru -WindowStyle Hidden

# Wait for startup
Start-Sleep -Seconds 8

# Test health endpoint
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 10
    if ($response.StatusCode -eq 200) {
        Write-Success "Server started successfully!"
        $health = $response.Content | ConvertFrom-Json
        Write-Host "  - Documents loaded: $($health.documents_loaded)"
        Write-Host "  - Status: $($health.status)"
    }
} catch {
    Write-Warn "Server may still be starting or encountered an issue..."
    Write-Host "Check the console output when running manually."
}

# Stop test server
try {
    Stop-Process -Id $ServerProcess.Id -Force -ErrorAction SilentlyContinue
} catch {}

Pop-Location

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Success "  Setup Complete!"
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start the server:"
Write-Host "  cd $ProjectRoot"
if ($UsePython311) {
    Write-Host "  .\venv311\Scripts\Activate.ps1"
} else {
    Write-Host "  .\venv\Scripts\Activate.ps1"
}
Write-Host "  cd campus_rag_chatbot"
Write-Host "  python app.py"
Write-Host ""
Write-Host "Or use the convenience script:"
Write-Host "  .\run.ps1"
Write-Host ""
Write-Host "Access the kiosk at:"
Write-Host "  http://localhost:8000/"
Write-Host ""
Write-Host "==============================================" -ForegroundColor Yellow
Write-Warn "Notes for Windows:"
Write-Host "==============================================" -ForegroundColor Yellow
Write-Host "- Voice TTS will use Edge-TTS (cloud) if Piper fails"
Write-Host "- Voice STT can use Google Cloud or Whisper.cpp"
Write-Host "- Install ffmpeg for audio conversion: https://ffmpeg.org/download.html"
Write-Host "- Layout-aware PDF parsing may be limited without poppler"
Write-Host ""
