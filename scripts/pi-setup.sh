#!/bin/bash
#
# CoCo Raspberry Pi Setup Script
# ==============================
# This script sets up the CoCo campus information kiosk on Raspberry Pi.
#
# Usage: ./scripts/pi-setup.sh
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

# Get the script's directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
APP_DIR="$PROJECT_ROOT/campus_rag_chatbot"

echo "Project root: $PROJECT_ROOT"
echo "App directory: $APP_DIR"
echo ""

# Step 1: Install system packages
echo -e "${YELLOW}[1/7] Installing system packages...${NC}"
echo "This requires sudo access."

sudo apt update && sudo apt install -y \
    python3-dev \
    python3-pip \
    python3-venv \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    libmagic-dev \
    poppler-utils \
    ffmpeg \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    espeak-ng \
    espeak-ng-data \
    curl

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

# Step 3: Activate virtual environment and install dependencies
echo -e "${YELLOW}[4/7] Installing dependencies...${NC}"
source "$VENV_DIR/bin/activate"

# Upgrade pip first
pip install --upgrade pip

# Install requirements (use py311 version for Piper TTS compatibility)
if [ -f "$APP_DIR/requirements_py311.txt" ]; then
    echo "Installing from requirements_py311.txt (Python 3.11)..."
    pip install -r "$APP_DIR/requirements_py311.txt"
else
    echo "Installing from requirements.txt..."
    pip install -r "$APP_DIR/requirements.txt"
fi

echo -e "${GREEN}Dependencies installed${NC}"
echo ""

# Step 4: Setup environment file
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

# Step 5: Ingest documents
echo -e "${YELLOW}[6/7] Ingesting documents...${NC}"
cd "$APP_DIR"

if [ -d "vector_store" ]; then
    echo "Vector store already exists"
    read -p "Re-ingest documents? (y/N): " reingest
    if [ "$reingest" = "y" ] || [ "$reingest" = "Y" ]; then
        python admin.py ingest data/
    else
        echo "Skipping document ingestion"
    fi
else
    echo "Ingesting default documents..."
    python admin.py ingest data/
fi
echo -e "${GREEN}Document ingestion complete${NC}"
echo ""

# Step 6: Test startup
echo -e "${YELLOW}[7/7] Testing application startup...${NC}"
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
echo "For auto-start on boot, see DEPLOYMENT.md"
echo ""
