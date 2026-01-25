/**
 * Developer Tools - Phase 17A.1
 * RAG-Only Mode Toggle
 */

// DOM Elements
const ragOnlyToggle = document.getElementById('ragOnlyToggle');
const statusDisplay = document.getElementById('statusDisplay');
const notification = document.getElementById('notification');

// State
let isUpdating = false;

/**
 * Load current RAG-only mode status from server
 */
async function loadStatus() {
    try {
        const response = await fetch('/dev/status');
        const data = await response.json();
        updateUI(data.rag_only_mode);
    } catch (error) {
        showNotification('Failed to load status: ' + error.message, 'error');
    }
}

/**
 * Toggle RAG-only mode
 */
async function toggleRagOnlyMode(enabled) {
    if (isUpdating) return;
    isUpdating = true;

    try {
        const response = await fetch('/dev/rag-only-mode', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled: enabled })
        });

        const data = await response.json();
        updateUI(data.rag_only_mode);
        showNotification(data.message, 'success');
    } catch (error) {
        showNotification('Failed to toggle: ' + error.message, 'error');
        // Revert toggle on error
        ragOnlyToggle.checked = !enabled;
    } finally {
        isUpdating = false;
    }
}

/**
 * Update UI based on current state
 */
function updateUI(ragOnlyMode) {
    ragOnlyToggle.checked = ragOnlyMode;

    if (ragOnlyMode) {
        statusDisplay.textContent = 'RAG-Only Mode (General AI Disabled)';
        statusDisplay.className = 'status-display on';
    } else {
        statusDisplay.textContent = 'Hybrid Mode (RAG + General AI)';
        statusDisplay.className = 'status-display off';
    }
}

/**
 * Show notification message
 */
function showNotification(message, type) {
    notification.textContent = message;
    notification.className = `notification ${type}`;
    notification.classList.remove('hidden');

    // Auto-hide after 3 seconds
    setTimeout(() => {
        notification.classList.add('hidden');
    }, 3000);
}

// Event Listeners
ragOnlyToggle.addEventListener('change', (e) => {
    toggleRagOnlyMode(e.target.checked);
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', loadStatus);
