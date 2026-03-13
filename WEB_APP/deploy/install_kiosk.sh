#!/bin/bash
#
# CoCo Campus Kiosk - Full Installation Script
# ==============================================
# Installs and configures the CoCo kiosk on Raspberry Pi OS.
# Safe to run multiple times (idempotent).
#
# Usage: sudo ./WEB_APP/deploy/install_kiosk.sh
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }

# ── Resolve paths ──────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$SCRIPT_DIR"                        # WEB_APP/deploy/
WEB_APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"     # WEB_APP/
PROJECT_ROOT="$(cd "$WEB_APP_DIR/.." && pwd)"   # project root (e.g. /home/pi/coco)
VENV_DIR="$PROJECT_ROOT/venv"                   # virtual environment

# Detect the non-root user (for autostart config)
if [ -n "${SUDO_USER:-}" ]; then
    KIOSK_USER="$SUDO_USER"
else
    KIOSK_USER="$(whoami)"
fi
KIOSK_HOME="$(eval echo "~$KIOSK_USER")"

echo ""
echo "=============================================="
echo "  CoCo Campus Kiosk - Installation"
echo "=============================================="
echo ""
echo "  Project root : $PROJECT_ROOT"
echo "  WEB_APP      : $WEB_APP_DIR"
echo "  Venv         : $VENV_DIR"
echo "  Kiosk user   : $KIOSK_USER"
echo "  Home dir     : $KIOSK_HOME"
echo ""

# ── Must run as root (or with sudo) ───────────────────────────────────────

if [ "$(id -u)" -ne 0 ]; then
    err "This script must be run with sudo."
    echo "  Usage: sudo $0"
    exit 1
fi

# ── Fix hostname resolution (prevents sudo warnings) ─────────────────────

fix_hostname() {
    local CURRENT_HOSTNAME
    CURRENT_HOSTNAME="$(hostname)"
    if ! grep -qF "$CURRENT_HOSTNAME" /etc/hosts 2>/dev/null; then
        echo "127.0.1.1	$CURRENT_HOSTNAME" >> /etc/hosts
        log "Added '$CURRENT_HOSTNAME' to /etc/hosts"
    fi
}

fix_hostname

# ── Step 1: System packages ───────────────────────────────────────────────

install_system_packages() {
    echo -e "${YELLOW}[1/9] Installing system packages...${NC}"

    # Clean cached packages to avoid corrupt .deb files from prior downloads
    apt-get clean

    if ! apt-get update -qq; then
        err "apt-get update failed. Check network connectivity."
        exit 1
    fi

    # Fix any broken package state before installing
    # (e.g. partial upgrades, version mismatches between chromium/chromium-common)
    if ! apt-get --fix-broken install -y; then
        warn "apt --fix-broken install had issues. Continuing anyway..."
    fi

    # RPi OS Bookworm uses 'chromium' not 'chromium-browser'
    # Detect which package name is available
    local CHROMIUM_PKG="chromium-browser"
    if apt-cache show chromium > /dev/null 2>&1; then
        CHROMIUM_PKG="chromium"
    fi

    if ! apt-get install -y \
        "$CHROMIUM_PKG" \
        python3-pip \
        python3-dev \
        python3-venv \
        libmagic-dev \
        espeak-ng \
        espeak-ng-data \
        ffmpeg \
        unclutter \
        fonts-noto-color-emoji \
        curl; then
        err "apt-get install failed. See output above for details."
        echo "  Try running: sudo apt --fix-broken install"
        exit 1
    fi

    log "System packages installed (browser: $CHROMIUM_PKG)"
    echo ""
}

install_system_packages

# ── Step 1b: WiFi management permissions ─────────────────────────────────
# The backend needs elevated privileges for nmcli connection management
# (add, delete, up). We grant targeted sudo access via a drop-in file
# and add the kiosk user to the netdev group.

