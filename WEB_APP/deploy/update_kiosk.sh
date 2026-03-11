#!/bin/bash
#
# CoCo Campus Kiosk - Update Script
# ====================================
# Pulls latest code, updates dependencies, and restarts the service.
#
# Usage: sudo ./WEB_APP/deploy/update_kiosk.sh
#

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[!!]${NC} $1"; }
err()  { echo -e "${RED}[ERR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$WEB_APP_DIR/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/venv"

echo ""
echo "=============================================="
echo "  CoCo Campus Kiosk - Update"
echo "=============================================="
echo ""

# ── Step 1: Pull latest code ─────────────────────────────────────────────

echo -e "${YELLOW}[1/3] Pulling latest code...${NC}"

cd "$PROJECT_ROOT"

if git diff --quiet && git diff --cached --quiet; then
    git pull
    log "Code updated"
else
    warn "Local changes detected. Pulling with rebase..."
    git stash
    git pull
    git stash pop || warn "Stash pop had conflicts — check manually"
    log "Code updated (local changes preserved)"
fi

echo ""

# ── Step 2: Update Python dependencies ───────────────────────────────────

echo -e "${YELLOW}[2/3] Updating Python dependencies...${NC}"

REQUIREMENTS="$WEB_APP_DIR/requirements_rpi.txt"

if [ ! -f "$REQUIREMENTS" ]; then
    err "Requirements file not found: $REQUIREMENTS"
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    err "Virtual environment not found at $VENV_DIR. Run install_kiosk.sh first."
    exit 1
fi

if "$VENV_DIR/bin/pip" install -r "$REQUIREMENTS"; then
    log "Dependencies updated"
else
    err "pip install failed. See output above."
    exit 1
fi

echo ""

# ── Step 3: Restart service ──────────────────────────────────────────────

echo -e "${YELLOW}[3/3] Restarting kiosk service...${NC}"

if systemctl is-active --quiet coco-kiosk 2>/dev/null; then
    sudo systemctl restart coco-kiosk
else
    sudo systemctl start coco-kiosk
fi

# Wait for backend
echo -n "  Waiting for backend"
for i in $(seq 1 10); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo ""
        log "Backend is running"
        break
    fi
    echo -n "."
    sleep 1
done

if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo ""
    warn "Backend not responding yet. Check: journalctl -u coco-kiosk -f"
fi

echo ""
echo "=============================================="
echo -e "${GREEN}  Update Complete!${NC}"
echo "=============================================="
echo ""
