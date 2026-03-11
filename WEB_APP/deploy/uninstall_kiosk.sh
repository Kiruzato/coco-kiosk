#!/bin/bash
#
# CoCo Campus Kiosk - Uninstall Script
# ======================================
# Removes the systemd service and autostart configuration.
# Does NOT remove Python packages or project files.
#
# Usage: sudo ./WEB_APP/deploy/uninstall_kiosk.sh
#

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[!!]${NC} $1"; }

if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}[ERR]${NC} This script must be run with sudo."
    exit 1
fi

KIOSK_USER="${SUDO_USER:-$(whoami)}"
KIOSK_HOME="$(eval echo "~$KIOSK_USER")"

echo ""
echo "=============================================="
echo "  CoCo Campus Kiosk - Uninstall"
echo "=============================================="
echo ""

# ── Stop and remove systemd service ──────────────────────────────────────

echo "Removing systemd service..."

if systemctl is-active --quiet coco-kiosk 2>/dev/null; then
    systemctl stop coco-kiosk
    log "Service stopped"
fi

if systemctl is-enabled --quiet coco-kiosk 2>/dev/null; then
    systemctl disable coco-kiosk > /dev/null 2>&1
    log "Service disabled"
fi

SERVICE_FILE="/etc/systemd/system/coco-kiosk.service"
if [ -f "$SERVICE_FILE" ]; then
    rm "$SERVICE_FILE"
    systemctl daemon-reload
    log "Service file removed"
else
    warn "Service file not found (already removed)"
fi

echo ""

# ── Remove Chromium autostart ────────────────────────────────────────────

echo "Removing Chromium autostart..."

AUTOSTART_FILE="$KIOSK_HOME/.config/autostart/coco-chromium.desktop"
if [ -f "$AUTOSTART_FILE" ]; then
    rm "$AUTOSTART_FILE"
    log "Chromium autostart removed"
else
    warn "Autostart file not found (already removed)"
fi

echo ""

# ── Remove screen blanking overrides ─────────────────────────────────────

echo "Removing screen blanking overrides..."

LXDE_AUTOSTART="$KIOSK_HOME/.config/lxsession/LXDE-pi/autostart"
if [ -f "$LXDE_AUTOSTART" ]; then
    # Remove only the lines we added
    sed -i '/@xset s off/d' "$LXDE_AUTOSTART"
    sed -i '/@xset -dpms/d' "$LXDE_AUTOSTART"
    sed -i '/@xset s noblank/d' "$LXDE_AUTOSTART"
    sed -i '/@unclutter/d' "$LXDE_AUTOSTART"
    log "Screen blanking overrides removed from LXDE autostart"
fi

echo ""

# ── Done ─────────────────────────────────────────────────────────────────

echo "=============================================="
echo -e "${GREEN}  Uninstall Complete${NC}"
echo "=============================================="
echo ""
echo "  The kiosk service and autostart have been removed."
echo "  Python packages and project files were NOT removed."
echo ""
echo "  To reinstall: sudo ./WEB_APP/deploy/install_kiosk.sh"
echo ""
