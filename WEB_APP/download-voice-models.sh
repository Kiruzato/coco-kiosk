#!/bin/bash
#
# CoCo Voice Model Download Script
# =================================
# Downloads STT and TTS models for offline voice support.
#
# Usage: ./download-voice-models.sh
#
# Models downloaded:
#   - Whisper tiny.en (STT): ~75MB
#   - Piper amy-medium (TTS): ~60MB
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "=============================================="
echo "  CoCo Voice Model Download"
echo "=============================================="
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VOICE_MODELS_DIR="$SCRIPT_DIR/campus_rag_chatbot/voice/models"

# Create directories
mkdir -p "$VOICE_MODELS_DIR/whisper"
mkdir -p "$VOICE_MODELS_DIR/piper"

echo "Models will be downloaded to: $VOICE_MODELS_DIR"
echo ""

# ============================================
# Whisper STT Model (tiny.en - optimized for English, fast)
# ============================================
echo -e "${YELLOW}[1/2] Downloading Whisper STT model...${NC}"

WHISPER_MODEL="ggml-tiny.en.bin"
WHISPER_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$WHISPER_MODEL"
WHISPER_PATH="$VOICE_MODELS_DIR/whisper/$WHISPER_MODEL"

if [ -f "$WHISPER_PATH" ]; then
    echo "Whisper model already exists: $WHISPER_PATH"
    read -p "Re-download? (y/N): " redownload
    if [ "$redownload" != "y" ] && [ "$redownload" != "Y" ]; then
        echo "Skipping Whisper download"
    else
        rm -f "$WHISPER_PATH"
        echo "Downloading $WHISPER_MODEL (~75MB)..."
        curl -L -o "$WHISPER_PATH" "$WHISPER_URL"
        echo -e "${GREEN}Whisper model downloaded${NC}"
    fi
else
    echo "Downloading $WHISPER_MODEL (~75MB)..."
    curl -L -o "$WHISPER_PATH" "$WHISPER_URL"
    echo -e "${GREEN}Whisper model downloaded${NC}"
fi
echo ""

# ============================================
# Piper TTS Model (amy-medium - natural female US English voice)
# ============================================
echo -e "${YELLOW}[2/2] Downloading Piper TTS model...${NC}"

PIPER_MODEL="en_US-amy-medium"
PIPER_BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium"
PIPER_ONNX="$PIPER_MODEL.onnx"
PIPER_JSON="$PIPER_MODEL.onnx.json"
PIPER_PATH_ONNX="$VOICE_MODELS_DIR/piper/$PIPER_ONNX"
PIPER_PATH_JSON="$VOICE_MODELS_DIR/piper/$PIPER_JSON"

if [ -f "$PIPER_PATH_ONNX" ] && [ -f "$PIPER_PATH_JSON" ]; then
    echo "Piper model already exists: $PIPER_PATH_ONNX"
    read -p "Re-download? (y/N): " redownload
    if [ "$redownload" != "y" ] && [ "$redownload" != "Y" ]; then
        echo "Skipping Piper download"
    else
        rm -f "$PIPER_PATH_ONNX" "$PIPER_PATH_JSON"
        echo "Downloading $PIPER_ONNX (~60MB)..."
        curl -L -o "$PIPER_PATH_ONNX" "$PIPER_BASE_URL/$PIPER_ONNX"
        echo "Downloading $PIPER_JSON..."
        curl -L -o "$PIPER_PATH_JSON" "$PIPER_BASE_URL/$PIPER_JSON"
        echo -e "${GREEN}Piper model downloaded${NC}"
    fi
else
    echo "Downloading $PIPER_ONNX (~60MB)..."
    curl -L -o "$PIPER_PATH_ONNX" "$PIPER_BASE_URL/$PIPER_ONNX"
    echo "Downloading $PIPER_JSON..."
    curl -L -o "$PIPER_PATH_JSON" "$PIPER_BASE_URL/$PIPER_JSON"
    echo -e "${GREEN}Piper model downloaded${NC}"
fi
echo ""

# ============================================
# Verify downloads
# ============================================
echo -e "${YELLOW}Verifying downloads...${NC}"

MISSING=0

if [ ! -f "$WHISPER_PATH" ]; then
    echo -e "${RED}Missing: $WHISPER_PATH${NC}"
    MISSING=1
fi

if [ ! -f "$PIPER_PATH_ONNX" ]; then
    echo -e "${RED}Missing: $PIPER_PATH_ONNX${NC}"
    MISSING=1
fi

if [ ! -f "$PIPER_PATH_JSON" ]; then
    echo -e "${RED}Missing: $PIPER_PATH_JSON${NC}"
    MISSING=1
fi

if [ $MISSING -eq 1 ]; then
    echo ""
    echo -e "${RED}Some models failed to download. Check your internet connection and try again.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}All voice models downloaded successfully!${NC}"
echo ""
echo "Models installed:"
echo "  STT: $WHISPER_PATH"
echo "  TTS: $PIPER_PATH_ONNX"
echo "  TTS config: $PIPER_PATH_JSON"
echo ""
echo "Total size: ~135MB"
echo ""