configure_wifi_permissions() {
    log "Configuring WiFi management permissions..."

    # Add kiosk user to netdev group (standard Debian network management group)
    if ! id -nG "$KIOSK_USER" | grep -qw netdev; then
        usermod -aG netdev "$KIOSK_USER"
        log "Added $KIOSK_USER to netdev group"
    else
        log "$KIOSK_USER already in netdev group"
    fi

    # Create targeted sudoers rule for nmcli WiFi management.
    # Restricts sudo access to: connection add/delete/up and dev wifi rescan.
    # Safe for repeated execution (overwrites the same file).
    local SUDOERS_FILE="/etc/sudoers.d/coco-wifi"
    cat > "$SUDOERS_FILE" << SUDOEOF
# CoCo Kiosk: Allow WiFi management via nmcli (no password prompt)
$KIOSK_USER ALL=(ALL) NOPASSWD: /usr/bin/nmcli connection add *
$KIOSK_USER ALL=(ALL) NOPASSWD: /usr/bin/nmcli connection delete *
$KIOSK_USER ALL=(ALL) NOPASSWD: /usr/bin/nmcli connection up *
$KIOSK_USER ALL=(ALL) NOPASSWD: /usr/bin/nmcli dev wifi rescan
SUDOEOF
    chmod 440 "$SUDOERS_FILE"

    # Validate the sudoers file syntax
    if visudo -cf "$SUDOERS_FILE" > /dev/null 2>&1; then
        log "Sudoers rule installed: $SUDOERS_FILE"
    else
        err "Invalid sudoers syntax in $SUDOERS_FILE — removing"
        rm -f "$SUDOERS_FILE"
    fi

    echo ""
}

configure_wifi_permissions

# ── Step 2: Python virtual environment & dependencies ─────────────────────
# Uses a venv to avoid PEP 668 conflicts with system packages.
# The venv is created once during install (not recreated on boot).

install_python_deps() {
    echo -e "${YELLOW}[2/9] Setting up Python environment...${NC}"

    local REQUIREMENTS="$WEB_APP_DIR/requirements_rpi.txt"

    if [ ! -f "$REQUIREMENTS" ]; then
        err "Requirements file not found: $REQUIREMENTS"
        exit 1
    fi

    # Create venv if it doesn't exist (idempotent)
    if [ ! -d "$VENV_DIR" ]; then
        log "Creating virtual environment at $VENV_DIR ..."
        sudo -u "$KIOSK_USER" python3 -m venv "$VENV_DIR"
    else
        log "Virtual environment already exists at $VENV_DIR"
    fi

    # Upgrade pip inside venv
    "$VENV_DIR/bin/pip" install --upgrade pip --quiet

    # Install dependencies inside venv (no PEP 668 issues)
    if "$VENV_DIR/bin/pip" install -r "$REQUIREMENTS"; then
        log "Python dependencies installed in venv"
    else
        err "pip install failed. See output above for details."
        exit 1
    fi

    # Show Python version
    local PY_VERSION
    PY_VERSION=$("$VENV_DIR/bin/python" --version 2>&1)
    log "Using $PY_VERSION"

    echo ""
}

install_python_deps

# ── Step 3: Download voice models ────────────────────────────────────────

download_voice_models() {
    echo -e "${YELLOW}[3/9] Downloading voice models...${NC}"

    local PIPER_MODEL_DIR="$WEB_APP_DIR/modules/voice/models/piper"
    local PIPER_ONNX="$PIPER_MODEL_DIR/en_US-amy-medium.onnx"
    local PIPER_JSON="$PIPER_MODEL_DIR/en_US-amy-medium.onnx.json"

    # Hugging Face is the standard distribution channel for Piper voices
    local HF_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium"

    sudo -u "$KIOSK_USER" mkdir -p "$PIPER_MODEL_DIR"

    if [ -f "$PIPER_ONNX" ] && [ -f "$PIPER_JSON" ]; then
        local MODEL_SIZE
        MODEL_SIZE=$(du -h "$PIPER_ONNX" | cut -f1)
        log "Piper voice model already exists ($MODEL_SIZE)"
    else
        log "Downloading Piper voice model (en_US-amy-medium)..."

        # Download ONNX model (~63 MB)
        if ! sudo -u "$KIOSK_USER" curl -L --progress-bar \
            -o "$PIPER_ONNX" \
            "$HF_BASE/en_US-amy-medium.onnx"; then
            err "Failed to download Piper ONNX model."
            warn "TTS will fall back to espeak-ng (lower quality)."
            echo ""
            return
        fi

        # Download config JSON
        if ! sudo -u "$KIOSK_USER" curl -sL \
            -o "$PIPER_JSON" \
            "$HF_BASE/en_US-amy-medium.onnx.json"; then
            err "Failed to download Piper config JSON."
            warn "TTS will fall back to espeak-ng (lower quality)."
            echo ""
            return
        fi

        # Verify download
        if [ -f "$PIPER_ONNX" ] && [ -s "$PIPER_ONNX" ]; then
            local MODEL_SIZE
            MODEL_SIZE=$(du -h "$PIPER_ONNX" | cut -f1)
            log "Piper voice model downloaded ($MODEL_SIZE)"
        else
            err "Piper model download appears corrupt or empty."
            rm -f "$PIPER_ONNX" "$PIPER_JSON"
            warn "TTS will fall back to espeak-ng (lower quality)."
        fi
    fi

    echo ""
}

