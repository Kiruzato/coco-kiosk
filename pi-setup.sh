#!/bin/bash
#
# CoCo Raspberry Pi Setup Script (Runtime Mode)
# ==============================================
# This script sets up the CoCo campus information kiosk on Raspberry Pi.
#
# IMPORTANT: This script assumes the vector store was pre-ingested on the
# development machine and is included in the repository. The Pi does NOT
# run ingestion - it only loads and uses the existing vector store.
#
# Usage: ./pi-setup.sh
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "=============================================="
echo "  CoCo Campus Kiosk - Raspberry Pi Setup"
echo "=============================================="
echo ""

# Get the script's directory (which is now the project root)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$PROJECT_ROOT/campus_rag_chatbot"

echo "Project root: $PROJECT_ROOT"
echo "App directory: $APP_DIR"
echo ""

# Step 1: Install system packages
echo -e "${YELLOW}[1/7] Installing system packages...${NC}"
echo "This requires sudo access."

sudo apt update

# Install base packages (always available)
sudo apt install -y \
    python3-dev \
    python3-pip \
    python3-venv \
    libmagic-dev \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    ffmpeg \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    espeak-ng \
    espeak-ng-data \
    curl

# Try to install Python 3.11 (optional - may not be available on all systems)
echo "Checking for Python 3.11 availability..."
if apt-cache show python3.11 &> /dev/null; then
    echo "Python 3.11 found in repositories, installing..."
    sudo apt install -y python3.11 python3.11-venv python3.11-dev
else
    echo -e "${YELLOW}Python 3.11 not available in repositories.${NC}"
    echo "Will use system Python instead."
    echo -e "${YELLOW}Note: Piper TTS may not work. Voice will use edge-tts (cloud) as fallback.${NC}"
fi

echo -e "${GREEN}System packages installed${NC}"
echo ""

# Step 2: Check Python version (prefer 3.11 for Piper TTS)
echo -e "${YELLOW}[2/7] Checking Python version...${NC}"

if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
    PYTHON_VERSION=$(python3.11 --version 2>&1 | cut -d' ' -f2)
    echo -e "${GREEN}Python 3.11 found ($PYTHON_VERSION) - recommended for Piper TTS${NC}"
else
    PYTHON_CMD="python3"
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
        echo -e "${RED}Error: Python 3.8+ required. Found: $PYTHON_VERSION${NC}"
        exit 1
    fi
    echo -e "${YELLOW}Python $PYTHON_VERSION found (3.11 recommended for Piper TTS)${NC}"
fi
echo ""

# Step 3: Create virtual environment
echo -e "${YELLOW}[3/7] Creating virtual environment...${NC}"
VENV_DIR="$PROJECT_ROOT/venv"

if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment already exists at $VENV_DIR"
    read -p "Recreate it? (y/N): " recreate
    if [ "$recreate" = "y" ] || [ "$recreate" = "Y" ]; then
        rm -rf "$VENV_DIR"
        $PYTHON_CMD -m venv "$VENV_DIR"
        echo -e "${GREEN}Virtual environment recreated with $PYTHON_CMD${NC}"
    else
        echo "Using existing virtual environment"
    fi
else
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo -e "${GREEN}Virtual environment created at $VENV_DIR with $PYTHON_CMD${NC}"
fi
echo ""

# Step 4: Activate virtual environment and install dependencies
echo -e "${YELLOW}[4/7] Installing dependencies...${NC}"
source "$VENV_DIR/bin/activate"

# Upgrade pip first
pip install --upgrade pip wheel setuptools

# Install requirements (use RPi-specific version)
if [ -f "$APP_DIR/requirements_rpi.txt" ]; then
    echo "Installing from requirements_rpi.txt (ARM64 optimized)..."
    pip install -r "$APP_DIR/requirements_rpi.txt"
elif [ -f "$APP_DIR/requirements_py311.txt" ]; then
    echo "Installing from requirements_py311.txt (Python 3.11)..."
    pip install -r "$APP_DIR/requirements_py311.txt"
else
    echo "Installing from requirements.txt..."
    pip install -r "$APP_DIR/requirements.txt"
fi

# Handle potential faiss-cpu ARM64 issue
if ! python -c "import faiss" 2>/dev/null; then
    echo -e "${YELLOW}Reinstalling faiss-cpu for ARM64...${NC}"
    pip install faiss-cpu --no-cache-dir
fi

echo -e "${GREEN}Dependencies installed${NC}"
echo ""

# Step 5: Setup environment file
echo -e "${YELLOW}[5/7] Setting up environment file...${NC}"
ENV_FILE="$APP_DIR/.env"
ENV_EXAMPLE="$APP_DIR/.env.example"

