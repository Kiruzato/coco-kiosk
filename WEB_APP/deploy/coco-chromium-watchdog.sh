#!/bin/bash
#
# CoCo Chromium Watchdog
# =======================
# Monitors the Chromium kiosk process and restarts it if it crashes or is closed.
# Launched as a systemd user service so it has access to the user's X display.
#
# This script is installed by install_kiosk.sh and should not be run manually.
#

# Chromium binary — set by install_kiosk.sh via sed replacement
CHROMIUM_BIN="@@CHROMIUM_BIN@@"
KIOSK_URL="http://localhost:8000"
CHECK_INTERVAL=5      # seconds between checks
STARTUP_DELAY=10      # seconds to wait before first check (let desktop settle)
RELAUNCH_DELAY=3      # seconds to wait before relaunching after crash

# Ensure DISPLAY is set (required for X11 GUI)
export DISPLAY="${DISPLAY:-:0}"

log() {
    echo "[WATCHDOG] $(date '+%H:%M:%S') $1"
}

launch_chromium() {
    log "Launching Chromium in kiosk mode..."

    # Clear any crash flags so Chromium doesn't show restore prompts
    local CHROMIUM_DIR="$HOME/.config/chromium"
    if [ -d "$CHROMIUM_DIR/Default" ]; then
        sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' \
            "$CHROMIUM_DIR/Default/Preferences" 2>/dev/null || true
        sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' \
            "$CHROMIUM_DIR/Default/Preferences" 2>/dev/null || true
    fi

    $CHROMIUM_BIN \
        --kiosk \
        --noerrdialogs \
        --disable-infobars \
        --disable-session-crashed-bubble \
        --disable-translate \
        --no-first-run \
        --check-for-update-interval=31536000 \
        --disable-pinch \
        --disable-features=TranslateUI \
        --autoplay-policy=no-user-gesture-required \
        "$KIOSK_URL" &

    log "Chromium launched (PID: $!)"
}

is_chromium_running() {
    pgrep -x "$CHROMIUM_BIN" > /dev/null 2>&1 || \
    pgrep -f "$CHROMIUM_BIN.*--kiosk" > /dev/null 2>&1
}

# ── Main loop ─────────────────────────────────────────────────────────────

log "Watchdog started (check every ${CHECK_INTERVAL}s)"
log "Waiting ${STARTUP_DELAY}s for desktop to settle..."
sleep "$STARTUP_DELAY"

while true; do
    if ! is_chromium_running; then
        log "Chromium is NOT running — restarting in ${RELAUNCH_DELAY}s..."
        sleep "$RELAUNCH_DELAY"

        # Double-check it hasn't come back (e.g. slow startup)
        if ! is_chromium_running; then
            launch_chromium
        fi
    fi

    sleep "$CHECK_INTERVAL"
done
