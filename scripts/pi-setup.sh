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

# Step 1: Check Python version
echo -e "${YELLOW}[1/6] Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo -e "${RED}Error: Python 3.8+ required. Found: $PYTHON_VERSION${NC}"
    exit 1
fi
echo -e "${GREEN}Python $PYTHON_VERSION found${NC}"
echo ""

# Step 2: Create virtual environment
echo -e "${YELLOW}[2/6] Creating virtual environment...${NC}"
VENV_DIR="$PROJECT_ROOT/venv"

if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment already exists at $VENV_DIR"
    read -p "Recreate it? (y/N): " recreate
    if [ "$recreate" = "y" ] || [ "$recreate" = "Y" ]; then
        rm -rf "$VENV_DIR"
        python3 -m venv "$VENV_DIR"
        echo -e "${GREEN}Virtual environment recreated${NC}"
    else
        echo "Using existing virtual environment"
    fi
else
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}Virtual environment created at $VENV_DIR${NC}"
fi
echo ""

# Step 3: Activate virtual environment and install dependencies
echo -e "${YELLOW}[3/6] Installing dependencies...${NC}"
source "$VENV_DIR/bin/activate"

# Upgrade pip first
pip install --upgrade pip

# Install requirements
echo "Installing from requirements.txt..."
pip install -r "$APP_DIR/requirements.txt"

echo -e "${GREEN}Dependencies installed${NC}"
echo ""

# Step 4: Setup environment file
echo -e "${YELLOW}[4/6] Setting up environment file...${NC}"
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
echo -e "${YELLOW}[5/6] Ingesting documents...${NC}"
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
echo -e "${YELLOW}[6/6] Testing application startup...${NC}"
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