download_voice_models

# ── Step 4: Setup .env file ──────────────────────────────────────────────

setup_env_file() {
    echo -e "${YELLOW}[4/9] Setting up environment file...${NC}"

    local ENV_FILE="$WEB_APP_DIR/.env"
    local ENV_EXAMPLE="$WEB_APP_DIR/.env.example"

    if [ -f "$ENV_FILE" ]; then
        log ".env file already exists"
    elif [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        chown "$KIOSK_USER:$KIOSK_USER" "$ENV_FILE"
        chmod 600 "$ENV_FILE"
        log ".env file created from .env.example"
    else
        # Generate minimal .env template
        cat > "$ENV_FILE" << 'ENVEOF'
OPENAI_API_KEY=your-api-key-here
ADMIN_API_KEY=change-me
ADMIN_PASSWORD=change-me
ENVEOF
        chown "$KIOSK_USER:$KIOSK_USER" "$ENV_FILE"
        chmod 600 "$ENV_FILE"
        warn ".env.example not found — created minimal .env template"
    fi

    # Validate critical keys are configured (not still placeholder values)
    local NEEDS_CONFIG=false
    if grep -q "your-api-key-here\|your-.*-here\|change-me" "$ENV_FILE" 2>/dev/null; then
        NEEDS_CONFIG=true
    fi

    if [ "$NEEDS_CONFIG" = true ]; then
        echo ""
        echo "  =============================================="
        echo -e "  ${YELLOW}IMPORTANT: Configure your API keys${NC}"
        echo "  =============================================="
        echo ""
        echo "  Edit the .env file:"
        echo "    sudo -u $KIOSK_USER nano $ENV_FILE"
        echo ""
        echo "  Required settings:"
        echo "    OPENAI_API_KEY=sk-your-actual-key"
        echo "    ADMIN_PASSWORD=your-secure-password"
        echo ""
        read -p "  Press Enter when you have configured .env (or Ctrl+C to abort)..."
        echo ""

        # Re-check after user edits
        if grep -q "your-api-key-here" "$ENV_FILE" 2>/dev/null; then
            err "OPENAI_API_KEY is still set to placeholder value."
            err "The backend WILL NOT START without a valid API key."
            echo "  Edit: nano $ENV_FILE"
            exit 1
        fi
    fi

    log ".env file ready"
    echo ""
}

setup_env_file

# ── Step 5: Verify vector store ───────────────────────────────────────────

verify_vector_store() {
    echo -e "${YELLOW}[5/9] Verifying vector store...${NC}"

    local VECTOR_DIR="$WEB_APP_DIR/modules/vector_store"

    if [ -f "$VECTOR_DIR/index.faiss" ] && [ -f "$VECTOR_DIR/index.pkl" ]; then
        local FAISS_SIZE
        FAISS_SIZE=$(du -h "$VECTOR_DIR/index.faiss" | cut -f1)
        log "Vector store found (index.faiss: $FAISS_SIZE)"
    else
        err "Vector store not found at $VECTOR_DIR"
        echo "  The RPi runs in runtime-only mode."
        echo "  Use INGESTION_MODULE on the dev machine to create the vector store,"
        echo "  then commit and push before deploying."
        exit 1
    fi
    echo ""
}

verify_vector_store

# ── Step 6: Install systemd service ──────────────────────────────────────

install_systemd_service() {
    echo -e "${YELLOW}[6/9] Installing systemd service...${NC}"

    local SERVICE_SRC="$DEPLOY_DIR/coco-kiosk.service"
    local SERVICE_DST="/etc/systemd/system/coco-kiosk.service"

    if [ ! -f "$SERVICE_SRC" ]; then
        err "Service file not found: $SERVICE_SRC"
        exit 1
    fi

    # Detect Chromium binary path for ExecStartPre health-wait
    local CHROMIUM_BIN="chromium-browser"
    if command -v chromium > /dev/null 2>&1; then
        CHROMIUM_BIN="chromium"
    fi

    # Generate the service file with actual paths, user, and venv Python
    local VENV_PYTHON="$VENV_DIR/bin/python"

    cat > "$SERVICE_DST" << SERVICEEOF
[Unit]
Description=CoCo Campus Information Kiosk Backend
After=network.target

[Service]
Type=simple
User=$KIOSK_USER
WorkingDirectory=$PROJECT_ROOT
ExecStart=$VENV_PYTHON -m WEB_APP
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICEEOF

    systemctl daemon-reload
    systemctl enable coco-kiosk.service > /dev/null 2>&1

    log "Systemd service installed and enabled"
    echo "  WorkingDirectory: $PROJECT_ROOT"
    echo "  ExecStart: $VENV_PYTHON -m WEB_APP"
    echo "  User: $KIOSK_USER"
    echo ""
}

install_systemd_service

# ── Step 7: Configure Chromium autostart ──────────────────────────────────

_write_chromium_desktop() {
    # Write/overwrite the Chromium autostart desktop file.
    # Separated so it can be called from both fresh install and reconfigure paths.
    local CHROMIUM_BIN="$1"
    local AUTOSTART_DIR="$2"

    cat > "$AUTOSTART_DIR/coco-chromium.desktop" << DESKTOPEOF
[Desktop Entry]
Type=Application
Name=CoCo Kiosk Browser
Comment=Launch CoCo campus kiosk in fullscreen Chromium
Exec=bash -c 'sleep 8 && $CHROMIUM_BIN --start-fullscreen --noerrdialogs --disable-infobars --disable-session-crashed-bubble --disable-translate --no-first-run --enable-features=VirtualKeyboard http://localhost:8000'
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
DESKTOPEOF

    chown "$KIOSK_USER:$KIOSK_USER" "$AUTOSTART_DIR/coco-chromium.desktop"
}

configure_chromium_autostart() {
    echo -e "${YELLOW}[7/9] Configuring Chromium autostart...${NC}"

    # Detect Chromium binary name
    local CHROMIUM_BIN="chromium-browser"
    if command -v chromium > /dev/null 2>&1 && ! command -v chromium-browser > /dev/null 2>&1; then
        CHROMIUM_BIN="chromium"
    fi

    local AUTOSTART_DIR="$KIOSK_HOME/.config/autostart"
    sudo -u "$KIOSK_USER" mkdir -p "$AUTOSTART_DIR"

    local DESKTOP_FILE="$AUTOSTART_DIR/coco-chromium.desktop"

    if [ -f "$DESKTOP_FILE" ]; then
        # Config exists — always ask user whether to reconfigure
        echo ""
        echo -e "  ${YELLOW}Chromium autostart configuration already exists.${NC}"
        echo ""
        read -p "  Do you want to reconfigure Chromium autostart? (Y/N): " RECONFIGURE
        echo ""
        if [[ "${RECONFIGURE^^}" == "Y" ]]; then
            _write_chromium_desktop "$CHROMIUM_BIN" "$AUTOSTART_DIR"
            log "Chromium autostart reconfigured"
        else
            log "Skipped Chromium autostart reconfiguration"
        fi
    else
        # Fresh install — write config automatically
        _write_chromium_desktop "$CHROMIUM_BIN" "$AUTOSTART_DIR"
        log "Chromium autostart configured (binary: $CHROMIUM_BIN, delay: 8s)"
    fi

    echo ""
}

configure_chromium_autostart

# ── Step 8: Disable screen blanking & power saving ───────────────────────

disable_screen_blanking() {
    echo -e "${YELLOW}[8/9] Disabling screen blanking / power saving...${NC}"

    # ── Method 1: LXDE autostart (append xset + unclutter) ──
    # IMPORTANT: We do NOT create our own LXDE autostart file.
    # If a user-level file doesn't exist, LXDE uses the system default at
    # /etc/xdg/lxsession/LXDE-pi/autostart.
    # Creating a partial user file REPLACES the system file entirely,
    # which can break the desktop session and cause a login loop.
    #
    # Instead, we copy the system file to the user dir first (if no user file exists),
    # then append our xset/unclutter commands.

    local LXDE_AUTOSTART="$KIOSK_HOME/.config/lxsession/LXDE-pi/autostart"
    local SYSTEM_AUTOSTART="/etc/xdg/lxsession/LXDE-pi/autostart"
    local LXDE_DIR
    LXDE_DIR="$(dirname "$LXDE_AUTOSTART")"

    # Create directory as the kiosk user (not root) to avoid ownership issues
    sudo -u "$KIOSK_USER" mkdir -p "$LXDE_DIR"

    if [ ! -f "$LXDE_AUTOSTART" ]; then
        if [ -f "$SYSTEM_AUTOSTART" ]; then
            # Copy the system default so we don't lose any entries
            cp "$SYSTEM_AUTOSTART" "$LXDE_AUTOSTART"
            log "Copied system LXDE autostart to user config"
        else
            # Fallback: create minimal LXDE defaults
            cat > "$LXDE_AUTOSTART" << 'AUTOSTART'
@lxpanel --profile LXDE-pi
@pcmanfm --desktop --profile LXDE-pi
AUTOSTART
            warn "System autostart not found, created minimal defaults"
        fi
    fi

    # Append xset commands if not already present
    for CMD in "@xset s off" "@xset -dpms" "@xset s noblank"; do
        if ! grep -qF "$CMD" "$LXDE_AUTOSTART" 2>/dev/null; then
            echo "$CMD" >> "$LXDE_AUTOSTART"
        fi
    done

    # Add unclutter (hide cursor after 3 seconds idle)
    if ! grep -qF "@unclutter" "$LXDE_AUTOSTART" 2>/dev/null; then
        echo "@unclutter -idle 3 -root" >> "$LXDE_AUTOSTART"
    fi

    # Fix ownership of the entire .config tree (script runs as root via sudo)
    chown -R "$KIOSK_USER:$KIOSK_USER" "$KIOSK_HOME/.config"

    # ── Method 2: lightdm.conf xserver-command (belt and suspenders) ──
    local LIGHTDM_CONF="/etc/lightdm/lightdm.conf"
    if [ -f "$LIGHTDM_CONF" ]; then
        if ! grep -q "xserver-command=X -s 0 -dpms" "$LIGHTDM_CONF" 2>/dev/null; then
            if grep -q "\[Seat:\*\]" "$LIGHTDM_CONF"; then
                sed -i '/\[Seat:\*\]/a xserver-command=X -s 0 -dpms' "$LIGHTDM_CONF"
            fi
        fi
    fi

    log "Screen blanking disabled"
    echo ""
}

disable_screen_blanking

# ── Step 9: Start the service ────────────────────────────────────────────

start_and_verify() {
    echo -e "${YELLOW}[9/9] Starting CoCo kiosk service...${NC}"

    systemctl restart coco-kiosk.service

    # Wait for the backend to come up
    echo -n "  Waiting for backend"
    local READY=false
    for i in $(seq 1 20); do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo ""
            log "Backend is running on port 8000"
            READY=true
            break
        fi
        echo -n "."
        sleep 1
    done

    if [ "$READY" = false ]; then
        echo ""
        warn "Backend not responding after 20s."
        echo ""
        echo "  Checking service status:"
        systemctl status coco-kiosk.service --no-pager -l 2>&1 | head -20 || true
        echo ""
        echo "  Recent logs:"
        journalctl -u coco-kiosk --no-pager -n 15 2>&1 || true
        echo ""
        err "Deployment may have issues. Review the output above."
        exit 1
    fi

    echo ""
}

start_and_verify

# ── Done ──────────────────────────────────────────────────────────────────

echo "=============================================="
echo -e "${GREEN}  Installation Complete!${NC}"
echo "=============================================="
echo ""
echo "  Service status : sudo systemctl status coco-kiosk"
echo "  Service logs   : journalctl -u coco-kiosk -f"
echo "  Web interface  : http://localhost:8000/"
echo ""
echo "  On next reboot, the kiosk will start automatically:"
echo "    1. systemd starts the backend server"
echo "    2. Chromium opens fullscreen to http://localhost:8000"
echo "    3. Screen blanking is disabled"
echo "    4. Mouse cursor hides after 3 seconds"
echo ""
echo "  To update later:  sudo $DEPLOY_DIR/update_kiosk.sh"
echo "  To uninstall:     sudo $DEPLOY_DIR/uninstall_kiosk.sh"
echo ""
