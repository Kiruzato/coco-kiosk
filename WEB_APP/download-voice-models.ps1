#
# CoCo Voice Model Download Script (Windows)
# ==========================================
# Downloads STT and TTS models for offline voice support.
#
# Usage: .\download-voice-models.ps1
#
# Models downloaded:
#   - Whisper tiny.en (STT): ~75MB
#   - Piper amy-medium (TTS): ~60MB
#

$ErrorActionPreference = "Stop"

# Colors for output
function Write-Success { param($msg) Write-Host $msg -ForegroundColor Green }
function Write-Warning { param($msg) Write-Host $msg -ForegroundColor Yellow }
function Write-Error { param($msg) Write-Host $msg -ForegroundColor Red }
function Write-Info { param($msg) Write-Host $msg -ForegroundColor Cyan }

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  CoCo Voice Model Download" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VoiceModelsDir = Join-Path $ScriptDir "campus_rag_chatbot\voice\models"

# Create directories
$WhisperDir = Join-Path $VoiceModelsDir "whisper"
$PiperDir = Join-Path $VoiceModelsDir "piper"

if (-not (Test-Path $WhisperDir)) {
    New-Item -ItemType Directory -Path $WhisperDir -Force | Out-Null
}
if (-not (Test-Path $PiperDir)) {
    New-Item -ItemType Directory -Path $PiperDir -Force | Out-Null
}

Write-Host "Models will be downloaded to: $VoiceModelsDir"
Write-Host ""

# ============================================
# Whisper STT Model (tiny.en - optimized for English, fast)
# ============================================
Write-Warning "[1/2] Downloading Whisper STT model..."

$WhisperModel = "ggml-tiny.en.bin"
$WhisperUrl = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$WhisperModel"
$WhisperPath = Join-Path $WhisperDir $WhisperModel

if (Test-Path $WhisperPath) {
    Write-Host "Whisper model already exists: $WhisperPath"
    $redownload = Read-Host "Re-download? (y/N)"
    if ($redownload -ne "y" -and $redownload -ne "Y") {
        Write-Host "Skipping Whisper download"
    } else {
        Remove-Item $WhisperPath -Force
        Write-Host "Downloading $WhisperModel (~75MB)..."
        Invoke-WebRequest -Uri $WhisperUrl -OutFile $WhisperPath -UseBasicParsing
        Write-Success "Whisper model downloaded"
    }
} else {
    Write-Host "Downloading $WhisperModel (~75MB)..."
    Invoke-WebRequest -Uri $WhisperUrl -OutFile $WhisperPath -UseBasicParsing
    Write-Success "Whisper model downloaded"
}
Write-Host ""

# ============================================
# Piper TTS Model (amy-medium - natural female US English voice)
# ============================================
Write-Warning "[2/2] Downloading Piper TTS model..."

$PiperModel = "en_US-amy-medium"
$PiperBaseUrl = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium"
$PiperOnnx = "$PiperModel.onnx"
$PiperJson = "$PiperModel.onnx.json"
$PiperPathOnnx = Join-Path $PiperDir $PiperOnnx
$PiperPathJson = Join-Path $PiperDir $PiperJson

if ((Test-Path $PiperPathOnnx) -and (Test-Path $PiperPathJson)) {
    Write-Host "Piper model already exists: $PiperPathOnnx"
    $redownload = Read-Host "Re-download? (y/N)"
    if ($redownload -ne "y" -and $redownload -ne "Y") {
        Write-Host "Skipping Piper download"
    } else {
        Remove-Item $PiperPathOnnx -Force
        Remove-Item $PiperPathJson -Force
        Write-Host "Downloading $PiperOnnx (~60MB)..."
        Invoke-WebRequest -Uri "$PiperBaseUrl/$PiperOnnx" -OutFile $PiperPathOnnx -UseBasicParsing
        Write-Host "Downloading $PiperJson..."
        Invoke-WebRequest -Uri "$PiperBaseUrl/$PiperJson" -OutFile $PiperPathJson -UseBasicParsing
        Write-Success "Piper model downloaded"
    }
} else {
    Write-Host "Downloading $PiperOnnx (~60MB)..."
    Invoke-WebRequest -Uri "$PiperBaseUrl/$PiperOnnx" -OutFile $PiperPathOnnx -UseBasicParsing
    Write-Host "Downloading $PiperJson..."
    Invoke-WebRequest -Uri "$PiperBaseUrl/$PiperJson" -OutFile $PiperPathJson -UseBasicParsing
    Write-Success "Piper model downloaded"
}
Write-Host ""

# ============================================
# Verify downloads
# ============================================
Write-Warning "Verifying downloads..."

$Missing = $false

if (-not (Test-Path $WhisperPath)) {
    Write-Error "Missing: $WhisperPath"
    $Missing = $true
}

if (-not (Test-Path $PiperPathOnnx)) {
    Write-Error "Missing: $PiperPathOnnx"
    $Missing = $true
}

if (-not (Test-Path $PiperPathJson)) {
    Write-Error "Missing: $PiperPathJson"
    $Missing = $true
}

if ($Missing) {
    Write-Host ""
    Write-Error "Some models failed to download. Check your internet connection and try again."
    exit 1
}

Write-Host ""
Write-Success "All voice models downloaded successfully!"
Write-Host ""
Write-Host "Models installed:"
Write-Host "  STT: $WhisperPath"
Write-Host "  TTS: $PiperPathOnnx"
Write-Host "  TTS config: $PiperPathJson"
Write-Host ""
Write-Host "Total size: ~135MB"
Write-Host ""
