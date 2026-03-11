/**
 * Developer Tools - Settings Management
 */

// DOM Elements
const devSectionToggle = document.getElementById('devSectionToggle');
const statusDisplay = document.getElementById('statusDisplay');
const notification = document.getElementById('notification');
const fusionRadios = document.querySelectorAll('input[name="fusionMethod"]');
const fusionLabelToggle = document.getElementById('fusionLabelToggle');
const optionLinear = document.getElementById('optionLinear');
const optionRrf = document.getElementById('optionRrf');

// State
let isUpdating = false;

/**
 * Load current settings from server
 */
async function loadSettings() {
    try {
        const response = await fetch('/dev/settings');
        if (response.status === 401) {
            window.location.href = '/dev/login';
            return;
        }
        const data = await response.json();
        updateDevSectionUI(data.dev_section_visible);
        updateFusionMethodUI(data.fusion_method || 'linear');
        updateFusionLabelUI(data.fusion_label_visible !== false);
    } catch (error) {
        showNotification('Failed to load settings: ' + error.message, 'error');
    }
}

/**
 * Toggle developer section visibility
 */
async function toggleDevSection(enabled) {
    if (isUpdating) return;
    isUpdating = true;

    try {
        const response = await fetch('/dev/settings/dev-section-visible', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled })
        });

        if (response.status === 401) {
            window.location.href = '/dev/login';
            return;
        }

        const data = await response.json();
        updateDevSectionUI(data.dev_section_visible);
        showNotification(data.message, 'success');
    } catch (error) {
        showNotification('Failed to toggle: ' + error.message, 'error');
        devSectionToggle.checked = !enabled;
    } finally {
        isUpdating = false;
    }
}

/**
 * Set fusion method
 */
async function setFusionMethod(method) {
    if (isUpdating) return;
    isUpdating = true;

    try {
        const response = await fetch('/dev/settings/fusion-method', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ method: method })
        });

        if (response.status === 401) {
            window.location.href = '/dev/login';
            return;
        }

        const data = await response.json();
        updateFusionMethodUI(data.fusion_method);
        showNotification(data.message, 'success');
    } catch (error) {
        showNotification('Failed to set fusion method: ' + error.message, 'error');
        // Revert radio selection
        loadSettings();
    } finally {
        isUpdating = false;
    }
}

/**
 * Toggle fusion label visibility
 */
async function toggleFusionLabel(enabled) {
    if (isUpdating) return;
    isUpdating = true;

    try {
        const response = await fetch('/dev/settings/fusion-label-visible', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled })
        });

        if (response.status === 401) {
            window.location.href = '/dev/login';
            return;
        }

        const data = await response.json();
        updateFusionLabelUI(data.fusion_label_visible);
        showNotification(data.message, 'success');
    } catch (error) {
        showNotification('Failed to toggle fusion label: ' + error.message, 'error');
        fusionLabelToggle.checked = !enabled;
    } finally {
        isUpdating = false;
    }
}

/**
 * Update dev section UI
 */
function updateDevSectionUI(visible) {
    devSectionToggle.checked = visible;

    if (visible) {
        statusDisplay.textContent = 'Developer Section Visible in Admin Sidebar';
        statusDisplay.className = 'status-display on';
    } else {
        statusDisplay.textContent = 'Developer Section Hidden from Admin Sidebar';
        statusDisplay.className = 'status-display off';
    }
}

/**
 * Update fusion method radio UI
 */
function updateFusionMethodUI(method) {
    fusionRadios.forEach(radio => {
        radio.checked = (radio.value === method);
    });
    optionLinear.classList.toggle('selected', method === 'linear');
    optionRrf.classList.toggle('selected', method === 'rrf');
}

/**
 * Update fusion label toggle UI
 */
function updateFusionLabelUI(visible) {
    fusionLabelToggle.checked = visible;
}

/**
 * Show notification message
 */
function showNotification(message, type) {
    notification.textContent = message;
    notification.className = `notification ${type}`;
    notification.classList.remove('hidden');

    setTimeout(() => {
        notification.classList.add('hidden');
    }, 3000);
}

// Event Listeners
devSectionToggle.addEventListener('change', (e) => {
    toggleDevSection(e.target.checked);
});

fusionRadios.forEach(radio => {
    radio.addEventListener('change', (e) => {
        setFusionMethod(e.target.value);
    });
});

fusionLabelToggle.addEventListener('change', (e) => {
    toggleFusionLabel(e.target.checked);
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', loadSettings);
