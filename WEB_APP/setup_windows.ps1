#
# CoCo WEB_APP - Windows Setup Script
# =====================================
# Sets up the CoCo campus information kiosk on Windows.
#
# Usage: .\WEB_APP\setup_windows.ps1
#
# Note: Run PowerShell as Administrator if you encounter permission issues.
#

$ErrorActionPreference = "Stop"

function Write-Success { param($msg) Write-Host $msg -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host $msg -ForegroundColor Yellow }
function Write-Err { param($msg) Write-Host $msg -ForegroundColor Red }

Write-Host ""
Write-Host "=============================================="  -ForegroundColor Cyan
Write-Host "  CoCo Campus Kiosk - Windows Setup"  -ForegroundColor Cyan
Write-Host "=============================================="  -ForegroundColor Cyan
Write-Host ""

# Get paths
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$ModulesDir = Join-Path $ScriptDir "modules"

Write-Host "WEB_APP:      $ScriptDir"
Write-Host "Project root: $ProjectRoot"
Write-Host ""

# ============================================
# Step 1: Check Python version
# ============================================
Write-Warn "[1/6] Checking Python version..."

$PythonCmd = $null
$PythonVersion = $null
$UsePython311 = $false

# Try Python 3.11 first
try {
    $py311 = & py -3.11 --version 2>&1
    if ($py311 -match "Python 3\.11") {
        $PythonCmd = "py -3.11"
        $PythonVersion = $py311
        $UsePython311 = $true
        Write-Success "Python 3.11 found ($PythonVersion)"
    }
} catch {}

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
Write-Warn "[2/6] Creating virtual environment..."

if ($UsePython311) {
    $VenvDir = Join-Path $ProjectRoot "venv311"
} else {
    $VenvDir = Join-Path $ProjectRoot "venv"
}

if (Test-Path $VenvDir) {
    Write-Host "Virtual environment already exists at $VenvDir"
    $recreate = Read-Host "Recreate it? (y/N)"
    if ($recreate -eq "y" -or $recreate -eq "Y") {
        Remove-Item -Recurse -Force $VenvDir
        if ($PythonCmd -eq "py -3.11") { & py -3.11 -m venv $VenvDir }
        elseif ($PythonCmd -eq "python") { & python -m venv $VenvDir }
        else { & py -m venv $VenvDir }
        Write-Success "Virtual environment recreated"
    } else {
        Write-Host "Using existing virtual environment"
    }
} else {
    if ($PythonCmd -eq "py -3.11") { & py -3.11 -m venv $VenvDir }
    elseif ($PythonCmd -eq "python") { & python -m venv $VenvDir }
    else { & py -m venv $VenvDir }
    Write-Success "Virtual environment created at $VenvDir"
}
Write-Host ""

# ============================================
# Step 3: Install dependencies
# ============================================
Write-Warn "[3/6] Installing dependencies..."

$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
if (-not (Test-Path $ActivateScript)) {
    Write-Err "Error: Could not find virtual environment activation script"
    exit 1
}

& $ActivateScript

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

Write-Host "Upgrading pip..."
& $VenvPython -m pip install --upgrade pip

$RequirementsFile = Join-Path $ScriptDir "requirements_windows.txt"
Write-Host "Installing from requirements_windows.txt (runtime-only)..."
& $VenvPip install -r $RequirementsFile

Write-Success "Dependencies installed"
Write-Host ""

# ============================================
# Step 4: Setup environment file
# ============================================
Write-Warn "[4/6] Setting up environment file..."
$EnvFile = Join-Path $ScriptDir ".env"
$EnvExample = Join-Path $ScriptDir ".env.example"

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

$AdminKey = [guid]::NewGuid().ToString()
Write-Host ""
Write-Host "=============================================="  -ForegroundColor Yellow
Write-Warn "IMPORTANT: Configure your API keys"
Write-Host "=============================================="  -ForegroundColor Yellow
Write-Host ""
Write-Host "Edit the .env file:"
Write-Host "  notepad $EnvFile"
Write-Host ""
Write-Host "Required settings:"
Write-Host "  OPENAI_API_KEY=sk-your-key-here"
Write-Host "  ADMIN_API_KEY=$AdminKey"
Write-Host ""
Read-Host "Press Enter when you have configured your .env file..."
Write-Host ""

# ============================================
# Step 5: Download voice models (optional)
# ============================================
Write-Warn "[5/6] Voice model setup..."

$VoiceScript = Join-Path $ScriptDir "download-voice-models.ps1"
if (Test-Path $VoiceScript) {
    $downloadVoice = Read-Host "Download voice models for offline STT/TTS? (~135MB) (y/N)"
    if ($downloadVoice -eq "y" -or $downloadVoice -eq "Y") {
        & $VoiceScript
    } else {
        Write-Host "Skipping voice model download"
    }
} else {
    Write-Warn "Voice model download script not found. Skipping..."
}
Write-Host ""

# ============================================
# Step 6: Verify vector store
# ============================================
Write-Warn "[6/6] Verifying vector store..."

$VectorStore = Join-Path $ModulesDir "vector_store"

if (Test-Path $VectorStore) {
    $IndexFaiss = Join-Path $VectorStore "index.faiss"
    $IndexPkl = Join-Path $VectorStore "index.pkl"

    if ((Test-Path $IndexFaiss) -and (Test-Path $IndexPkl)) {
        Write-Success "Vector store found and valid"
    } else {
        Write-Warn "Vector store incomplete."
        Write-Host "Use INGESTION_MODULE to create the vector store."
    }
} else {
    Write-Warn "No vector store found."
    Write-Host "Use INGESTION_MODULE to create the vector store."
}
Write-Host ""

# Test startup
Write-Warn "Testing application startup..."
Push-Location $ProjectRoot

$ServerProcess = Start-Process -FilePath $VenvPython -ArgumentList "-m", "WEB_APP" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 8

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 10
    if ($response.StatusCode -eq 200) {
        Write-Success "Server started successfully!"
    }
} catch {
    Write-Warn "Server may still be starting..."
}

try { Stop-Process -Id $ServerProcess.Id -Force -ErrorAction SilentlyContinue } catch {}
Pop-Location

Write-Host ""
Write-Host "=============================================="  -ForegroundColor Green
Write-Success "  Setup Complete!"
Write-Host "=============================================="  -ForegroundColor Green
Write-Host ""
Write-Host "To start the server:"
Write-Host "  cd $ProjectRoot"
if ($UsePython311) { Write-Host "  .\venv311\Scripts\Activate.ps1" }
else { Write-Host "  .\venv\Scripts\Activate.ps1" }
Write-Host "  python -m WEB_APP"
Write-Host ""
Write-Host "Access the kiosk at:"
Write-Host "  http://localhost:8000/"
Write-Host ""