if [ -f "$ENV_FILE" ]; then
    echo ".env file already exists"
    read -p "Overwrite with template? (y/N): " overwrite
    if [ "$overwrite" = "y" ] || [ "$overwrite" = "Y" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        echo -e "${GREEN}.env file created from template${NC}"
    else
        echo "Keeping existing .env file"
    fi
else
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    echo -e "${GREEN}.env file created from template${NC}"
fi

# Generate admin API key suggestion
ADMIN_KEY=$(python3 -c "import uuid; print(uuid.uuid4())")
echo ""
echo "=============================================="
echo -e "${YELLOW}IMPORTANT: Configure your API keys${NC}"
echo "=============================================="
echo ""
echo "Edit the .env file:"
echo "  nano $ENV_FILE"
echo ""
echo "Required settings:"
echo "  OPENAI_API_KEY=sk-your-key-here"
echo "  ADMIN_API_KEY=$ADMIN_KEY"
echo ""
echo "(The admin key above was auto-generated for you)"
echo ""

read -p "Press Enter when you have configured your .env file..."
echo ""

# Step 6: Download voice models (optional)
echo -e "${YELLOW}[6/7] Voice model setup...${NC}"
VOICE_SCRIPT="$PROJECT_ROOT/download-voice-models.sh"

if [ -f "$VOICE_SCRIPT" ]; then
    read -p "Download voice models for offline STT/TTS? (~135MB) (y/N): " download_voice
    if [ "$download_voice" = "y" ] || [ "$download_voice" = "Y" ]; then
        chmod +x "$VOICE_SCRIPT"
        "$VOICE_SCRIPT"
    else
        echo "Skipping voice model download"
        echo -e "${YELLOW}Note: Voice will use cloud fallback (edge-tts) if models not present${NC}"
    fi
else
    echo -e "${YELLOW}Voice model download script not found. Skipping...${NC}"
fi
echo ""

# Step 7: Verify vector store (pre-ingested from dev machine)
echo -e "${YELLOW}[7/7] Verifying vector store...${NC}"
cd "$APP_DIR"

VECTOR_STORE_DIR="vector_store"

if [ -d "$VECTOR_STORE_DIR" ]; then
    # Check for essential files
    if [ -f "$VECTOR_STORE_DIR/index.faiss" ] && [ -f "$VECTOR_STORE_DIR/index.pkl" ]; then
        echo -e "${GREEN}Vector store found and valid${NC}"
        echo "  - index.faiss: $(ls -lh $VECTOR_STORE_DIR/index.faiss | awk '{print $5}')"
        echo "  - index.pkl: $(ls -lh $VECTOR_STORE_DIR/index.pkl | awk '{print $5}')"
    else
        echo -e "${RED}ERROR: Vector store directory exists but is incomplete${NC}"
        echo "Missing required files (index.faiss and/or index.pkl)"
        echo ""
        echo "The vector store must be pre-ingested on the development machine"
        echo "and included in the git repository before deploying to RPi."
        echo ""
        echo "On your development machine, run:"
        echo "  cd campus_rag_chatbot"
        echo "  python admin.py ingest documents_to_ingest/"
        echo "  git add vector_store/"
        echo "  git commit -m 'Add pre-ingested vector store'"
        echo "  git push"
        echo ""
        echo "Then on RPi, run: git pull"
        exit 1
    fi
else
    echo -e "${RED}ERROR: Vector store not found${NC}"
    echo ""
    echo "The Raspberry Pi runs in RUNTIME MODE only."
    echo "It does NOT perform document ingestion."
    echo ""
    echo "The vector store must be pre-ingested on the development machine"
    echo "and included in the git repository."
    echo ""
    echo "On your development machine, run:"
    echo "  cd campus_rag_chatbot"
    echo "  python admin.py ingest documents_to_ingest/"
    echo "  git add vector_store/"
    echo "  git commit -m 'Add pre-ingested vector store'"
    echo "  git push"
    echo ""
    echo "Then on RPi, run: git pull"
    exit 1
fi
echo ""

# Test startup
echo -e "${YELLOW}Testing application startup...${NC}"
echo "Starting server for quick test (will stop after 5 seconds)..."

# Start server in background
python app.py &
SERVER_PID=$!

# Wait for startup
sleep 5

# Test health endpoint
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}Server started successfully!${NC}"
else
    echo -e "${YELLOW}Server may still be starting...${NC}"
fi

# Stop the test server
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true

echo ""
echo "=============================================="
echo -e "${GREEN}  Setup Complete!${NC}"
echo "=============================================="
echo ""
echo "To start the server:"
echo "  source $VENV_DIR/bin/activate"
echo "  cd $APP_DIR"
echo "  python app.py"
echo ""
echo "Access the kiosk at:"
echo "  http://$(hostname -I | awk '{print $1}'):8000/"
echo ""
