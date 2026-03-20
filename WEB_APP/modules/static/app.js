/**
 * Campus Information Kiosk - Frontend JavaScript
 * ================================================
 * Handles chat interactions, API calls, and feedback submission
 */

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

// Phase 35 fix: Use sessionStorage to persist sessionId across page refresh
// This prevents clarification state from being lost when user refreshes mid-conversation
let sessionId = sessionStorage.getItem('chatSessionId') || null;
let lastQueryId = null;
let isWaiting = false;

// Phase 48: Advertisement slideshow state
let advertisements = [];
let currentAdIndex = 0;
let adRotationTimer = null;
const AD_ROTATION_INTERVAL = 60000; // 1 minute per ad

// Phase 55: Advertisement auto-refresh state
let adAutoRefreshTimer = null;
const AD_AUTO_REFRESH_INTERVAL = 600000; // 10 minutes

// Phase 55: Cooldown state
const BUTTON_COOLDOWN_MS = 5000; // 5 seconds
let resetButtonCooldown = false;
let refreshAdButtonCooldown = false;

// Connectivity state
let isOnline = true;
let connectivityCheckInterval = null;
let consecutiveFailures = 0;
const CONNECTIVITY_CHECK_URL = 'https://connectivitycheck.gstatic.com/generate_204';
const CONNECTIVITY_POLL_MS = 10000;      // 10 seconds
const CONNECTIVITY_TIMEOUT_MS = 5000;    // 5 second fetch timeout
const CONNECTIVITY_FAIL_THRESHOLD = 2;   // require 2 consecutive failures before offline

// Phase 50: Metadata visibility setting (loaded from server)
let metadataVisible = true; // Default: show metadata

// ============================================================================
// ADAPTIVE TEXT SCALER MODULE
// ============================================================================
// Content-measurement-based adaptive text scaling for text advertisements.
// Uses binary search to find optimal font size that fits within container.

const AdaptiveTextScaler = (function() {
    'use strict';

    // Configuration
    const CONFIG = {
        MIN_FONT_SIZE: 14,      // Minimum font size in pixels (floor for readability)
        MAX_FONT_SIZE: 72,      // Maximum font size in pixels (cap for short texts)
        LINE_HEIGHT_RATIO: 1.5, // Consistent line-height multiplier
        PADDING_FACTOR: 0.9,    // Use 90% of container to leave breathing room
        TOLERANCE: 2,           // Pixel tolerance for binary search convergence
        MAX_ITERATIONS: 15      // Safety limit for binary search iterations
    };

    // Reusable measurement element (created once, reused for performance)
    let measurementElement = null;

    /**
     * Get or create the hidden measurement element.
     * Uses a single reusable element to avoid DOM thrashing.
     */
    function getMeasurementElement() {
        if (!measurementElement) {
            measurementElement = document.createElement('div');
            measurementElement.style.cssText = `
                position: absolute;
                visibility: hidden;
                pointer-events: none;
                z-index: -9999;
                left: -9999px;
                top: 0;
                box-sizing: border-box;
            `;
            measurementElement.setAttribute('aria-hidden', 'true');
            document.body.appendChild(measurementElement);
        }
        return measurementElement;
    }

    /**
     * Measure text dimensions at a specific font size.
     * @param {string} htmlContent - The HTML content to measure
     * @param {number} fontSize - Font size in pixels
     * @param {number} containerWidth - Available width in pixels
     * @returns {{width: number, height: number}} - Measured dimensions
     */
    function measureTextAtSize(htmlContent, fontSize, containerWidth) {
        const el = getMeasurementElement();

        // Apply styling that matches .ad-text-content
        el.style.width = containerWidth + 'px';
        el.style.fontSize = fontSize + 'px';
        el.style.lineHeight = CONFIG.LINE_HEIGHT_RATIO;
        el.style.fontWeight = '500';
        el.style.textAlign = 'left';
        el.style.wordWrap = 'break-word';
        el.style.overflowWrap = 'break-word';
        el.style.padding = '0';
        el.style.margin = '0';

        // Set content and measure
        el.innerHTML = htmlContent;

        return {
            width: el.scrollWidth,
            height: el.scrollHeight
        };
    }

    /**
     * Calculate optimal font size using binary search.
     * Finds the largest font size where content fits within container.
     *
     * @param {string} htmlContent - The HTML content to fit
     * @param {number} containerWidth - Available width in pixels
     * @param {number} containerHeight - Available height in pixels
     * @returns {number} - Optimal font size in pixels
     */
    function calculateOptimalFontSize(htmlContent, containerWidth, containerHeight) {
        // Apply padding factor for breathing room
        const targetWidth = containerWidth * CONFIG.PADDING_FACTOR;
        const targetHeight = containerHeight * CONFIG.PADDING_FACTOR;

        let minSize = CONFIG.MIN_FONT_SIZE;
        let maxSize = CONFIG.MAX_FONT_SIZE;
        let optimalSize = minSize;
        let iterations = 0;

        // Binary search for optimal font size
        while (maxSize - minSize > CONFIG.TOLERANCE && iterations < CONFIG.MAX_ITERATIONS) {
            const midSize = Math.floor((minSize + maxSize) / 2);
            const measurement = measureTextAtSize(htmlContent, midSize, targetWidth);

            if (measurement.height <= targetHeight) {
                // Content fits, try larger
                optimalSize = midSize;
                minSize = midSize + 1;
            } else {
                // Content overflows, try smaller
                maxSize = midSize - 1;
            }

            iterations++;
        }

        // Final validation: ensure the optimal size actually fits
        const finalMeasurement = measureTextAtSize(htmlContent, optimalSize, targetWidth);
        if (finalMeasurement.height > targetHeight && optimalSize > CONFIG.MIN_FONT_SIZE) {
            // Reduce by 1 step to ensure fit
            optimalSize = Math.max(CONFIG.MIN_FONT_SIZE, optimalSize - 2);
        }

        return optimalSize;
    }

    /**
     * Apply adaptive scaling to a text advertisement element.
     * @param {HTMLElement} textAdElement - The .ad-text container element
     */
    function scaleTextAd(textAdElement) {
        if (!textAdElement) return;

        const contentElement = textAdElement.querySelector('.ad-text-content');
        if (!contentElement) return;

        // Get container dimensions (excluding padding)
        const computedStyle = window.getComputedStyle(textAdElement);
        const paddingTop = parseFloat(computedStyle.paddingTop) || 0;
        const paddingBottom = parseFloat(computedStyle.paddingBottom) || 0;
        const paddingLeft = parseFloat(computedStyle.paddingLeft) || 0;
        const paddingRight = parseFloat(computedStyle.paddingRight) || 0;

        const containerWidth = textAdElement.clientWidth - paddingLeft - paddingRight;
        const containerHeight = textAdElement.clientHeight - paddingTop - paddingBottom;

        // Skip if container has no dimensions yet
        if (containerWidth <= 0 || containerHeight <= 0) return;

        // Get the HTML content to measure
        const htmlContent = contentElement.innerHTML;
        if (!htmlContent.trim()) return;

        // Calculate optimal font size
        const optimalFontSize = calculateOptimalFontSize(
            htmlContent,
            containerWidth,
            containerHeight
        );

        // Apply the calculated font size
        contentElement.style.fontSize = optimalFontSize + 'px';
        contentElement.style.lineHeight = CONFIG.LINE_HEIGHT_RATIO;
    }

    /**
     * Scale all visible text advertisements in the carousel.
     * Call this after rendering or on container resize.
     */
    function scaleAllTextAds() {
        const textAds = document.querySelectorAll('.ad-item.ad-text');
        textAds.forEach(scaleTextAd);
    }

    /**
     * Create a ResizeObserver for responsive scaling.
     * @param {HTMLElement} container - The container to observe
     * @returns {ResizeObserver} - The observer instance
     */
    function createResizeObserver(container) {
        if (!window.ResizeObserver) {
            console.warn('[AdaptiveTextScaler] ResizeObserver not supported');
            return null;
        }

        let resizeTimeout = null;
        const observer = new ResizeObserver((entries) => {
            // Debounce resize events to avoid excessive recalculations
            if (resizeTimeout) clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                scaleAllTextAds();
            }, 100);
        });

        observer.observe(container);
        return observer;
    }

    // Public API
    return {
        scaleTextAd: scaleTextAd,
        scaleAllTextAds: scaleAllTextAds,
        createResizeObserver: createResizeObserver,
        CONFIG: CONFIG // Expose for debugging/testing
    };
})();

// ============================================================================
// DRAW QUOTE LABEL SWITCHER MODULE
// ============================================================================
// Handles label switching animation for the Draw Quote button.
// Alternates between "Draw Quotes" and "Click Me" every 5 seconds.
// Uses vertical slide + fade animation with adaptive text scaling.

const DrawQuoteLabelSwitcher = (function() {
    'use strict';

    // Configuration
    const CONFIG = {
        SWITCH_INTERVAL_MS: 5000,       // Switch every 5 seconds
        ANIMATION_DURATION_MS: 350,     // Match CSS transition duration
        MIN_FONT_SIZE: 12,              // Minimum font size in pixels
        MAX_FONT_SIZE: 32,              // Maximum font size in pixels (allow large text)
        LINE_HEIGHT_RATIO: 1.15,        // Tighter line height for 2-line layout
        PADDING_FACTOR: 0.95            // Use 95% of container space
    };

    // State
    let switchTimer = null;
    let isAnimating = false;
    let button = null;
    let labelContainer = null;
    let labels = [];
    let currentLabelIndex = 0;
    let measurementElement = null;

    /**
     * Get or create the hidden measurement element for font scaling.
     */
    function getMeasurementElement() {
        if (!measurementElement) {
            measurementElement = document.createElement('div');
            measurementElement.style.cssText = `
                position: absolute;
                visibility: hidden;
                pointer-events: none;
                z-index: -9999;
                left: -9999px;
                top: 0;
                box-sizing: border-box;
            `;
            measurementElement.setAttribute('aria-hidden', 'true');
            document.body.appendChild(measurementElement);
        }
        return measurementElement;
    }

    /**
     * Measure label dimensions at a specific font size.
     * @param {HTMLElement} label - The label element to measure
     * @param {number} fontSize - Font size in pixels
     * @param {number} containerWidth - Available width
     * @returns {{width: number, height: number}}
     */
    function measureLabelAtSize(label, fontSize, containerWidth) {
        const el = getMeasurementElement();

        el.style.width = containerWidth + 'px';
        el.style.fontSize = fontSize + 'px';
        el.style.lineHeight = CONFIG.LINE_HEIGHT_RATIO;
        el.style.fontWeight = '700';
        el.style.textAlign = 'center';
        el.style.display = 'flex';
        el.style.flexDirection = 'column';
        el.style.alignItems = 'center';

        // Clone the label content
        el.innerHTML = label.innerHTML;

        return {
            width: el.scrollWidth,
            height: el.scrollHeight
        };
    }

    /**
     * Calculate optimal font size for a label using binary search.
     * @param {HTMLElement} label - The label element
     * @param {number} containerWidth - Available width
     * @param {number} containerHeight - Available height
     * @returns {number} Optimal font size in pixels
     */
    function calculateOptimalFontSize(label, containerWidth, containerHeight) {
        const targetWidth = containerWidth * CONFIG.PADDING_FACTOR;
        const targetHeight = containerHeight * CONFIG.PADDING_FACTOR;

        let minSize = CONFIG.MIN_FONT_SIZE;
        let maxSize = CONFIG.MAX_FONT_SIZE;
        let optimalSize = minSize;
        let iterations = 0;
        const maxIterations = 12;

        while (maxSize - minSize > 1 && iterations < maxIterations) {
            const midSize = Math.floor((minSize + maxSize) / 2);
            const measurement = measureLabelAtSize(label, midSize, targetWidth);

            if (measurement.height <= targetHeight && measurement.width <= targetWidth) {
                optimalSize = midSize;
                minSize = midSize + 1;
            } else {
                maxSize = midSize - 1;
            }
            iterations++;
        }

        return optimalSize;
    }

    /**
     * Apply adaptive font scaling to all labels.
     */
    function scaleLabels() {
        if (!button || labels.length === 0) return;

        const computedStyle = window.getComputedStyle(button);
        const paddingTop = parseFloat(computedStyle.paddingTop) || 0;
        const paddingBottom = parseFloat(computedStyle.paddingBottom) || 0;
        const paddingLeft = parseFloat(computedStyle.paddingLeft) || 0;
        const paddingRight = parseFloat(computedStyle.paddingRight) || 0;

        const containerWidth = button.clientWidth - paddingLeft - paddingRight;
        const containerHeight = button.clientHeight - paddingTop - paddingBottom;

        if (containerWidth <= 0 || containerHeight <= 0) return;

        // Find the minimum optimal size that works for all labels
        let minOptimalSize = CONFIG.MAX_FONT_SIZE;

        labels.forEach(label => {
            const optimalSize = calculateOptimalFontSize(label, containerWidth, containerHeight);
            minOptimalSize = Math.min(minOptimalSize, optimalSize);
        });

        // Apply the same font size to all labels for consistency
        labels.forEach(label => {
            label.style.fontSize = minOptimalSize + 'px';
            label.style.lineHeight = CONFIG.LINE_HEIGHT_RATIO;
        });

        console.log('[DrawQuoteLabelSwitcher] Scaled labels to', minOptimalSize + 'px',
            '(container:', containerWidth + 'x' + containerHeight + ')');
    }

    /**
     * Switch to the next label with animation.
     */
    function switchLabel() {
        if (isAnimating || labels.length < 2) return;

        isAnimating = true;

        const currentLabel = labels[currentLabelIndex];
        const nextIndex = (currentLabelIndex + 1) % labels.length;
        const nextLabel = labels[nextIndex];

        // Start exit animation on current label
        currentLabel.classList.remove('active');
        currentLabel.classList.add('exiting');

        // Start enter animation on next label
        nextLabel.classList.add('active');

        // Clean up after animation completes
        setTimeout(() => {
            currentLabel.classList.remove('exiting');
            currentLabelIndex = nextIndex;
            isAnimating = false;
        }, CONFIG.ANIMATION_DURATION_MS);
    }

    /**
     * Start the automatic label switching timer.
     */
    function startTimer() {
        stopTimer(); // Clear any existing timer
        switchTimer = setInterval(() => {
            if (!isAnimating) {
                switchLabel();
            }
        }, CONFIG.SWITCH_INTERVAL_MS);
    }

    /**
     * Stop the automatic label switching timer.
     */
    function stopTimer() {
        if (switchTimer) {
            clearInterval(switchTimer);
            switchTimer = null;
        }
    }

    /**
     * Initialize the label switcher.
     * @param {string} buttonId - The ID of the Draw Quote button
     */
    function init(buttonId) {
        button = document.getElementById(buttonId);
        if (!button) {
            console.warn('[DrawQuoteLabelSwitcher] Button not found:', buttonId);
            return;
        }

        labelContainer = button.querySelector('.draw-quote-label-container');
        if (!labelContainer) {
            console.warn('[DrawQuoteLabelSwitcher] Label container not found');
            return;
        }

        labels = Array.from(button.querySelectorAll('.draw-quote-label'));
        if (labels.length < 2) {
            console.warn('[DrawQuoteLabelSwitcher] Need at least 2 labels for switching');
            return;
        }

        // Initial state: first label is active
        currentLabelIndex = 0;
        labels.forEach((label, index) => {
            if (index === 0) {
                label.classList.add('active');
                label.classList.remove('exiting');
            } else {
                label.classList.remove('active', 'exiting');
            }
        });

        // Apply initial font scaling
        scaleLabels();

        // Start the switching timer
        startTimer();

        // Set up resize observer for responsive scaling
        if (window.ResizeObserver) {
            let resizeTimeout = null;
            const observer = new ResizeObserver(() => {
                if (resizeTimeout) clearTimeout(resizeTimeout);
                resizeTimeout = setTimeout(scaleLabels, 100);
            });
            observer.observe(button);
        }

        console.log('[DrawQuoteLabelSwitcher] Initialized with', labels.length, 'labels');
    }

    /**
     * Clean up resources.
     */
    function destroy() {
        stopTimer();
        if (measurementElement && measurementElement.parentNode) {
            measurementElement.parentNode.removeChild(measurementElement);
            measurementElement = null;
        }
        button = null;
        labelContainer = null;
        labels = [];
        currentLabelIndex = 0;
        isAnimating = false;
    }

    // Public API
    return {
        init: init,
        destroy: destroy,
        switchLabel: switchLabel,
        scaleLabels: scaleLabels,
        startTimer: startTimer,
        stopTimer: stopTimer,
        CONFIG: CONFIG
    };
})();

// Helper to update sessionId both in memory and sessionStorage
function updateSessionId(newId) {
    sessionId = newId;
    if (newId) {
        sessionStorage.setItem('chatSessionId', newId);
    }
}

// ============================================================================
// CONNECTIVITY SERVICE
// ============================================================================

/**
 * Check actual internet connectivity by pinging a lightweight external endpoint.
 * Uses no-cors mode so the fetch succeeds (opaque response) when online.
 * Debounces: requires CONNECTIVITY_FAIL_THRESHOLD consecutive failures before
 * reporting offline, but a single success restores online immediately.
 */
async function checkConnectivity() {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), CONNECTIVITY_TIMEOUT_MS);

    try {
        await fetch(CONNECTIVITY_CHECK_URL, {
            mode: 'no-cors',
            cache: 'no-store',
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        // Success — reset failures and go online
        consecutiveFailures = 0;
        if (!isOnline) {
            console.log('[Connectivity] Internet restored');
            setOnlineState(true);
        }
    } catch (_) {
        clearTimeout(timeoutId);
        consecutiveFailures++;

        if (isOnline && consecutiveFailures >= CONNECTIVITY_FAIL_THRESHOLD) {
            console.log('[Connectivity] Internet lost (after', consecutiveFailures, 'failures)');
            setOnlineState(false);
        }
    }
}

/**
 * Update the centralized online state and refresh UI controls.
 */
function setOnlineState(online) {
    isOnline = online;
    updateConnectivityUI();
}

/**
 * Enable/disable UI controls based on connectivity state.
 * Respects isWaiting — does not re-enable inputs during an active query.
 */
function updateConnectivityUI() {
    const voiceBtn = document.getElementById('voiceBtn');
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');

    if (!isOnline) {
        // Offline — disable all input controls
        if (userInput) {
            userInput.disabled = true;
            userInput.placeholder = 'No internet connection\u2026';
        }
        if (sendBtn) sendBtn.disabled = true;
        if (voiceBtn) {
            voiceBtn.disabled = true;
            voiceBtn.classList.add('disabled');
        }
    } else {
        // Online — re-enable controls (only if not mid-query)
        if (!isWaiting) {
            if (userInput) {
                userInput.disabled = false;
                userInput.placeholder = 'Type your question here...';
            }
            if (sendBtn) sendBtn.disabled = false;
        }
        // Voice button depends on voiceEnabled (set by initVoice)
        if (voiceBtn && typeof voiceEnabled !== 'undefined' && voiceEnabled && !isWaiting) {
            voiceBtn.disabled = false;
            voiceBtn.classList.remove('disabled');
        }
    }
}

/**
 * Start the connectivity monitor. Runs an immediate check then polls every
 * CONNECTIVITY_POLL_MS. Also listens for browser online/offline events for
 * faster detection.
 */
function startConnectivityMonitor() {
    // Immediate check on startup
    checkConnectivity();

    // Periodic polling
    connectivityCheckInterval = setInterval(checkConnectivity, CONNECTIVITY_POLL_MS);

    // Browser events for fast detection (supplement to polling)
    window.addEventListener('online', () => {
        console.log('[Connectivity] Browser online event');
        consecutiveFailures = 0;
        setOnlineState(true);
    });
    window.addEventListener('offline', () => {
        console.log('[Connectivity] Browser offline event');
        setOnlineState(false);
    });
}

// ============================================================================
// DOM ELEMENTS
// ============================================================================

const chatContainer = document.getElementById('chatContainer');
const chatForm = document.getElementById('chatForm');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const resetBtn = document.getElementById('resetBtn');
const loadingIndicator = document.getElementById('loadingIndicator');
const fullscreenBtn = document.getElementById('fullscreenBtn');
const refreshAdBtn = document.getElementById('refreshAdBtn'); // Phase 55
const kioskContainer = document.querySelector('.kiosk-container');

// ============================================================================
// THINKING ANIMATION
// ============================================================================

let thinkingInterval = null;

/**
 * Show the inline status panel below the input area with animated
 * "CoCo is thinking..." dots.  Reuses the existing #voiceStatus bar.
 * Safe to call multiple times — clears any existing animation first.
 */
function startThinkingAnimation() {
    stopThinkingAnimation();
    const voiceStatus = document.getElementById('voiceStatus');
    const voiceStatusText = voiceStatus?.querySelector('.voice-status-text');
    const voiceStatusIcon = voiceStatus?.querySelector('.voice-status-icon');
    if (!voiceStatus) return;

    voiceStatus.style.display = 'flex';
    voiceStatus.classList.add('processing');
    if (voiceStatusIcon) voiceStatusIcon.style.display = 'none';

    let dotCount = 1;
    if (voiceStatusText) voiceStatusText.textContent = 'CoCo is thinking.';
    thinkingInterval = setInterval(() => {
        dotCount = (dotCount % 3) + 1;
        if (voiceStatusText) voiceStatusText.textContent = 'CoCo is thinking' + '.'.repeat(dotCount);
    }, 500);
}

/**
 * Hide the thinking panel and stop the dot animation.
 */
function stopThinkingAnimation() {
    if (thinkingInterval) {
        clearInterval(thinkingInterval);
        thinkingInterval = null;
    }
    const voiceStatus = document.getElementById('voiceStatus');
    if (voiceStatus) {
        voiceStatus.style.display = 'none';
        voiceStatus.classList.remove('processing');
        const voiceStatusIcon = voiceStatus.querySelector('.voice-status-icon');
        if (voiceStatusIcon) voiceStatusIcon.style.display = '';
    }
}

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Set up event listeners
    chatForm.addEventListener('submit', handleSubmit);
    resetBtn.addEventListener('click', handleReset);

    // Set up fullscreen button with long-press detection for kiosk admin
    if (fullscreenBtn) {
        initKioskFullscreenButton(fullscreenBtn);
    }

    // Phase 55: Set up refresh advertisement button
    if (refreshAdBtn) {
        refreshAdBtn.addEventListener('click', handleRefreshAdvertisements);
    }

    // Listen for fullscreen changes to update button icon
    document.addEventListener('fullscreenchange', updateFullscreenButton);
    document.addEventListener('webkitfullscreenchange', updateFullscreenButton);

    // Detect initial fullscreen state (Chromium --start-fullscreen won't fire fullscreenchange)
    updateFullscreenButton();

    // Note: Auto-focus disabled to prevent virtual keyboard from obstructing view on RPi

    // Phase 48: Initialize advertisement slideshow
    initAdvertisementSlideshow();

    // Phase 49: Load welcome message from admin config
    loadWelcomeMessageContent();

    // Phase 50: Load display settings (metadata visibility)
    loadDisplaySettings();

    // Initialize FAQ section
    initFAQSection();

    // Start real-time connectivity monitoring
    startConnectivityMonitor();
});

// ============================================================================
// PHASE 48: ADVERTISEMENT SLIDESHOW
// ============================================================================

/**
 * Initialize the advertisement slideshow
 * Phase 55: Added auto-refresh timer (10 minutes)
 */
async function initAdvertisementSlideshow() {
    // Set up navigation click handlers
    const navLeft = document.getElementById('adNavLeft');
    const navRight = document.getElementById('adNavRight');

    if (navLeft) {
        navLeft.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('[ADS] Left nav clicked, going to previous');
            previousAdvertisement();
        });
    }
    if (navRight) {
        navRight.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('[ADS] Right nav clicked, going to next');
            nextAdvertisement();
        });
    }

    console.log('[ADS] Navigation handlers set up:', { navLeft: !!navLeft, navRight: !!navRight });

    // Set up ResizeObserver for adaptive text scaling
    const slideshow = document.getElementById('adSlideshow');
    if (slideshow) {
        AdaptiveTextScaler.createResizeObserver(slideshow);
    }

    // Load advertisements
    await loadAdvertisements();

    // Phase 55: Start auto-refresh timer (10 minutes)
    startAdAutoRefresh();
}

/**
 * Phase 55: Start the auto-refresh timer for advertisements
 * Refreshes every 10 minutes to pick up admin changes
 */
function startAdAutoRefresh() {
    // Clear any existing timer to prevent duplicates
    stopAdAutoRefresh();

    adAutoRefreshTimer = setInterval(async () => {
        console.log('[ADS] Auto-refreshing advertisements (10-minute interval)');
        await refreshAdvertisements();
    }, AD_AUTO_REFRESH_INTERVAL);

    console.log('[ADS] Auto-refresh timer started (interval:', AD_AUTO_REFRESH_INTERVAL / 1000, 'seconds)');
}

/**
 * Phase 55: Stop the auto-refresh timer
 * Called on cleanup or page unload
 */
function stopAdAutoRefresh() {
    if (adAutoRefreshTimer) {
        clearInterval(adAutoRefreshTimer);
        adAutoRefreshTimer = null;
        console.log('[ADS] Auto-refresh timer stopped');
    }
}

// Phase 55: Cleanup timers on page unload to prevent memory leaks
window.addEventListener('beforeunload', () => {
    stopAdAutoRefresh();
    stopAdRotation();
    stopTriviaRotation();
    stopQuoteTimer();
    stopFAQInactivityTimer();
});

// ============================================================================
// PHASE 56C: TRIVIA/STUDY TIPS/QUOTES SYSTEM (Final Layout)
// - Inline icon layout: [ICON] Content text...
// - Unified flip transition controller
// - Vertical flip animation (bottom-up)
// - Adaptive text scaling
// ============================================================================

// Trivia configuration
const TRIVIA_ROTATION_INTERVAL = 120000; // 2 minutes
const QUOTE_DISPLAY_DURATION = 60000;    // 1 minute
const TRIVIA_BUTTON_COOLDOWN = 5000;     // 5 seconds
const TRIVIA_FLIP_DURATION = 500;        // 0.5 seconds (match CSS)

// SVG Icons for each content type
const TRIVIA_ICONS = {
    // Lightbulb icon for trivia (ideas/curiosity)
    trivia: `<svg class="trivia-icon" viewBox="0 0 24 24" fill="currentColor">
        <path d="M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9v1zm3-19C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7zm2.85 11.1l-.85.6V16h-4v-2.3l-.85-.6A4.997 4.997 0 0 1 7 9c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.63-.8 3.16-2.15 4.1z"/>
    </svg>`,
    // Book icon for study tips (learning/education)
    study_tip: `<svg class="trivia-icon" viewBox="0 0 24 24" fill="currentColor">
        <path d="M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 4h5v8l-2.5-1.5L6 12V4z"/>
    </svg>`,
    // Quotation marks icon for quotes
    quote: `<svg class="trivia-icon" viewBox="0 0 24 24" fill="currentColor">
        <path d="M6 17h3l2-4V7H5v6h3zm8 0h3l2-4V7h-6v6h3z"/>
    </svg>`
};

// Trivia state
let triviaRotationTimer = null;
let quoteDisplayTimer = null;
let triviaButtonCooldown = false;
let triviaIsFlipping = false;
let currentTriviaMode = 'trivia'; // 'trivia', 'study_tip', or 'quote'
let triviaData = { trivia: '', study_tip: '', currentQuote: '' };

// Track which face is currently visible (for flip logic)
let triviaShowingFront = true;

// DOM Elements for Trivia (initialized on DOMContentLoaded)
let triviaCard, triviaContentFront, triviaContentBack;
let triviaIconContainerFront, triviaIconContainerBack, drawQuoteBtn;
let triviaFaceFront, triviaFaceBack;

/**
 * Initialize the trivia system
 */
async function initTriviaSystem() {
    console.log('[TRIVIA] Initializing trivia system...');

    // Get DOM elements
    triviaCard = document.getElementById('triviaCard');
    triviaFaceFront = document.getElementById('triviaFront');
    triviaFaceBack = document.getElementById('triviaBack');
    triviaContentFront = document.getElementById('triviaContent');
    triviaContentBack = document.getElementById('triviaContentBack');
    triviaIconContainerFront = document.getElementById('triviaIconContainer');
    triviaIconContainerBack = document.getElementById('triviaIconContainerBack');
    drawQuoteBtn = document.getElementById('drawQuoteBtn');

    if (!triviaCard) {
        console.warn('[TRIVIA] Trivia card not found, skipping initialization');
        return;
    }

    // Load today's content
    await loadTriviaContent();

    // Set up Draw Quote button
    if (drawQuoteBtn) {
        drawQuoteBtn.addEventListener('click', handleDrawQuote);
    }

    // Set up adaptive text scaling
    setupTriviaTextScaling();

    // Start rotation timer
    startTriviaRotation();

    console.log('[TRIVIA] Trivia system initialized');
}

/**
 * Load today's trivia and study tip from API
 */
async function loadTriviaContent() {
    try {
        const response = await fetch('/api/trivia/today');
        if (!response.ok) throw new Error('Failed to load trivia');

        const data = await response.json();
        triviaData.trivia = data.trivia || 'Engineering shapes our world!';
        triviaData.study_tip = data.study_tip || 'Stay curious, keep learning!';

        // Display initial content (trivia) without flip
        setTriviaFaceContent('front', 'trivia', triviaData.trivia);
        currentTriviaMode = 'trivia';

        console.log('[TRIVIA] Content loaded:', data.available ? 'available' : 'pending');
    } catch (error) {
        console.error('[TRIVIA] Failed to load content:', error);
        triviaData.trivia = 'Engineering shapes our world!';
        triviaData.study_tip = 'Stay curious, keep learning!';
        setTriviaFaceContent('front', 'trivia', triviaData.trivia);
        currentTriviaMode = 'trivia';
    }
}

/**
 * Set content on a specific face (front or back)
 * @param {string} face - 'front' or 'back'
 * @param {string} type - 'trivia', 'study_tip', or 'quote'
 * @param {string} content - The text content to display
 */
function setTriviaFaceContent(face, type, content) {
    const faceEl = face === 'front' ? triviaFaceFront : triviaFaceBack;
    const iconContainer = face === 'front' ? triviaIconContainerFront : triviaIconContainerBack;
    const contentEl = face === 'front' ? triviaContentFront : triviaContentBack;

    // Update card face type for background color
    if (faceEl) {
        faceEl.dataset.type = type;
    }

    // Update icon and icon container type
    if (iconContainer) {
        iconContainer.dataset.type = type;
        iconContainer.innerHTML = TRIVIA_ICONS[type] || TRIVIA_ICONS.trivia;
    }

    // Update content with adaptive font scaling
    if (contentEl) {
        contentEl.textContent = content;
        applyAdaptiveTextSize(contentEl);
    }
}

/**
 * Unified Transition Controller
 * Handles all content transitions with flip animation
 * @param {string} mode - Content type: 'trivia', 'study_tip', or 'quote'
 * @param {string} content - The text content to display
 */
function transitionToContent(mode, content) {
    if (triviaIsFlipping) return;
    triviaIsFlipping = true;

    // Determine which face to update (the hidden one)
    const targetFace = triviaShowingFront ? 'back' : 'front';

    // Set content on the hidden face
    setTriviaFaceContent(targetFace, mode, content);

    // Trigger flip
    if (triviaShowingFront) {
        triviaCard.classList.add('flipped');
    } else {
        triviaCard.classList.remove('flipped');
    }

    // Update state after flip completes
    setTimeout(() => {
        triviaShowingFront = !triviaShowingFront;
        currentTriviaMode = mode;
        triviaIsFlipping = false;
    }, TRIVIA_FLIP_DURATION);
}

/**
 * Start the trivia rotation timer (alternates every 2 minutes)
 */
function startTriviaRotation() {
    stopTriviaRotation();

    triviaRotationTimer = setInterval(() => {
        // Skip rotation if showing quote or flipping
        if (currentTriviaMode === 'quote' || triviaIsFlipping) {
            return;
        }

        // Alternate between trivia and study tip
        if (currentTriviaMode === 'trivia') {
            transitionToContent('study_tip', triviaData.study_tip);
        } else {
            transitionToContent('trivia', triviaData.trivia);
        }
    }, TRIVIA_ROTATION_INTERVAL);

    console.log('[TRIVIA] Rotation timer started (interval:', TRIVIA_ROTATION_INTERVAL / 1000, 'seconds)');
}

/**
 * Stop the trivia rotation timer
 */
function stopTriviaRotation() {
    if (triviaRotationTimer) {
        clearInterval(triviaRotationTimer);
        triviaRotationTimer = null;
    }
}

/**
 * Handle Draw Quote button click
 */
async function handleDrawQuote() {
    if (triviaButtonCooldown || triviaIsFlipping) {
        return;
    }

    startTriviaButtonCooldown();

    try {
        const response = await fetch('/api/trivia/quote');
        if (!response.ok) throw new Error('Failed to fetch quote');

        const data = await response.json();
        const quote = data.quote || 'Innovation distinguishes a leader from a follower.';

        showQuote(quote);
    } catch (error) {
        console.error('[TRIVIA] Failed to fetch quote:', error);
        showQuote('Engineering is the art of making dreams real.');
    }
}

/**
 * Show quote with flip animation
 */
function showQuote(quote) {
    triviaData.currentQuote = quote;

    // Transition to quote with flip
    transitionToContent('quote', quote);

    // Clear any existing timer
    stopQuoteTimer();

    // Set timer to return to rotation after 1 minute
    quoteDisplayTimer = setTimeout(() => {
        returnFromQuote();
    }, QUOTE_DISPLAY_DURATION);

    console.log('[TRIVIA] Showing quote for', QUOTE_DISPLAY_DURATION / 1000, 'seconds');
}

/**
 * Return from quote to normal rotation
 */
function returnFromQuote() {
    // Return to trivia (default after quote)
    transitionToContent('trivia', triviaData.trivia);
    console.log('[TRIVIA] Quote display ended, returning to trivia');
}

/**
 * Stop the quote display timer
 */
function stopQuoteTimer() {
    if (quoteDisplayTimer) {
        clearTimeout(quoteDisplayTimer);
        quoteDisplayTimer = null;
    }
}

/**
 * Start cooldown for Draw Quote button
 */
function startTriviaButtonCooldown() {
    triviaButtonCooldown = true;
    if (drawQuoteBtn) {
        drawQuoteBtn.disabled = true;
        drawQuoteBtn.classList.add('cooldown');
    }

    setTimeout(() => {
        triviaButtonCooldown = false;
        if (drawQuoteBtn) {
            drawQuoteBtn.disabled = false;
            drawQuoteBtn.classList.remove('cooldown');
        }
    }, TRIVIA_BUTTON_COOLDOWN);
}

// ============================================================================
// ADAPTIVE TEXT SCALING (Content-Measurement Based)
// ============================================================================

const TRIVIA_TEXT_CONFIG = {
    MIN_FONT_SIZE: 11,
    MAX_FONT_SIZE: 20,
    LINE_HEIGHT: 1.4,
    FONT_WEIGHT: 500
};

// Measurement element (created once, reused)
let triviaTextMeasurer = null;

/**
 * Get or create the off-screen measurement element
 * @returns {HTMLElement} The measurement element
 */
function getTextMeasurer() {
    if (!triviaTextMeasurer) {
        triviaTextMeasurer = document.createElement('span');
        triviaTextMeasurer.style.cssText = `
            position: absolute;
            visibility: hidden;
            white-space: normal;
            word-wrap: break-word;
            font-family: inherit;
            font-weight: ${TRIVIA_TEXT_CONFIG.FONT_WEIGHT};
            line-height: ${TRIVIA_TEXT_CONFIG.LINE_HEIGHT};
            padding: 0;
            margin: 0;
        `;
        document.body.appendChild(triviaTextMeasurer);
    }
    return triviaTextMeasurer;
}

/**
 * Measure if text fits within given dimensions at specified font size
 * @param {string} text - The text to measure
 * @param {number} fontSize - Font size in pixels
 * @param {number} maxWidth - Maximum width in pixels
 * @param {number} maxHeight - Maximum height in pixels
 * @returns {boolean} True if text fits
 */
function textFitsAtSize(text, fontSize, maxWidth, maxHeight) {
    const measurer = getTextMeasurer();
    measurer.style.fontSize = `${fontSize}px`;
    measurer.style.width = `${maxWidth}px`;
    measurer.textContent = text;

    return measurer.scrollHeight <= maxHeight;
}

/**
 * Apply adaptive text size using content measurement (binary search)
 * Maximizes font size while ensuring text fits without overflow
 * @param {HTMLElement} element - The content element to scale
 */
function applyAdaptiveTextSize(element) {
    if (!element) return;

    const text = element.textContent || '';
    if (!text.trim()) return;

    // Get container dimensions from parent (.trivia-content-area)
    const container = element.parentElement;
    if (!container) return;

    // Get available space (account for any padding)
    const containerStyle = getComputedStyle(container);
    const maxWidth = container.clientWidth -
        parseFloat(containerStyle.paddingLeft || 0) -
        parseFloat(containerStyle.paddingRight || 0);
    const maxHeight = container.clientHeight -
        parseFloat(containerStyle.paddingTop || 0) -
        parseFloat(containerStyle.paddingBottom || 0);

    // Skip if container has no size yet
    if (maxWidth <= 0 || maxHeight <= 0) return;

    // Binary search for optimal font size
    let minSize = TRIVIA_TEXT_CONFIG.MIN_FONT_SIZE;
    let maxSize = TRIVIA_TEXT_CONFIG.MAX_FONT_SIZE;
    let optimalSize = minSize;

    while (minSize <= maxSize) {
        const midSize = Math.floor((minSize + maxSize) / 2);

        if (textFitsAtSize(text, midSize, maxWidth, maxHeight)) {
            optimalSize = midSize;
            minSize = midSize + 1; // Try larger
        } else {
            maxSize = midSize - 1; // Try smaller
        }
    }

    // Apply the optimal font size
    element.style.fontSize = `${optimalSize}px`;
    element.style.lineHeight = String(TRIVIA_TEXT_CONFIG.LINE_HEIGHT);
}

/**
 * Set up ResizeObserver for adaptive text scaling
 */
function setupTriviaTextScaling() {
    // Initial scaling (with slight delay for DOM readiness)
    requestAnimationFrame(() => {
        if (triviaContentFront) applyAdaptiveTextSize(triviaContentFront);
        if (triviaContentBack) applyAdaptiveTextSize(triviaContentBack);
    });

    // Watch for container resizes
    if (triviaCard && window.ResizeObserver) {
        const observer = new ResizeObserver(() => {
            // Debounce resize handling
            requestAnimationFrame(() => {
                if (triviaContentFront) applyAdaptiveTextSize(triviaContentFront);
                if (triviaContentBack) applyAdaptiveTextSize(triviaContentBack);
            });
        });
        observer.observe(triviaCard);
    }
}

// Initialize trivia system on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    // Delay trivia init slightly to not block other initializations
    setTimeout(initTriviaSystem, 500);

    // Initialize Draw Quote label switcher
    setTimeout(() => {
        DrawQuoteLabelSwitcher.init('drawQuoteBtn');
    }, 600);
});

/**
 * Load advertisements from the API
 */
async function loadAdvertisements() {
    try {
        const response = await fetch('/api/advertisements');
        if (!response.ok) throw new Error('Failed to load advertisements');

        const data = await response.json();
        advertisements = data.advertisements || [];

        renderSlideshow();
    } catch (error) {
        console.error('[ADS] Failed to load advertisements:', error);
        showPlaceholder();
    }
}

/**
 * Render the slideshow based on loaded advertisements
 * Phase 54: Supports both image and text advertisements
 */
function renderSlideshow() {
    const slideshow = document.getElementById('adSlideshow');
    const placeholder = document.getElementById('adPlaceholder');
    const container = document.getElementById('adContainer');
    const indicators = document.getElementById('adIndicators');

    if (!slideshow || !placeholder || !container || !indicators) return;

    if (advertisements.length === 0) {
        // No ads - show placeholder
        showPlaceholder();
        return;
    }

    // Show slideshow, hide placeholder
    slideshow.style.display = 'block';
    placeholder.style.display = 'none';

    // Render ads (images and text)
    container.innerHTML = advertisements.map((ad, index) => renderAdItem(ad, index)).join('');

    // Render indicators
    indicators.innerHTML = advertisements.map((ad, index) => `
        <div class="ad-indicator ${index === 0 ? 'active' : ''}" data-index="${index}"></div>
    `).join('');

    // Add click handlers to indicators
    indicators.querySelectorAll('.ad-indicator').forEach(dot => {
        dot.addEventListener('click', () => {
            showAdvertisement(parseInt(dot.dataset.index));
            resetAdRotation();
        });
    });

    // Reset to first ad
    currentAdIndex = 0;

    // Start auto-rotation if more than one ad
    if (advertisements.length > 1) {
        startAdRotation();
    }

    // Apply adaptive text scaling after a brief delay to ensure layout is complete
    // Using requestAnimationFrame ensures DOM has been painted
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            AdaptiveTextScaler.scaleAllTextAds();
        });
    });
}

/**
 * Render a single advertisement item (image or text)
 * Phase 54: Added text advertisement support
 */
function renderAdItem(ad, index) {
    const isActive = index === 0 ? 'active' : '';

    // Check if it's a text ad (display.type === 'text' or ad_type === 'text')
    const displayData = ad.display || {};
    const isTextAd = displayData.type === 'text' || ad.ad_type === 'text';

    if (isTextAd) {
        // Text advertisement
        const content = displayData.content || ad.content || '';
        return `
            <div class="ad-item ad-text ${isActive}" data-index="${index}">
                <div class="ad-text-content">${formatAdText(content)}</div>
            </div>
        `;
    } else {
        // Image advertisement
        const url = displayData.url || ad.url || '';
        return `
            <img src="${url}" alt="Advertisement ${index + 1}" class="ad-item ad-image ${isActive}" data-index="${index}">
        `;
    }
}

/**
 * Format text for ad content display.
 * Escapes HTML for security and converts newlines to <br> for proper rendering.
 * Phase 54 fix: Centralized formatting utility for text ads.
 */
function formatAdText(text) {
    if (!text) return '';

    // Step 1: Escape HTML for security
    const div = document.createElement('div');
    div.textContent = text;
    let escaped = div.innerHTML;

    // Step 2: Convert newlines to <br> for proper line breaks
    // Handle both \r\n (Windows) and \n (Unix) line endings
    escaped = escaped.replace(/\r\n/g, '<br>');
    escaped = escaped.replace(/\n/g, '<br>');

    // Step 3: Convert multiple consecutive <br> to paragraph spacing
    escaped = escaped.replace(/(<br>){3,}/g, '<br><br>');

    return escaped;
}

/**
 * Show the placeholder when no advertisements are available
 */
function showPlaceholder() {
    const slideshow = document.getElementById('adSlideshow');
    const placeholder = document.getElementById('adPlaceholder');

    if (slideshow) slideshow.style.display = 'none';
    if (placeholder) placeholder.style.display = 'flex';

    stopAdRotation();
}

/**
 * Show a specific advertisement by index
 * Phase 54: Updated to handle both image and text ads using .ad-item class
 */
function showAdvertisement(index) {
    const container = document.getElementById('adContainer');
    const indicators = document.getElementById('adIndicators');

    console.log('[ADS] showAdvertisement called:', { index, totalAds: advertisements.length, currentAdIndex });

    if (!container || !indicators || advertisements.length === 0) {
        console.log('[ADS] Cannot show ad - missing container/indicators or no ads');
        return;
    }

    // Clamp index
    if (index < 0) index = advertisements.length - 1;
    if (index >= advertisements.length) index = 0;

    currentAdIndex = index;
    console.log('[ADS] Showing ad index:', currentAdIndex);

    // Update ad items (images and text ads)
    container.querySelectorAll('.ad-item').forEach((item, i) => {
        item.classList.toggle('active', i === index);
    });

    // Update indicators
    indicators.querySelectorAll('.ad-indicator').forEach((dot, i) => {
        dot.classList.toggle('active', i === index);
    });
}

/**
 * Go to the next advertisement
 */
function nextAdvertisement() {
    showAdvertisement(currentAdIndex + 1);
    resetAdRotation();
}

/**
 * Go to the previous advertisement
 */
function previousAdvertisement() {
    showAdvertisement(currentAdIndex - 1);
    resetAdRotation();
}

/**
 * Start the auto-rotation timer
 */
function startAdRotation() {
    stopAdRotation();
    if (advertisements.length > 1) {
        adRotationTimer = setInterval(() => {
            showAdvertisement(currentAdIndex + 1);
        }, AD_ROTATION_INTERVAL);
    }
}

/**
 * Stop the auto-rotation timer
 */
function stopAdRotation() {
    if (adRotationTimer) {
        clearInterval(adRotationTimer);
        adRotationTimer = null;
    }
}

/**
 * Reset the auto-rotation timer (called after manual navigation)
 */
function resetAdRotation() {
    startAdRotation();
}

// ============================================================================
// PHASE 50: DISPLAY SETTINGS (METADATA VISIBILITY)
// ============================================================================

/**
 * Load display settings from server (metadata visibility)
 */
async function loadDisplaySettings() {
    try {
        const response = await fetch('/api/settings');
        if (response.ok) {
            const data = await response.json();
            metadataVisible = data.metadata_visible;
            console.log('[SETTINGS] Metadata visible:', metadataVisible);
        }
    } catch (error) {
        console.error('[SETTINGS] Failed to load display settings:', error);
        // Default to visible on error
        metadataVisible = true;
    }
}

// ============================================================================
// PHASE 49: WELCOME MESSAGE LOADING
// ============================================================================

/**
 * Load welcome message from server and display it
 */
async function loadWelcomeMessageContent() {
    const welcomeText = document.getElementById('welcomeText');
    const welcomeImage = document.getElementById('welcomeImage');

    try {
        const response = await fetch('/api/welcome');
        if (!response.ok) throw new Error('Failed to load welcome message');

        const data = await response.json();

        // Format and display message
        if (welcomeText) {
            welcomeText.innerHTML = formatWelcomeText(data.message);
        }

        // Update image URL if provided (already set in HTML, but API can override)
        if (welcomeImage && data.image_url) {
            welcomeImage.src = data.image_url;
        }

        console.log('[WELCOME] Loaded welcome message from server');
    } catch (error) {
        console.error('[WELCOME] Failed to load:', error);
        // Fallback to default message
        if (welcomeText) {
            welcomeText.innerHTML = '<p class="large-text">Welcome! How can I help you today?</p>';
        }
    }
}

/**
 * Format welcome message text to HTML
 * Converts plain text with "- " bullet points to HTML lists
 */
function formatWelcomeText(text) {
    if (!text) return '';

    const lines = text.split('\n');
    let html = '';
    let inList = false;

    for (const line of lines) {
        const trimmed = line.trim();

        if (trimmed.startsWith('- ')) {
            // Bullet point item
            if (!inList) {
                html += '<ul class="examples-list">';
                inList = true;
            }
            html += `<li>${escapeHtmlWelcome(trimmed.substring(2))}</li>`;
        } else {
            // Regular text
            if (inList) {
                html += '</ul>';
                inList = false;
            }
            if (trimmed) {
                html += `<p class="large-text">${escapeHtmlWelcome(trimmed)}</p>`;
            }
        }
    }

    // Close any open list
    if (inList) html += '</ul>';

    return html;
}

/**
 * Escape HTML characters for safe display
 */
function escapeHtmlWelcome(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// MESSAGE HANDLING
// ============================================================================

/**
 * Add a user message to the chat
 */
function addUserMessage(text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user-message';
    messageDiv.innerHTML = `
        <div class="message-content">
            ${escapeHtml(text)}
        </div>
    `;
    chatContainer.appendChild(messageDiv);
    scrollToBottom();
}

/**
 * Render structured answer for kiosk display - Phase 17B.2
 * Shows full answer immediately without expand/collapse for better kiosk UX
 */
function renderStructuredAnswer(structured) {
    let html = '';

    // Full Answer - displayed directly for kiosk users
    // Phase 35: Use formatAnswerText to preserve formatting (lists, bold, paragraphs)
    if (structured.full_answer) {
        html += `
            <div class="answer-section">
                <div class="full-answer">${formatAnswerText(structured.full_answer)}</div>
            </div>
        `;
    } else if (structured.direct_answer) {
        // Fallback to direct_answer if full_answer not available
        html += `
            <div class="answer-section">
                <div class="full-answer">${formatAnswerText(structured.direct_answer)}</div>
            </div>
        `;
    }

    // Notes section (kept for important warnings)
    if (structured.notes) {
        html += `
            <div class="answer-section notes-section">
                <h3 class="section-heading">Notes</h3>
                <div>${formatAnswerText(structured.notes)}</div>
            </div>
        `;
    }

    // Disclaimer (kept for medium confidence answers)
    if (structured.disclaimer) {
        html += `<p class="disclaimer">${escapeHtml(structured.disclaimer)}</p>`;
    }

    return html;
}

/**
 * Add an assistant message to the chat
 */
function addAssistantMessage(data) {
    // Disable feedback on all previous messages
    disablePastFeedback();

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant-message';

    // Build message content
    let html = `<div class="message-content">`;

    // Phase 17B.1: Use structured_answer if available, otherwise fall back to plain answer
    if (data.structured_answer) {
        html += renderStructuredAnswer(data.structured_answer);
    } else {
        // Fallback to plain text answer - Phase 35: Use formatAnswerText for formatting
        html += `<div class="large-text">${formatAnswerText(data.answer)}</div>`;
    }

    // Phase 51: Read metadata visibility from response (server-authoritative)
    const showMetadata = data.metadata_visible !== false;

    // Phase 50/51: Conditionally render confidence badge and score based on response setting
    if (showMetadata) {
        const confidenceClass = `confidence-${data.confidence_level.toLowerCase()}`;
        html += `
            <div class="confidence-badge ${confidenceClass}">
                Confidence: ${data.confidence_level}
            </div>
            <div class="confidence-score">
                Score: ${data.confidence_score}/100
            </div>
        `;
    }

    // Phase 50B/51: Mode badges controlled by response metadata_visible
    if (showMetadata) {
        if (data.mode === 'campus') {
            html += `<div class="mode-badge mode-campus">📚 Based on campus documents</div>`;
        } else if (data.mode === 'general') {
            html += `<div class="mode-badge mode-general">🤖 Based on general AI knowledge</div>`;
        } else if (data.mode === 'clarification') {
            html += `<div class="mode-badge mode-clarification">❓ Needs clarification</div>`;
        }
    }

    // Fusion mode label (controlled by server-side fusion_label_visible)
    if (data.fusion_label_visible && data.fusion_mode) {
        const fusionLabel = data.fusion_mode === 'rrf' ? 'Fusion: RRF' : 'Fusion: Linear';
        html += `<div class="fusion-label">${fusionLabel}</div>`;
    }

    // Phase 50/51: Conditionally render sources based on response setting
    if (showMetadata && data.sources && data.sources.length > 0) {
        html += `
            <div class="sources">
                <div class="sources-title">Sources:</div>
        `;
        data.sources.forEach(source => {
            html += `
                <div class="source-item">
                    ${escapeHtml(source.document_name)} - ${escapeHtml(source.section)}
                </div>
            `;
        });
        html += `</div>`;
    }

    // Warning for rejected answers
    if (data.rejected) {
        html += `
            <div class="warning-message">
                &#9888; This answer was generated with low confidence. Please try rephrasing your question or ask about a different topic.
            </div>
        `;
    }

    // Feedback buttons (only for non-rejected AI answers, not system errors)
    if (!data.rejected && data.mode !== 'system_error') {
        const feedbackId = `feedback-${Date.now()}`;
        const queryId = data.timestamp || '';
        html += `
            <div class="feedback-container" id="${feedbackId}" data-query-id="${escapeHtml(queryId)}">
                <div class="feedback-icons">
                    <button class="feedback-icon-btn thumbs-up" onclick="submitFeedback('${feedbackId}', true)" aria-label="Helpful" title="Helpful">
                        <svg viewBox="0 0 24 24" fill="currentColor" width="28" height="28">
                            <path d="M2 20h2c.55 0 1-.45 1-1v-9c0-.55-.45-1-1-1H2v11zm19.83-7.12c.11-.25.17-.52.17-.8V11c0-1.1-.9-2-2-2h-5.5l.92-4.65c.05-.22.02-.46-.08-.66-.23-.45-.52-.86-.88-1.22L14 2 7.59 8.41C7.21 8.79 7 9.3 7 9.83v7.84C7 18.95 8.05 20 9.34 20h8.11c.7 0 1.36-.37 1.72-.97l2.66-6.15z"/>
                        </svg>
                    </button>
                    <button class="feedback-icon-btn thumbs-down" onclick="submitFeedback('${feedbackId}', false)" aria-label="Not helpful" title="Not helpful">
                        <svg viewBox="0 0 24 24" fill="currentColor" width="28" height="28">
                            <path d="M22 4h-2c-.55 0-1 .45-1 1v9c0 .55.45 1 1 1h2V4zM2.17 11.12c-.11.25-.17.52-.17.8V13c0 1.1.9 2 2 2h5.5l-.92 4.65c-.05.22-.02.46.08.66.23.45.52.86.88 1.22L10 22l6.41-6.41c.38-.38.59-.89.59-1.42V6.34C17 5.05 15.95 4 14.66 4h-8.1c-.71 0-1.36.37-1.72.97l-2.67 6.15z"/>
                        </svg>
                    </button>
                </div>
            </div>
        `;
    }

    // Phase 39B: Add debug panel if debug_info is present
    console.log('[DEBUG] Response data:', data);
    console.log('[DEBUG] debug_info:', data.debug_info);
    if (data.debug_info) {
        console.log('[DEBUG] Rendering debug panel');
        html += renderDebugPanel(data.debug_info);
    }

    html += `</div>`;
    messageDiv.innerHTML = html;

    chatContainer.appendChild(messageDiv);
    scrollToBottom();
}

/**
 * Add an error message to the chat
 */
function addErrorMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message system-message';
    messageDiv.innerHTML = `
        <div class="message-content">
            <p class="large-text" style="color: #f44336;">
                &#10007; ${escapeHtml(message)}
            </p>
        </div>
    `;
    chatContainer.appendChild(messageDiv);
    scrollToBottom();
}

// ============================================================================
// API COMMUNICATION
// ============================================================================

/**
 * Send a chat message to the API
 */
async function sendMessage(message) {
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Server error');
        }

        const data = await response.json();

        // Store session ID - always store if provided
        if (data.session_id) {
            updateSessionId(data.session_id);
        }

        return data;
    } catch (error) {
        console.error('Error sending message:', error);
        throw error;
    }
}

// ============================================================================
// PHASE 47: STREAMING RESPONSE SUPPORT
// ============================================================================

// Streaming mode toggle - can be enabled/disabled
let streamingEnabled = true;

/**
 * Phase 47: Send message with streaming response via SSE
 * Progressive token delivery for improved responsiveness
 */
async function sendMessageStreaming(message) {
    // Create streaming message container
    const messageDiv = createStreamingMessageContainer();
    chatContainer.appendChild(messageDiv);

    const contentDiv = messageDiv.querySelector('.streaming-content');
    const metadataDiv = messageDiv.querySelector('.streaming-metadata');

    let fullAnswer = '';
    let metadata = null;
    let currentEvent = null;

    try {
        const response = await fetch('/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        // Read SSE stream using ReadableStream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';  // Keep incomplete line in buffer

            for (const line of lines) {
                if (line.startsWith('event:')) {
                    currentEvent = line.slice(6).trim();
                } else if (line.startsWith('data:') && currentEvent) {
                    const data = JSON.parse(line.slice(5).trim());

                    if (currentEvent === 'metadata') {
                        metadata = data;
                        updateSessionId(data.session_id);
                        renderStreamingMetadata(metadataDiv, metadata);
                        // Hide thinking animation once metadata arrives
                        stopThinkingAnimation();
                    } else if (currentEvent === 'token') {
                        fullAnswer += data.content;
                        // Update content with formatted text and cursor
                        contentDiv.innerHTML = formatAnswerText(fullAnswer) +
                            '<span class="streaming-cursor">▋</span>';
                        scrollToBottom();
                    } else if (currentEvent === 'complete') {
                        // Finalize the message
                        finalizeStreamingMessage(messageDiv, metadata, data, fullAnswer);
                    } else if (currentEvent === 'error') {
                        const err = new Error(data.message);
                        if (data.code === 'network_error') err.isNetworkError = true;
                        throw err;
                    }

                    currentEvent = null;  // Reset for next event
                }
            }
        }

        return { answer: fullAnswer, metadata: metadata };

    } catch (error) {
        console.error('Streaming error:', error);
        // For network errors, show the server's message directly (it's user-friendly)
        const displayMsg = error.isNetworkError
            ? escapeHtml(error.message)
            : `Error: ${escapeHtml(error.message)}`;
        contentDiv.innerHTML = `<span class="error-text">${displayMsg}</span>`;
        messageDiv.classList.remove('streaming');
        throw error;
    }
}

/**
 * Phase 47: Create container for streaming message with cursor
 */
function createStreamingMessageContainer() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant-message streaming';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="streaming-metadata"></div>
            <div class="streaming-content">
                <span class="streaming-cursor">▋</span>
            </div>
        </div>
    `;
    return messageDiv;
}

/**
 * Phase 47: Render metadata (confidence, sources, mode) immediately
 * Phase 50/51: Conditionally renders based on metadata.metadata_visible setting
 */
function renderStreamingMetadata(container, metadata) {
    let html = '';

    // Phase 51: Read metadata visibility from response (server-authoritative)
    const showMetadata = metadata.metadata_visible !== false;

    // Phase 50/51: Conditionally render confidence badge and score
    if (showMetadata) {
        const confidenceClass = `confidence-${metadata.confidence_level.toLowerCase()}`;
        html += `
            <div class="confidence-badge ${confidenceClass}">
                Confidence: ${metadata.confidence_level}
            </div>
            <div class="confidence-score">
                Score: ${Math.round(metadata.confidence_score)}/100
            </div>
        `;
    }

    // Phase 50B/51: Mode badges controlled by response metadata_visible
    if (showMetadata) {
        if (metadata.mode === 'campus') {
            html += `<div class="mode-badge mode-campus">📚 Based on campus documents</div>`;
        } else if (metadata.mode === 'general') {
            html += `<div class="mode-badge mode-general">🤖 Based on general AI knowledge</div>`;
        }
    }

    // Fusion mode label (controlled by server-side fusion_label_visible)
    if (metadata.fusion_label_visible && metadata.fusion_mode) {
        const fusionLabel = metadata.fusion_mode === 'rrf' ? 'Fusion: RRF' : 'Fusion: Linear';
        html += `<div class="fusion-label">${fusionLabel}</div>`;
    }

    container.innerHTML = html;
}

/**
 * Phase 47: Finalize streaming message with complete data
 * Phase 50/51: Conditionally renders sources based on metadata.metadata_visible setting
 */
function finalizeStreamingMessage(messageDiv, metadata, completeData, fullAnswer) {
    // Disable feedback on all previous messages
    disablePastFeedback();

    messageDiv.classList.remove('streaming');

    // Remove cursor
    const cursor = messageDiv.querySelector('.streaming-cursor');
    if (cursor) cursor.remove();

    // Update content without cursor
    const contentDiv = messageDiv.querySelector('.streaming-content');
    contentDiv.innerHTML = `<div class="large-text">${formatAnswerText(fullAnswer)}</div>`;

    // Phase 51: Read metadata visibility from response (server-authoritative)
    const showMetadata = metadata.metadata_visible !== false;

    // Phase 50/51: Conditionally render sources based on response setting
    if (showMetadata && metadata.sources && metadata.sources.length > 0) {
        const sourcesHtml = `
            <div class="sources">
                <div class="sources-title">Sources:</div>
                ${metadata.sources.map(s => `
                    <div class="source-item">
                        ${escapeHtml(s.document_name)} - ${escapeHtml(s.section)}
                    </div>
                `).join('')}
            </div>
        `;
        messageDiv.querySelector('.message-content').insertAdjacentHTML('beforeend', sourcesHtml);
    }

    // Add feedback buttons with queryId from metadata timestamp
    const feedbackId = `feedback-${Date.now()}`;
    const queryId = metadata.timestamp || '';
    const feedbackHtml = `
        <div class="feedback-container" id="${feedbackId}" data-query-id="${escapeHtml(queryId)}">
            <div class="feedback-icons">
                <button class="feedback-icon-btn thumbs-up" onclick="submitFeedback('${feedbackId}', true)" aria-label="Helpful" title="Helpful">
                    <svg viewBox="0 0 24 24" fill="currentColor" width="28" height="28">
                        <path d="M2 20h2c.55 0 1-.45 1-1v-9c0-.55-.45-1-1-1H2v11zm19.83-7.12c.11-.25.17-.52.17-.8V11c0-1.1-.9-2-2-2h-5.5l.92-4.65c.05-.22.02-.46-.08-.66-.23-.45-.52-.86-.88-1.22L14 2 7.59 8.41C7.21 8.79 7 9.3 7 9.83v7.84C7 18.95 8.05 20 9.34 20h8.11c.7 0 1.36-.37 1.72-.97l2.66-6.15z"/>
                    </svg>
                </button>
                <button class="feedback-icon-btn thumbs-down" onclick="submitFeedback('${feedbackId}', false)" aria-label="Not helpful" title="Not helpful">
                    <svg viewBox="0 0 24 24" fill="currentColor" width="28" height="28">
                        <path d="M22 4h-2c-.55 0-1 .45-1 1v9c0 .55.45 1 1 1h2V4zM2.17 11.12c-.11.25-.17.52-.17.8V13c0 1.1.9 2 2 2h5.5l-.92 4.65c-.05.22-.02.46.08.66.23.45.52.86.88 1.22L10 22l6.41-6.41c.38-.38.59-.89.59-1.42V6.34C17 5.05 15.95 4 14.66 4h-8.1c-.71 0-1.36.37-1.72.97l-2.67 6.15z"/>
                    </svg>
                </button>
            </div>
        </div>
    `;
    messageDiv.querySelector('.message-content').insertAdjacentHTML('beforeend', feedbackHtml);

    // Add debug panel if debug_info is present
    if (metadata.debug_info) {
        // Add timing from complete event
        metadata.debug_info.timing = completeData.timing;
        const debugHtml = renderDebugPanel(metadata.debug_info);
        messageDiv.querySelector('.message-content').insertAdjacentHTML('beforeend', debugHtml);
    }

    scrollToBottom();
}

/**
 * Disable feedback buttons on all previous assistant messages.
 * Called before rendering a new assistant message so only the latest has active feedback.
 */
function disablePastFeedback() {
    document.querySelectorAll('.feedback-container').forEach(container => {
        container.querySelectorAll('.feedback-icon-btn').forEach(btn => {
            btn.disabled = true;
        });
        container.classList.add('feedback-disabled');
    });
}

/**
 * Submit feedback for a response
 */
async function submitFeedback(feedbackId, isHelpful) {
    // Read the query ID from the feedback container's data attribute
    const feedbackContainer = document.getElementById(feedbackId);
    const queryId = feedbackContainer?.dataset?.queryId || lastQueryId || 'unknown';

    try {
        const response = await fetch('/feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionId,
                query_id: queryId,
                is_helpful: isHelpful
            })
        });

        if (response.ok) {
            // Show selected state on clicked button, disable both
            if (feedbackContainer) {
                const buttons = feedbackContainer.querySelectorAll('.feedback-icon-btn');
                buttons.forEach(btn => {
                    btn.disabled = true;
                    if ((isHelpful && btn.classList.contains('thumbs-up')) ||
                        (!isHelpful && btn.classList.contains('thumbs-down'))) {
                        btn.classList.add('selected');
                    }
                });
            }
        }
    } catch (error) {
        console.error('Error submitting feedback:', error);
    }
}

/**
 * Reset the conversation
 */
async function resetConversation() {
    try {
        if (sessionId) {
            await fetch('/reset', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: sessionId
                })
            });
        }

        // Reset state
        sessionId = null;
        sessionStorage.removeItem('chatSessionId');
        lastQueryId = null;

        // Clear chat (keep welcome message)
        const messages = chatContainer.querySelectorAll('.message');
        messages.forEach((msg, index) => {
            if (index > 0) {  // Keep first message (welcome)
                msg.remove();
            }
        });

        // Phase 49: Reload welcome message in case admin updated it
        await loadWelcomeMessageContent();

        // Reload FAQ data from backend in case admin updated it
        faqExpanded = false;
        await loadFAQs();

        // Re-check voice service availability (may have changed during runtime)
        await initVoice();

        // Note: Auto-focus disabled to prevent virtual keyboard from obstructing view on RPi
    } catch (error) {
        console.error('Error resetting conversation:', error);
    }
}

// ============================================================================
// EVENT HANDLERS
// ============================================================================

/**
 * Handle form submission
 */
async function handleSubmit(event) {
    event.preventDefault();

    if (isWaiting || !isOnline) {
        return;
    }

    const message = userInput.value.trim();

    if (!message) {
        return;
    }

    // Disable input
    isWaiting = true;
    userInput.disabled = true;
    sendBtn.disabled = true;
    userInput.value = '';

    // Show user message
    addUserMessage(message);

    // Show thinking animation
    startThinkingAnimation();

    try {
        // Phase 47: Use streaming if enabled (and TTS disabled for now)
        // Streaming provides progressive token delivery for better UX
        // Note: TTS currently not compatible with streaming - use non-streaming for TTS
        if (streamingEnabled && !ttsEnabled) {
            console.log('[Phase 47] Using streaming response...');
            const result = await sendMessageStreaming(message);
            lastQueryId = Date.now();

        } else {
            // Non-streaming path (original behavior)
            // Send to API
            const data = await sendMessage(message);

            // Store query ID for feedback
            lastQueryId = data.timestamp;

            // Phase 41: Synchronized text-voice delivery
            // If TTS enabled, synthesize audio BEFORE showing text
            // Note: TTS plays for ALL answers including graceful refusals (rejected=true)
            console.log('[Phase 41] TTS check:', { ttsEnabled, hasAnswer: !!data.answer });
            if (ttsEnabled && data.answer) {
                // Keep thinking animation visible during TTS synthesis

                // Synthesize TTS (keep loading indicator visible)
                console.log('[Phase 41] Synthesizing TTS for typed input...');
                const ttsResult = await synthesizeTTSOnly(data.answer);
                console.log('[Phase 41] TTS synthesis result:', ttsResult ? `Blob size: ${ttsResult.blob.size}, Engine: ${ttsResult.engine}` : 'null');

                // Add TTS engine info to debug_info from synthesis response header
                if (ttsResult && data.debug_info) {
                    data.debug_info.tts_engine = ttsResult.engine;
                }

                // Hide thinking animation
                stopThinkingAnimation();

                // Show text and play audio together
                addAssistantMessage(data);
                if (ttsResult) {
                    console.log('[Phase 41] Playing audio blob...');
                    playAudioBlob(ttsResult.blob);
                } else {
                    console.log('[Phase 41] No audio blob to play');
                }
            } else {
                // No TTS - show text immediately
                console.log('[Phase 41] Skipping TTS:', { ttsEnabled, hasAnswer: !!data.answer });
                stopThinkingAnimation();
                addAssistantMessage(data);
            }
        }

    } catch (error) {
        // Hide thinking animation
        stopThinkingAnimation();

        // Network-aware error message
        if (error.isNetworkError || !navigator.onLine) {
            addErrorMessage("It looks like there's no internet connection. I'm unable to process your request right now.");
        } else {
            addErrorMessage('Sorry, I encountered an error processing your request. Please try again.');
        }
    } finally {
        // Re-enable input (respects connectivity state)
        isWaiting = false;
        if (isOnline) {
            userInput.disabled = false;
            sendBtn.disabled = false;
        }
        // Note: Auto-focus disabled to prevent virtual keyboard from obstructing view on RPi
    }
}

/**
 * Handle reset button click
 * Phase 55: Removed confirmation dialog, added 5-second cooldown
 */
async function handleReset(event) {
    event.preventDefault();

    // Check cooldown
    if (resetButtonCooldown) {
        return;
    }

    // Start cooldown
    startResetCooldown();

    // Reset conversation directly (no confirmation)
    await resetConversation();
}

/**
 * Phase 55: Start cooldown for reset button
 */
function startResetCooldown() {
    resetButtonCooldown = true;
    resetBtn.disabled = true;
    resetBtn.classList.add('cooldown');

    setTimeout(() => {
        resetButtonCooldown = false;
        resetBtn.disabled = false;
        resetBtn.classList.remove('cooldown');
    }, BUTTON_COOLDOWN_MS);
}

/**
 * Phase 55: Handle refresh advertisements button click
 * Manual refresh with 5-second cooldown
 */
async function handleRefreshAdvertisements(event) {
    if (event) event.preventDefault();

    // Check cooldown
    if (refreshAdButtonCooldown) {
        return;
    }

    // Start cooldown
    startRefreshAdCooldown();

    // Refresh advertisements
    await refreshAdvertisements();
}

/**
 * Phase 55: Start cooldown for refresh ad button
 */
function startRefreshAdCooldown() {
    refreshAdButtonCooldown = true;
    if (refreshAdBtn) {
        refreshAdBtn.disabled = true;
        refreshAdBtn.classList.add('cooldown');
    }

    setTimeout(() => {
        refreshAdButtonCooldown = false;
        if (refreshAdBtn) {
            refreshAdBtn.disabled = false;
            refreshAdBtn.classList.remove('cooldown');
        }
    }, BUTTON_COOLDOWN_MS);
}

/**
 * Phase 55: Refresh advertisements from API
 * Re-fetches latest advertisements without breaking carousel state
 */
async function refreshAdvertisements() {
    console.log('[ADS] Refreshing advertisements...');

    try {
        // Store current position
        const previousIndex = currentAdIndex;

        // Re-load advertisements
        await loadAdvertisements();

        // Try to maintain position if possible
        if (advertisements.length > 0) {
            const newIndex = Math.min(previousIndex, advertisements.length - 1);
            if (newIndex !== 0) {
                showAdvertisement(newIndex);
            }
        }

        console.log('[ADS] Advertisements refreshed successfully');
    } catch (error) {
        console.error('[ADS] Failed to refresh advertisements:', error);
    }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Scroll chat container to bottom
 */
function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Convert text with markdown-like formatting to HTML
 * Handles: numbered lists, bullet lists, bold, line breaks, paragraphs
 * Phase 35: Fix formatting regression
 */
function formatAnswerText(text) {
    if (!text) return '';

    // First escape HTML entities
    let html = escapeHtml(text);

    // Convert markdown-style bold (**text**) to <strong>
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Convert numbered lists (1. item, 2. item) - must be at start of line
    html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<li value="$1">$2</li>');

    // Convert bullet lists (- item or * item) - must be at start of line
    html = html.replace(/^[-*]\s+(.+)$/gm, '<li>$1</li>');

    // Wrap consecutive <li> items in appropriate list tags
    html = html.replace(/((?:<li[^>]*>.*<\/li>\s*)+)/g, function(match) {
        // Check if it's a numbered list (has value attribute)
        if (match.includes('value="')) {
            return '<ol class="answer-list">' + match + '</ol>';
        }
        return '<ul class="answer-list">' + match + '</ul>';
    });

    // Convert double newlines to paragraph breaks
    html = html.replace(/\n\n+/g, '</p><p>');

    // Convert single newlines to <br> (but not inside lists)
    html = html.replace(/\n(?![<])/g, '<br>');

    // Wrap in paragraph if not already wrapped
    if (!html.startsWith('<ol') && !html.startsWith('<ul') && !html.startsWith('<p>')) {
        html = '<p>' + html + '</p>';
    }

    // Clean up empty paragraphs
    html = html.replace(/<p>\s*<\/p>/g, '');

    return html;
}

/**
 * Make submitFeedback available globally for onclick handlers
 */
window.submitFeedback = submitFeedback;

// ============================================================================
// KIOSK FULLSCREEN + LONG PRESS ADMIN ACCESS
// ============================================================================

// When true, fullscreen detection is overridden to return false.
// Set by exitFullscreen() to handle --start-fullscreen/--kiosk mode where
// the Fullscreen API has no control over the browser window state.
let fullscreenOverrideActive = false;

/**
 * Enter fullscreen mode (never exits on normal tap).
 * Exiting fullscreen is only allowed via kiosk admin overlay.
 */
function enterFullscreen() {
    fullscreenOverrideActive = false;
    if (!document.fullscreenElement && !document.webkitFullscreenElement) {
        const elem = kioskContainer || document.documentElement;
        if (elem.requestFullscreen) {
            elem.requestFullscreen();
        } else if (elem.webkitRequestFullscreen) {
            elem.webkitRequestFullscreen();
        }
    }
}

/**
 * Exit fullscreen mode (admin-only action).
 * Handles both DOM Fullscreen API and Chromium --start-fullscreen/--kiosk.
 */
function exitFullscreen() {
    // Exit DOM Fullscreen API if active
    if (document.fullscreenElement || document.webkitFullscreenElement) {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        }
    }
    // Override detection for --start-fullscreen mode (no API to exit,
    // but we revert the UI to non-fullscreen state)
    fullscreenOverrideActive = true;
    updateFullscreenButton();
}

/**
 * Detect fullscreen state (both Fullscreen API and Chromium --start-fullscreen/--kiosk).
 * Respects the manual override set by exitFullscreen().
 */
function detectFullscreen() {
    if (fullscreenOverrideActive) return false;
    if (document.fullscreenElement || document.webkitFullscreenElement) return true;
    if (window.innerWidth >= screen.width && window.innerHeight >= screen.height) return true;
    return false;
}

/**
 * Update fullscreen button icon based on current state.
 */
function updateFullscreenButton() {
    const isFS = detectFullscreen();
    const icon = fullscreenBtn?.querySelector('.fullscreen-icon');

    if (icon) {
        icon.innerHTML = isFS ? '&#x26F6;' : '&#x26F6;';
    }

    if (kioskContainer) {
        kioskContainer.classList.toggle('fullscreen-mode', isFS);
    }
    document.body.classList.toggle('fullscreen-active', isFS);
}

/**
 * Initialize the fullscreen button with long-press detection.
 * Short tap: enter fullscreen (no exit).
 * 5-second hold: show kiosk admin overlay.
 */
function initKioskFullscreenButton(btn) {
    const LONG_PRESS_MS = 5000;
    let pressTimer = null;
    let isLongPress = false;

    function startPress(e) {
        // Prevent default to avoid text selection / context menu on long press
        e.preventDefault();
        isLongPress = false;
        pressTimer = setTimeout(() => {
            isLongPress = true;
            showKioskAdminOverlay();
        }, LONG_PRESS_MS);
    }

    function endPress(e) {
        if (pressTimer) {
            clearTimeout(pressTimer);
            pressTimer = null;
        }
        if (!isLongPress) {
            // Short tap: enter fullscreen only (never exit)
            enterFullscreen();
        }
        isLongPress = false;
    }

    function cancelPress() {
        if (pressTimer) {
            clearTimeout(pressTimer);
            pressTimer = null;
        }
        isLongPress = false;
    }

    // Mouse events
    btn.addEventListener('mousedown', startPress);
    btn.addEventListener('mouseup', endPress);
    btn.addEventListener('mouseleave', cancelPress);

    // Touch events
    btn.addEventListener('touchstart', startPress, { passive: false });
    btn.addEventListener('touchend', endPress);
    btn.addEventListener('touchcancel', cancelPress);
}

// ============================================================================
// KIOSK ADMIN OVERLAY
// ============================================================================

/**
 * Show the kiosk admin overlay modal.
 */
function showKioskAdminOverlay() {
    const overlay = document.getElementById('kioskAdminOverlay');
    const pwdInput = document.getElementById('kioskAdminPassword');
    const errorEl = document.getElementById('kioskAdminError');
    if (!overlay) return;

    overlay.classList.add('visible');
    errorEl.textContent = '';
    pwdInput.value = '';
    pwdInput.type = 'password';
    pwdInput.focus();

    // Reset all password toggle buttons to "Show"
    overlay.querySelectorAll('.kiosk-password-toggle').forEach(btn => btn.textContent = 'Show');

    // Fetch WiFi status
    loadKioskWifiStatus();
}

/**
 * Fetch and display the current WiFi SSID and IP address in the kiosk admin panel.
 */
async function loadKioskWifiStatus() {
    const wifiEl = document.getElementById('kioskWifiStatus');
    const ipEl = document.getElementById('kioskIpAddress');
    if (!wifiEl) return;
    wifiEl.textContent = 'WiFi: checking...';
    if (ipEl) ipEl.textContent = 'IP Address: checking...';
    try {
        const resp = await fetch('/admin/kiosk/wifi');
        const data = await resp.json();
        if (data.ssid) {
            wifiEl.textContent = `Connected WiFi: ${data.ssid}`;
            wifiEl.style.color = '#4ade80';
        } else {
            wifiEl.textContent = data.message || 'No WiFi connection detected';
            wifiEl.style.color = '#f87171';
        }
        if (ipEl) {
            if (data.ip_address) {
                ipEl.textContent = `IP Address: ${data.ip_address}`;
                ipEl.style.color = '#4ade80';
            } else {
                ipEl.textContent = 'IP Address: Not available';
                ipEl.style.color = '#f87171';
            }
        }
    } catch {
        wifiEl.textContent = 'WiFi: unable to check';
        wifiEl.style.color = '#f87171';
        if (ipEl) {
            ipEl.textContent = 'IP Address: Not available';
            ipEl.style.color = '#f87171';
        }
    }
}

/**
 * Hide the kiosk admin overlay modal.
 */
function hideKioskAdminOverlay() {
    const overlay = document.getElementById('kioskAdminOverlay');
    if (overlay) {
        overlay.classList.remove('visible');
        // Reset password fields to hidden and toggle buttons to "Show"
        overlay.querySelectorAll('.kiosk-admin-input[type="text"]').forEach(input => {
            if (input.id === 'kioskAdminPassword' || input.id === 'kioskWifiPassword') {
                input.type = 'password';
            }
        });
        overlay.querySelectorAll('.kiosk-password-toggle').forEach(btn => btn.textContent = 'Show');
    }
    // Blur password fields so the virtual keyboard hides
    const pwdInput = document.getElementById('kioskAdminPassword');
    if (pwdInput) pwdInput.blur();
    const wifiPwd = document.getElementById('kioskWifiPassword');
    if (wifiPwd) wifiPwd.blur();

    // Reset to main view and clear stored password
    document.getElementById('kioskMainView').style.display = '';
    document.getElementById('kioskWifiView').style.display = 'none';
    kioskAdminStoredPassword = '';
    kioskSelectedWifiSSID = '';
}

/**
 * Authenticate kiosk admin and perform an action.
 * @param {string} action - 'exit_fullscreen' | 'shutdown' | 'reboot' | 'wifi_settings'
 */
async function kioskAdminAction(action) {
    const pwdInput = document.getElementById('kioskAdminPassword');
    const errorEl = document.getElementById('kioskAdminError');
    const password = pwdInput?.value || '';

    if (!password) {
        errorEl.textContent = 'Please enter the admin password.';
        return;
    }

    errorEl.textContent = '';

    if (action === 'exit_fullscreen') {
        // Validate password via backend, then exit fullscreen locally
        try {
            const resp = await fetch('/admin/kiosk/auth', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });
            if (!resp.ok) {
                errorEl.textContent = 'Invalid password.';
                return;
            }
            hideKioskAdminOverlay();
            exitFullscreen();
        } catch (err) {
            errorEl.textContent = 'Connection error. Try again.';
        }
    } else if (action === 'shutdown' || action === 'reboot') {
        try {
            const resp = await fetch(`/admin/kiosk/${action}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });
            const data = await resp.json();
            if (!resp.ok) {
                errorEl.textContent = data.detail || 'Action failed.';
                return;
            }
            errorEl.style.color = '#4ade80';
            errorEl.textContent = data.message || 'Command sent.';
        } catch (err) {
            errorEl.textContent = 'Connection error. Try again.';
        }
    } else if (action === 'wifi_settings') {
        // Verify password then switch to WiFi view
        try {
            const resp = await fetch('/admin/kiosk/auth', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });
            if (!resp.ok) {
                errorEl.textContent = 'Invalid password.';
                return;
            }
            kioskAdminStoredPassword = password;
            showKioskWifiView();
        } catch (err) {
            errorEl.textContent = 'Connection error. Try again.';
        }
    }
}

// ============================================================================
// KIOSK WIFI SETTINGS
// ============================================================================

// Stored admin password for WiFi operations (cleared on overlay close/back)
let kioskAdminStoredPassword = '';
let kioskSelectedWifiSSID = '';

/**
 * Switch to the WiFi settings view.
 */
function showKioskWifiView() {
    document.getElementById('kioskMainView').style.display = 'none';
    document.getElementById('kioskWifiView').style.display = '';

    // Load current WiFi status
    loadKioskWifiCurrent();

    // Reset state
    kioskSelectedWifiSSID = '';
    document.getElementById('kioskWifiConnectSection').style.display = 'none';
    setKioskWifiMessage('', '');
}

/**
 * Switch back to the main admin view.
 */
function showKioskMainView() {
    document.getElementById('kioskWifiView').style.display = 'none';
    document.getElementById('kioskMainView').style.display = '';
    kioskAdminStoredPassword = '';
    kioskSelectedWifiSSID = '';

    // Blur WiFi password field so VKB hides
    const wifiPwd = document.getElementById('kioskWifiPassword');
    if (wifiPwd) wifiPwd.blur();

    // Refresh the WiFi status label to reflect any changes made in WiFi settings
    loadKioskWifiStatus();
}

/**
 * Load current WiFi SSID into the WiFi view header.
 */
async function loadKioskWifiCurrent() {
    const el = document.getElementById('kioskWifiCurrent');
    if (!el) return;
    el.textContent = 'Connected: checking...';
    el.style.color = '#94a3b8';
    try {
        const resp = await fetch('/admin/kiosk/wifi');
        const data = await resp.json();
        if (data.ssid) {
            el.textContent = `Connected: ${data.ssid}`;
            el.style.color = '#4ade80';
        } else {
            el.textContent = 'Not connected';
            el.style.color = '#f87171';
        }
    } catch {
        el.textContent = 'Unable to check';
        el.style.color = '#f87171';
    }
}

/**
 * Scan for available WiFi networks.
 */
async function scanKioskWifi() {
    const listEl = document.getElementById('kioskWifiList');
    const scanBtn = document.getElementById('kioskWifiScanBtn');

    listEl.innerHTML = '<p class="kiosk-wifi-empty">Scanning...</p>';
    scanBtn.disabled = true;
    scanBtn.textContent = 'Scanning...';
    setKioskWifiMessage('', '');
    document.getElementById('kioskWifiConnectSection').style.display = 'none';
    kioskSelectedWifiSSID = '';

    try {
        const resp = await fetch('/admin/kiosk/wifi/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: kioskAdminStoredPassword })
        });

        if (resp.status === 401) {
            setKioskWifiMessage('Session expired. Go back and re-enter password.', 'error');
            listEl.innerHTML = '';
            return;
        }

        const data = await resp.json();

        if (!data.networks || data.networks.length === 0) {
            listEl.innerHTML = `<p class="kiosk-wifi-empty">${data.message || 'No networks found'}</p>`;
            return;
        }

        listEl.innerHTML = data.networks.map(n => {
            const sigClass = n.signal >= 70 ? 'strong' : n.signal >= 50 ? 'good' : n.signal >= 30 ? 'weak' : 'very-weak';
            const lockIcon = n.security && n.security !== '--' ? '&#x1F512;' : '';
            return `<div class="kiosk-wifi-item" data-ssid="${escapeHtml(n.ssid)}" onclick="selectKioskWifi(this)">
                <span class="kiosk-wifi-item-ssid">${escapeHtml(n.ssid)}</span>
                <span class="kiosk-wifi-item-info">
                    <span class="kiosk-wifi-signal ${sigClass}">${n.signal}%</span>
                    <span class="kiosk-wifi-lock">${lockIcon}</span>
                </span>
            </div>`;
        }).join('');

    } catch (err) {
        setKioskWifiMessage('Scan failed. Check connection.', 'error');
        listEl.innerHTML = '<p class="kiosk-wifi-empty">Scan failed</p>';
    } finally {
        // 5-second cooldown to prevent rapid repeated scans
        let cooldown = 5;
        scanBtn.textContent = `Wait ${cooldown}s`;
        const interval = setInterval(() => {
            cooldown--;
            if (cooldown <= 0) {
                clearInterval(interval);
                scanBtn.disabled = false;
                scanBtn.textContent = 'Scan Networks';
            } else {
                scanBtn.textContent = `Wait ${cooldown}s`;
            }
        }, 1000);
    }
}

/**
 * Select a WiFi network from the scan list.
 */
function selectKioskWifi(el) {
    // Deselect previous
    document.querySelectorAll('.kiosk-wifi-item.selected').forEach(item => item.classList.remove('selected'));

    // Select this one
    el.classList.add('selected');
    kioskSelectedWifiSSID = el.getAttribute('data-ssid');

    // Show connect section
    const connectSection = document.getElementById('kioskWifiConnectSection');
    const label = document.getElementById('kioskWifiSelectedLabel');
    const wifiPwd = document.getElementById('kioskWifiPassword');

    label.textContent = `Network: ${kioskSelectedWifiSSID}`;
    wifiPwd.value = '';
    connectSection.style.display = '';
    setKioskWifiMessage('', '');
}

/**
 * Connect to the selected WiFi network.
 */
async function connectKioskWifi() {
    if (!kioskSelectedWifiSSID) return;

    const wifiPwd = document.getElementById('kioskWifiPassword');
    const wifiPassword = wifiPwd?.value || '';

    setKioskWifiMessage('Connecting...', 'info');

    try {
        const resp = await fetch('/admin/kiosk/wifi/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                password: kioskAdminStoredPassword,
                ssid: kioskSelectedWifiSSID,
                wifi_password: wifiPassword
            })
        });

        if (resp.status === 401) {
            setKioskWifiMessage('Session expired. Go back and re-enter password.', 'error');
            return;
        }

        const data = await resp.json();

        if (data.status === 'success') {
            setKioskWifiMessage(data.message || 'Connected!', 'success');
            loadKioskWifiCurrent();
        } else {
            setKioskWifiMessage(data.message || 'Connection failed.', 'error');
        }
    } catch (err) {
        setKioskWifiMessage('Connection error. Try again.', 'error');
    }
}

/**
 * Set the WiFi feedback message.
 */
function setKioskWifiMessage(text, type) {
    const el = document.getElementById('kioskWifiMessage');
    if (!el) return;
    el.textContent = text;
    el.className = 'kiosk-wifi-message' + (type ? ' ' + type : '');
}

/**
 * Escape HTML to prevent XSS in rendered network names.
 */
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Expose for onclick handlers in the overlay HTML
window.hideKioskAdminOverlay = hideKioskAdminOverlay;
window.kioskAdminAction = kioskAdminAction;
window.showKioskMainView = showKioskMainView;
window.scanKioskWifi = scanKioskWifi;
window.selectKioskWifi = selectKioskWifi;
window.connectKioskWifi = connectKioskWifi;

/**
 * Toggle password field visibility between hidden and visible.
 * Shared by admin login and WiFi password fields.
 */
function togglePasswordVisibility(inputId, toggleBtn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === 'password') {
        input.type = 'text';
        toggleBtn.textContent = 'Hide';
    } else {
        input.type = 'password';
        toggleBtn.textContent = 'Show';
    }
}

window.togglePasswordVisibility = togglePasswordVisibility;

// ============================================================================
// PHASE 39B: DEBUG PANEL
// ============================================================================

/**
 * Phase 39B: Render debug panel for a response
 * Shows technical details about how the response was generated
 */
function renderDebugPanel(debugInfo) {
    if (!debugInfo) return '';

    // Format timing values
    const formatMs = (ms) => ms ? `${ms}ms` : '--';

    // Build timing section - Phase 42: Enhanced with STT/TTS and Resolution timing
    let timingHtml = '';
    if (debugInfo.timing) {
        const t = debugInfo.timing;
        // Build timing rows dynamically based on available data
        let timingRows = '';

        // Voice timing (if present)
        if (t.stt_ms !== undefined) {
            timingRows += `<div class="debug-row"><span class="debug-label">STT:</span> ${formatMs(t.stt_ms)}</div>`;
        }

        // Resolution timing for deterministic paths
        if (t.resolution_ms !== undefined) {
            timingRows += `<div class="debug-row"><span class="debug-label">Resolution:</span> ${formatMs(t.resolution_ms)}</div>`;
        }

        // Standard LLM-based timing
        if (t.retrieval_ms !== undefined) {
            timingRows += `<div class="debug-row"><span class="debug-label">Retrieval:</span> ${formatMs(t.retrieval_ms)}</div>`;
        }
        if (t.llm_ms !== undefined) {
            timingRows += `<div class="debug-row"><span class="debug-label">LLM:</span> ${formatMs(t.llm_ms)}</div>`;
        }

        // TTS timing (if present)
        if (t.tts_ms !== undefined) {
            timingRows += `<div class="debug-row"><span class="debug-label">TTS:</span> ${formatMs(t.tts_ms)}</div>`;
        }

        // Total timing
        if (t.total_ms !== undefined) {
            timingRows += `<div class="debug-row"><span class="debug-label">Total:</span> ${formatMs(t.total_ms)}</div>`;
        }

        // Only show timing section if we have rows
        if (timingRows) {
            timingHtml = `
                <div class="debug-column">
                    <div class="debug-column-title">TIMING</div>
                    ${timingRows}
                </div>
            `;
        }
    }

    // Build grounding status
    const groundingStatus = debugInfo.grounding_passed ? '✓ Passed' : '✗ Failed';
    const groundingClass = debugInfo.grounding_passed ? 'grounding-passed' : 'grounding-failed';

    // Build query terms display
    let queryTermsHtml = '';
    if (debugInfo.query_terms && debugInfo.query_terms.length > 0) {
        queryTermsHtml = debugInfo.query_terms.map(term =>
            `<span class="debug-term">${escapeHtml(term)}</span>`
        ).join(' ');
    } else {
        queryTermsHtml = '<span class="debug-term none">none</span>';
    }

    // Build extractor info
    let extractorHtml = '';
    if (debugInfo.extractor_used) {
        extractorHtml = `<div class="debug-row"><span class="debug-label">Extractor:</span> ${escapeHtml(debugInfo.extractor_used)}</div>`;
    }

    // Build voice info - always show for consistency
    // For text input: STT shows "N/A (text input)", TTS shows engine or status
    // For voice input: STT and TTS show actual engine names
    const sttDisplay = debugInfo.stt_engine
        ? `${escapeHtml(debugInfo.stt_engine)}${debugInfo.stt_fallback_used ? ' (fallback)' : ''}`
        : 'N/A (text input)';
    const ttsDisplay = debugInfo.tts_engine
        ? `${escapeHtml(debugInfo.tts_engine)}${debugInfo.tts_fallback_used ? ' (fallback)' : ''}`
        : (ttsEnabled ? 'Active' : 'Disabled');

    const voiceHtml = `
        <div class="debug-column">
            <div class="debug-column-title">VOICE</div>
            <div class="debug-row"><span class="debug-label">STT:</span> ${sttDisplay}</div>
            <div class="debug-row"><span class="debug-label">TTS:</span> ${ttsDisplay}</div>
        </div>
    `;

    return `
        <div class="debug-panel collapsed">
            <div class="debug-header" onclick="toggleDebugPanel(this)">
                <span class="debug-icon">&#9881;</span>
                <span class="debug-title">Debug Info</span>
                <span class="debug-expand">▼</span>
            </div>
            <div class="debug-content">
                <div class="debug-grid">
                    <div class="debug-column">
                        <div class="debug-column-title">PROVIDER</div>
                        <div class="debug-row"><span class="debug-label">LLM:</span> ${escapeHtml(debugInfo.llm_model || 'gpt-4o-mini')}</div>
                        <div class="debug-row"><span class="debug-label">Provider:</span> ${escapeHtml(debugInfo.llm_provider || 'openai')}</div>
                    </div>
                    <div class="debug-column">
                        <div class="debug-column-title">RETRIEVAL</div>
                        <div class="debug-row"><span class="debug-label">Mode:</span> ${escapeHtml(debugInfo.retrieval_mode || 'hybrid')}</div>
                        <div class="debug-row"><span class="debug-label">Method:</span> ${escapeHtml(debugInfo.retrieval_method || 'rrf')}</div>
                        <div class="debug-row"><span class="debug-label">Chunks:</span> ${debugInfo.chunks_retrieved || 0}</div>
                        <div class="debug-row"><span class="debug-label">Top Score:</span> ${(debugInfo.top_chunk_score || 0).toFixed(3)}</div>
                    </div>
                    <div class="debug-column">
                        <div class="debug-column-title">ROUTING</div>
                        <div class="debug-row"><span class="debug-label">Intent:</span> ${escapeHtml(debugInfo.intent_classified || '--')}</div>
                        <div class="debug-row"><span class="debug-label">Path:</span> ${escapeHtml(debugInfo.routing_path || '--')}</div>
                        <div class="debug-row"><span class="debug-label ${groundingClass}">Ground:</span> ${groundingStatus}</div>
                        ${extractorHtml}
                    </div>
                    ${voiceHtml}
                    ${timingHtml}
                </div>
                <div class="debug-terms">
                    <span class="debug-terms-label">Query Terms:</span> ${queryTermsHtml}
                </div>
            </div>
        </div>
    `;
}

/**
 * Phase 39B: Toggle debug panel expanded/collapsed
 */
function toggleDebugPanel(header) {
    const panel = header.parentElement;
    panel.classList.toggle('collapsed');
    const expand = header.querySelector('.debug-expand');
    if (expand) {
        expand.textContent = panel.classList.contains('collapsed') ? '▼' : '▲';
    }
}

// Make toggleDebugPanel available globally for onclick
window.toggleDebugPanel = toggleDebugPanel;

// ============================================================================
// PHASE 34: VOICE UI
// ============================================================================

/**
 * Voice State Machine
 * States: IDLE, LISTENING, PROCESSING, RESPONDING, ERROR
 */
const VoiceState = {
    IDLE: 'idle',
    LISTENING: 'listening',
    PROCESSING: 'processing',
    RESPONDING: 'responding',
    ERROR: 'error'
};

let voiceState = VoiceState.IDLE;
let mediaRecorder = null;
let audioChunks = [];
let voiceEnabled = false;
let ttsEnabled = false;

// DOM Elements for Voice
const voiceBtn = document.getElementById('voiceBtn');
const voiceStatus = document.getElementById('voiceStatus');
const voiceStatusText = voiceStatus?.querySelector('.voice-status-text');
const transcriptionPreview = document.getElementById('transcriptionPreview');
const previewText = transcriptionPreview?.querySelector('.preview-text');
// Phase 40: voiceIndicator and stopSpeakingBtn removed - TTS plays silently
const loadingText = document.getElementById('loadingText');
const ttsAudio = document.getElementById('ttsAudio');

// Audio Visualizer Elements
const audioVisualizerContainer = document.getElementById('audioVisualizerContainer');
const audioVisualizerCanvas = document.getElementById('audioVisualizer');
let audioContext = null;
let analyserNode = null;
let visualizerAnimationId = null;

// Silence Detection Configuration (Phase 35: Auto-stop on speech end)
// NOTE: SPEECH_THRESHOLD is also used by the backend silence trimmer
// (audio_utils.py SPEECH_RMS_THRESHOLD) to trim leading silence before
// STT.  If you change SPEECH_THRESHOLD here, update the backend constant
// too:  new_value × 32768 = backend RMS threshold.
const SILENCE_DETECTION = {
    SILENCE_THRESHOLD: 0.015,      // RMS below this = silence
    SPEECH_THRESHOLD: 0.025,       // RMS above this = speech detected
    SILENCE_DURATION_MS: 1500,     // Silence duration to trigger stop
    MIN_SPEECH_DURATION_MS: 300,   // Minimum speech before allowing auto-stop
};

// Silence Detection State
let silenceDetectionState = {
    speechDetected: false,         // Has user started speaking?
    speechStartTime: null,         // When did speech begin?
    silenceStartTime: null,        // When did current silence period begin?
    lastRMS: 0,                    // Last computed RMS value
};

// ============================================================================
// VOICE INITIALIZATION
// ============================================================================

/**
 * Check voice service availability on page load
 */
async function initVoice() {
    try {
        const response = await fetch('/voice/status');
        if (response.ok) {
            const data = await response.json();
            console.log('[Phase 41] Voice status:', data);
            voiceEnabled = data.voice_enabled && data.stt_available;
            ttsEnabled = data.voice_enabled && data.tts_available;
            console.log('[Phase 41] Voice/TTS enabled:', { voiceEnabled, ttsEnabled });

            if (voiceEnabled) {
                voiceBtn.disabled = false;
                voiceBtn.title = 'Click to speak';
                voiceBtn.classList.remove('disabled');
            } else {
                voiceBtn.disabled = true;
                voiceBtn.title = 'Voice input unavailable';
                voiceBtn.classList.add('disabled');
            }
        } else {
            console.log('[Phase 41] Voice status request failed:', response.status);
        }
    } catch (error) {
        console.log('Voice services not available:', error);
        voiceBtn.disabled = true;
        voiceBtn.title = 'Voice services not available';
    }
}

// Initialize voice on page load
document.addEventListener('DOMContentLoaded', () => {
    initVoice();

    // Set up voice button click handler
    if (voiceBtn) {
        voiceBtn.addEventListener('click', handleVoiceClick);
    }

    // Set up transcription preview buttons
    if (transcriptionPreview) {
        transcriptionPreview.querySelector('.preview-edit')?.addEventListener('click', handlePreviewEdit);
        transcriptionPreview.querySelector('.preview-send')?.addEventListener('click', handlePreviewSend);
        transcriptionPreview.querySelector('.preview-cancel')?.addEventListener('click', handlePreviewCancel);
    }

    // Phase 40: Remove stop speaking button handler (no longer needed)
    // Stop button removed from UI - interruption is now implicit

    // TTS audio event handlers
    if (ttsAudio) {
        ttsAudio.addEventListener('ended', () => {
            // Phase 41: Cleanup object URL when audio finishes
            cleanupAudioUrl();
            setVoiceState(VoiceState.IDLE);
        });
        ttsAudio.addEventListener('error', () => {
            // Phase 41: Cleanup object URL on error
            cleanupAudioUrl();
            setVoiceState(VoiceState.IDLE);
        });
    }

    // =========================================================================
    // Phase 40: Centralized TTS Interruption
    // Any user input automatically stops TTS playback
    // =========================================================================
    initTTSInterruption();
});

/**
 * Phase 40: Initialize TTS interruption listeners
 * Stops any playing TTS when user interacts with input controls
 */
function initTTSInterruption() {
    // List of events that should interrupt TTS
    // Note: focus/click on userInput removed - only actual typing interrupts TTS
    const interruptionBindings = [
        // Voice button - interrupt before starting recording
        { element: voiceBtn, event: 'click', handler: interruptTTS },
        // Text input - only interrupt when user actually types
        { element: userInput, event: 'input', handler: interruptTTS },
        // Send button
        { element: sendBtn, event: 'click', handler: interruptTTS },
        // Form submission (covers Enter key)
        { element: chatForm, event: 'submit', handler: interruptTTS },
    ];

    interruptionBindings.forEach(({ element, event, handler }) => {
        if (element) {
            element.addEventListener(event, handler);
        }
    });

    console.log('[Phase 40] TTS interruption listeners initialized');
}

// ============================================================================
// VOICE STATE MANAGEMENT
// ============================================================================

/**
 * Set voice state and update UI accordingly
 */
function setVoiceState(newState, message = null) {
    voiceState = newState;

    // Update button state
    voiceBtn.classList.remove('listening', 'processing', 'error', 'speaking');

    // Update status display
    if (voiceStatus) {
        voiceStatus.classList.remove('processing', 'error', 'speaking');
    }

    switch (newState) {
        case VoiceState.IDLE:
            voiceBtn.disabled = !voiceEnabled || !isOnline;
            stopThinkingAnimation();
            // Re-enable typed input when voice returns to idle (respects connectivity)
            if (!isWaiting && isOnline) {
                userInput.disabled = false;
                sendBtn.disabled = false;
            }
            break;

        case VoiceState.LISTENING:
            voiceBtn.classList.add('listening');
            voiceBtn.disabled = false;
            voiceStatus.style.display = 'flex';
            // Phase 35: Updated message to indicate auto-stop behavior
            if (voiceStatusText) voiceStatusText.textContent = message || 'Listening... (speak now)';
            break;

        case VoiceState.PROCESSING:
            voiceBtn.classList.add('processing');
            voiceBtn.disabled = true;
            startThinkingAnimation();
            break;

        case VoiceState.RESPONDING:
            // Phase 40: Silent TTS - no visual indicator, audio plays in background
            // Keep UI in normal state so user can read response while listening
            voiceBtn.disabled = !voiceEnabled || !isOnline;
            stopThinkingAnimation();
            // Phase 41 fix: Re-enable inputs during RESPONDING so user can interact
            // while TTS plays (respects connectivity state)
            if (isOnline) {
                userInput.disabled = false;
                sendBtn.disabled = false;
            }
            break;

        case VoiceState.ERROR:
            stopThinkingAnimation();
            voiceBtn.classList.add('error');
            voiceBtn.disabled = !isOnline;
            voiceStatus.style.display = 'flex';
            voiceStatus.classList.add('error');
            if (voiceStatusText) voiceStatusText.textContent = message || 'Error occurred';
            // Re-enable typed input on error so user can fall back to typing (respects connectivity)
            if (!isWaiting && isOnline) {
                userInput.disabled = false;
                sendBtn.disabled = false;
            }

            // Auto-clear error after 3 seconds
            setTimeout(() => {
                if (voiceState === VoiceState.ERROR) {
                    setVoiceState(VoiceState.IDLE);
                }
            }, 3000);
            break;
    }
}

// ============================================================================
// AUDIO RECORDING
// ============================================================================

/**
 * Handle voice button click - toggle recording
 */
async function handleVoiceClick() {
    if (!isOnline) return;

    if (voiceState === VoiceState.LISTENING) {
        // Stop recording
        stopRecording();
    } else if (voiceState === VoiceState.IDLE) {
        // Start recording
        await startRecording();
    }
}

/**
 * Start audio recording
 */
async function startRecording() {
    try {
        // Request microphone access
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                channelCount: 1,
                sampleRate: 16000,
                echoCancellation: true,
                noiseSuppression: true
            }
        });

        // Create MediaRecorder
        const options = { mimeType: 'audio/webm' };
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
            // Fallback for Safari
            options.mimeType = 'audio/mp4';
            if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                options.mimeType = '';
            }
        }

        mediaRecorder = new MediaRecorder(stream, options);
        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = async () => {
            // Stop all tracks
            stream.getTracks().forEach(track => track.stop());

            // Process the recorded audio
            if (audioChunks.length > 0) {
                const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
                await processVoiceInput(audioBlob);
            } else {
                setVoiceState(VoiceState.ERROR, 'No audio recorded');
            }
        };

        mediaRecorder.onerror = (event) => {
            console.error('MediaRecorder error:', event.error);
            setVoiceState(VoiceState.ERROR, 'Recording error');
            stopAudioVisualizer();
            stream.getTracks().forEach(track => track.stop());
        };

        // Initialize audio visualizer
        initAudioVisualizer(stream);

        // Disable typed input while voice is active to prevent conflicts
        userInput.disabled = true;
        sendBtn.disabled = true;

        // Start recording
        mediaRecorder.start(100); // Collect data every 100ms
        setVoiceState(VoiceState.LISTENING);

        // Auto-stop after 30 seconds
        setTimeout(() => {
            if (voiceState === VoiceState.LISTENING && mediaRecorder?.state === 'recording') {
                stopRecording();
            }
        }, 30000);

    } catch (error) {
        console.error('Error starting recording:', error);
        stopAudioVisualizer();
        if (error.name === 'NotAllowedError') {
            setVoiceState(VoiceState.ERROR, 'Microphone access denied');
        } else {
            setVoiceState(VoiceState.ERROR, 'Could not start recording');
        }
    }
}

/**
 * Stop audio recording
 */
function stopRecording() {
    // Stop visualizer first
    stopAudioVisualizer();

    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        setVoiceState(VoiceState.PROCESSING, 'Processing audio...');
    }
}

// ============================================================================
// VOICE API INTEGRATION
// ============================================================================

/**
 * Process voice input - send to API
 */
async function processVoiceInput(audioBlob) {
    try {
        // Create form data
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');
        formData.append('session_id', sessionId || '');
        formData.append('skip_tts', ttsEnabled ? 'false' : 'true');

        // Send to voice chat endpoint with timeout to prevent indefinite hang
        const voiceChatController = new AbortController();
        const voiceChatTimeout = setTimeout(() => voiceChatController.abort(), 30000);

        let response;
        try {
            response = await fetch('/voice/chat', {
                method: 'POST',
                body: formData,
                signal: voiceChatController.signal
            });
        } finally {
            clearTimeout(voiceChatTimeout);
        }

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail?.message || error.detail || 'Voice processing failed');
        }

        const data = await response.json();

        // Update session ID
        if (data.session_id) {
            updateSessionId(data.session_id);
        }

        // Show transcription (API returns transcribed_text)
        if (data.transcribed_text) {
            addUserMessage(data.transcribed_text);
        }

        // If STT/chat failed with an error_message but no answer, surface it as the answer
        const displayAnswer = data.answer || data.error_message || '';
        const isSystemError = !data.answer && !!data.error_message;

        // Build response object for addAssistantMessage
        // System errors: hide all metadata (confidence, score, fusion, warnings)
        const chatResponse = displayAnswer ? {
            answer: displayAnswer,
            mode: isSystemError ? 'system_error' : (data.mode || 'campus'),
            confidence_level: isSystemError ? '' : (data.confidence || 'Low'),
            confidence_score: isSystemError ? 0 : (Math.round(data.transcription_confidence * 100) || 50),
            sources: isSystemError ? [] : (data.sources || []),
            rejected: false,
            structured_answer: isSystemError ? null : (data.structured_answer || null),
            debug_info: isSystemError ? null : (data.debug_info || null),
            metadata_visible: isSystemError ? false : data.metadata_visible,
            fusion_mode: isSystemError ? null : data.fusion_mode,
            fusion_label_visible: isSystemError ? false : data.fusion_label_visible,
            timestamp: data.timestamp
        } : null;

        // Phase 41: Synchronized text-voice delivery
        // Fetch audio BEFORE displaying text for unified experience
        if (data.has_audio && data.audio_url && ttsEnabled && chatResponse) {
            // Extract audio_id from audio_url (e.g., "/voice/audio/xxx" -> "xxx")
            const audioId = data.audio_url.split('/').pop();

            // Fetch audio blob before showing text
            const audioBlob = await fetchAudioBlob(audioId);

            // Show text and play audio together
            addAssistantMessage(chatResponse);
            lastQueryId = data.timestamp || Date.now();

            if (audioBlob) {
                playAudioBlob(audioBlob);
            } else {
                setVoiceState(VoiceState.IDLE);
            }
        } else if (isSystemError && chatResponse && ttsEnabled) {
            // System error with no server-side audio — synthesize locally via Piper TTS
            addAssistantMessage(chatResponse);
            const ttsResult = await synthesizeTTSOnly(displayAnswer);
            if (ttsResult) {
                playAudioBlob(ttsResult.blob);
            } else {
                setVoiceState(VoiceState.IDLE);
            }
        } else {
            // No TTS - show text immediately
            if (chatResponse) {
                addAssistantMessage(chatResponse);
                lastQueryId = data.timestamp || Date.now();
            }
            setVoiceState(VoiceState.IDLE);
        }

    } catch (error) {
        console.error('Voice processing error:', error);

        // Detect timeout/network errors and show a clear message
        let userMessage;
        if (error.name === 'AbortError') {
            userMessage = 'Voice request timed out. Please check your internet connection and try again.';
        } else if (!navigator.onLine) {
            userMessage = 'No internet connection. Please reconnect and try again.';
        } else {
            userMessage = 'Voice processing failed. Please try again or type your question.';
        }

        setVoiceState(VoiceState.ERROR, error.message || 'Voice processing failed');
        addErrorMessage(userMessage);
    }
}

/**
 * Transcribe audio only (without chat)
 */
async function transcribeAudio(audioBlob) {
    try {
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');
        formData.append('language', 'en');

        const response = await fetch('/voice/transcribe', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail?.message || 'Transcription failed');
        }

        const data = await response.json();
        return data.text;

    } catch (error) {
        console.error('Transcription error:', error);
        throw error;
    }
}

// ============================================================================
// TTS PLAYBACK
// ============================================================================

/**
 * Play TTS audio response from stored audio ID
 * Phase 40: Silent playback - no visual indicators
 * Phase 41: Uses cleanup for memory management
 */
async function playTTSResponse(audioId) {
    try {
        // Phase 40: Interrupt any existing playback first
        interruptTTS();
        cleanupAudioUrl();

        // Fetch audio
        const response = await fetch(`/voice/audio/${audioId}`);
        if (!response.ok) {
            throw new Error('Could not fetch audio');
        }

        const audioBlob = await response.blob();
        currentAudioObjectUrl = URL.createObjectURL(audioBlob);

        // Phase 40: Track that we're playing (for interruption detection)
        setVoiceState(VoiceState.RESPONDING);

        // Play audio silently in background
        ttsAudio.src = currentAudioObjectUrl;
        await ttsAudio.play();

    } catch (error) {
        // Phase 40: Silent failure - don't disrupt UI
        console.log('TTS playback error (silent):', error);
        cleanupAudioUrl();
        setVoiceState(VoiceState.IDLE);
    }
}

/**
 * Phase 35: Synthesize and play TTS for typed input responses
 * Phase 40: Silent playback - no visual indicators
 * Phase 41: Uses cleanup for memory management (legacy function)
 * Note: New code should use synthesizeTTSOnly() + playAudioBlob() for sync
 */
async function synthesizeAndPlayTTS(text) {
    if (!ttsEnabled || !text) {
        return;
    }

    try {
        // Phase 40: Interrupt any existing playback first
        interruptTTS();
        cleanupAudioUrl();

        // Call synthesize endpoint
        const response = await fetch('/voice/synthesize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text: text })
        });

        if (!response.ok) {
            console.log('TTS synthesis failed (silent):', response.status);
            return;
        }

        // Get audio blob and play
        const audioBlob = await response.blob();
        currentAudioObjectUrl = URL.createObjectURL(audioBlob);

        // Phase 40: Track that we're playing (for interruption detection)
        setVoiceState(VoiceState.RESPONDING);

        // Play audio silently in background
        ttsAudio.src = currentAudioObjectUrl;
        await ttsAudio.play();

    } catch (error) {
        // Phase 40: Silent failure - don't disrupt UI
        console.log('TTS synthesis error (silent):', error);
        cleanupAudioUrl();
    }
}

/**
 * Phase 40: Interrupt any playing TTS audio
 * Central function called from all user interaction points
 * Idempotent - safe to call multiple times
 * Phase 41: Also cleans up object URL to prevent memory leaks
 */
function interruptTTS() {
    if (ttsAudio && !ttsAudio.paused) {
        ttsAudio.pause();
        ttsAudio.currentTime = 0;
        // Phase 41: Cleanup object URL when interrupted
        cleanupAudioUrl();
        // Reset to IDLE only if we were in RESPONDING state
        if (voiceState === VoiceState.RESPONDING) {
            setVoiceState(VoiceState.IDLE);
        }
    }
}

// ============================================================================
// PHASE 41: SYNCHRONIZED TEXT-VOICE RESPONSE HELPERS
// ============================================================================

// Track current audio URL for cleanup (memory leak prevention)
let currentAudioObjectUrl = null;

/**
 * Phase 41: Clean up previous audio object URL to prevent memory leaks
 */
function cleanupAudioUrl() {
    if (currentAudioObjectUrl) {
        URL.revokeObjectURL(currentAudioObjectUrl);
        currentAudioObjectUrl = null;
    }
}

/**
 * Phase 41: Synthesize TTS and return audio blob without playing
 * Used for synchronized text-voice delivery
 * Includes timeout to prevent infinite loading
 * @param {string} text - Text to synthesize
 * @param {number} timeoutMs - Timeout in milliseconds (default 8000)
 * @returns {Promise<{blob: Blob, engine: string}|null>} Object with audio blob and engine name, or null on failure/timeout
 */
async function synthesizeTTSOnly(text, timeoutMs = 8000) {
    if (!text) return null;

    try {
        // Create abort controller for timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

        const response = await fetch('/voice/synthesize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            console.log('[Phase 41] TTS synthesis failed:', response.status);
            return null;
        }

        // Get engine from response header
        const engine = response.headers.get('X-TTS-Engine') || 'unknown';
        const blob = await response.blob();

        return { blob, engine };
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('[Phase 41] TTS synthesis timeout after', timeoutMs, 'ms');
        } else {
            console.log('[Phase 41] TTS synthesis error:', error);
        }
        return null;
    }
}

/**
 * Phase 41: Fetch audio blob from stored audio ID without playing
 * Used for synchronized text-voice delivery in voice input flow
 * Includes timeout to prevent infinite loading
 * @param {string} audioId - Audio ID from voice chat response
 * @param {number} timeoutMs - Timeout in milliseconds (default 5000)
 * @returns {Promise<Blob|null>} Audio blob or null on failure/timeout
 */
async function fetchAudioBlob(audioId, timeoutMs = 5000) {
    if (!audioId) return null;

    try {
        // Create abort controller for timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

        const response = await fetch(`/voice/audio/${audioId}`, {
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            console.log('[Phase 41] Audio fetch failed:', response.status);
            return null;
        }
        return await response.blob();
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('[Phase 41] Audio fetch timeout after', timeoutMs, 'ms');
        } else {
            console.log('[Phase 41] Audio fetch error:', error);
        }
        return null;
    }
}

/**
 * Phase 41: Play audio blob immediately (no fetch delay)
 * Used after text is displayed for synchronized playback
 * Includes memory cleanup for object URLs
 * @param {Blob} blob - Audio blob to play
 */
function playAudioBlob(blob) {
    if (!blob) {
        console.log('[Phase 41] playAudioBlob: no blob provided');
        return;
    }
    if (!ttsAudio) {
        console.log('[Phase 41] playAudioBlob: ttsAudio element not found');
        return;
    }

    // Interrupt any existing playback and cleanup old URL
    interruptTTS();
    cleanupAudioUrl();

    // Create new object URL and track it for cleanup
    currentAudioObjectUrl = URL.createObjectURL(blob);
    console.log('[Phase 41] Playing audio URL:', currentAudioObjectUrl);
    setVoiceState(VoiceState.RESPONDING);
    ttsAudio.src = currentAudioObjectUrl;

    // Play with proper error handling
    const playPromise = ttsAudio.play();
    if (playPromise !== undefined) {
        playPromise
            .then(() => {
                console.log('[Phase 41] Audio playback started successfully');
            })
            .catch(error => {
                console.log('[Phase 41] Audio playback error:', error.name, error.message);
                // Check for autoplay restriction
                if (error.name === 'NotAllowedError') {
                    console.log('[Phase 41] Autoplay blocked by browser policy');
                }
                cleanupAudioUrl();
                setVoiceState(VoiceState.IDLE);
            });
    }
}

/**
 * Stop TTS playback (legacy function, now calls interruptTTS)
 */
function stopSpeaking() {
    interruptTTS();
}

// ============================================================================
// TRANSCRIPTION PREVIEW HANDLERS
// ============================================================================

let pendingTranscription = '';

/**
 * Show transcription preview for editing
 */
function showTranscriptionPreview(text) {
    pendingTranscription = text;
    if (previewText) previewText.textContent = `"${text}"`;
    transcriptionPreview.style.display = 'flex';
}

/**
 * Handle preview edit - put text in input for editing
 */
function handlePreviewEdit() {
    userInput.value = pendingTranscription;
    transcriptionPreview.style.display = 'none';
    pendingTranscription = '';
    // Note: Auto-focus disabled to prevent virtual keyboard from obstructing view on RPi
    setVoiceState(VoiceState.IDLE);
}

/**
 * Handle preview send - send transcription directly
 */
async function handlePreviewSend() {
    transcriptionPreview.style.display = 'none';
    const message = pendingTranscription;
    pendingTranscription = '';

    if (message) {
        // Show user message
        addUserMessage(message);

        // Send to chat
        startThinkingAnimation();

        try {
            const data = await sendMessage(message);
            stopThinkingAnimation();
            addAssistantMessage(data);
            lastQueryId = data.timestamp;
        } catch (error) {
            stopThinkingAnimation();
            addErrorMessage('Sorry, I encountered an error processing your request.');
        }
    }

    setVoiceState(VoiceState.IDLE);
}

/**
 * Handle preview cancel - discard transcription
 */
function handlePreviewCancel() {
    transcriptionPreview.style.display = 'none';
    pendingTranscription = '';
    setVoiceState(VoiceState.IDLE);
}

// ============================================================================
// AUDIO VISUALIZER
// ============================================================================

/**
 * Reset silence detection state
 */
function resetSilenceDetection() {
    silenceDetectionState = {
        speechDetected: false,
        speechStartTime: null,
        silenceStartTime: null,
        lastRMS: 0,
    };
}

/**
 * Compute RMS (root mean square) audio level from time domain data
 */
function computeRMS(dataArray) {
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
        // Convert from 0-255 to -1 to 1 range
        const normalized = (dataArray[i] - 128) / 128;
        sum += normalized * normalized;
    }
    return Math.sqrt(sum / dataArray.length);
}

/**
 * Check for silence and auto-stop recording if speech has ended
 */
function checkSilenceDetection(rms) {
    const now = Date.now();
    const state = silenceDetectionState;
    state.lastRMS = rms;

    // Check if speech is detected
    if (rms >= SILENCE_DETECTION.SPEECH_THRESHOLD) {
        if (!state.speechDetected) {
            state.speechDetected = true;
            state.speechStartTime = now;
            console.log('[Silence Detection] Speech started');
            // Update status to show auto-stop is active
            if (voiceStatusText) {
                voiceStatusText.textContent = 'Listening... (auto-stops when done)';
            }
        }
        // Reset silence timer when speech is detected
        state.silenceStartTime = null;
    } else if (rms < SILENCE_DETECTION.SILENCE_THRESHOLD) {
        // Silence detected
        if (!state.silenceStartTime) {
            state.silenceStartTime = now;
        }
    } else {
        // Audio between thresholds - reset silence timer
        state.silenceStartTime = null;
    }

    // Check if we should auto-stop
    if (state.speechDetected && state.silenceStartTime) {
        const speechDuration = now - state.speechStartTime;
        const silenceDuration = now - state.silenceStartTime;

        // Only auto-stop if:
        // 1. User has spoken for minimum duration
        // 2. Silence has lasted long enough
        if (speechDuration >= SILENCE_DETECTION.MIN_SPEECH_DURATION_MS &&
            silenceDuration >= SILENCE_DETECTION.SILENCE_DURATION_MS) {
            console.log(`[Silence Detection] Auto-stopping: speech=${speechDuration}ms, silence=${silenceDuration}ms`);
            stopRecording();
            return true; // Stop the visualizer loop
        }
    }

    return false;
}

/**
 * Initialize audio visualizer with the microphone stream
 */
function initAudioVisualizer(stream) {
    try {
        // Reset silence detection state
        resetSilenceDetection();

        // Create audio context
        audioContext = new (window.AudioContext || window.webkitAudioContext)();

        // Create analyser node
        analyserNode = audioContext.createAnalyser();
        analyserNode.fftSize = 256;
        analyserNode.smoothingTimeConstant = 0.8;

        // Connect microphone to analyser
        const source = audioContext.createMediaStreamSource(stream);
        source.connect(analyserNode);

        // Show visualizer container
        if (audioVisualizerContainer) {
            audioVisualizerContainer.style.display = 'block';
        }

        // Start drawing
        drawVisualizer();

    } catch (error) {
        console.error('Error initializing audio visualizer:', error);
    }
}

/**
 * Draw the audio visualizer
 */
function drawVisualizer() {
    if (!analyserNode || !audioVisualizerCanvas) {
        return;
    }

    const canvas = audioVisualizerCanvas;
    const ctx = canvas.getContext('2d');

    // Set canvas size to match display size
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    const width = rect.width;
    const height = rect.height;

    // Get frequency data for visualization
    const bufferLength = analyserNode.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyserNode.getByteFrequencyData(dataArray);

    // Phase 35: Get time domain data for silence detection
    const timeDomainData = new Uint8Array(analyserNode.fftSize);
    analyserNode.getByteTimeDomainData(timeDomainData);
    const rms = computeRMS(timeDomainData);

    // Check for silence and auto-stop if speech has ended
    if (voiceState === VoiceState.LISTENING && checkSilenceDetection(rms)) {
        return; // Recording stopped, exit animation loop
    }

    // Clear canvas
    ctx.fillStyle = 'rgba(15, 15, 26, 0.3)';
    ctx.fillRect(0, 0, width, height);

    // Calculate bar properties
    const barCount = 64;
    const barWidth = (width / barCount) - 2;
    const barSpacing = 2;

    // Draw bars
    for (let i = 0; i < barCount; i++) {
        // Sample from frequency data
        const dataIndex = Math.floor(i * bufferLength / barCount);
        const value = dataArray[dataIndex];
        const barHeight = (value / 255) * height * 0.9;

        // Calculate x position (centered)
        const x = i * (barWidth + barSpacing);
        const y = height - barHeight;

        // Create gradient for bar
        const gradient = ctx.createLinearGradient(0, height, 0, y);
        gradient.addColorStop(0, '#4caf50');  // Green at bottom
        gradient.addColorStop(0.5, '#8bc34a'); // Light green
        gradient.addColorStop(0.8, '#ffeb3b'); // Yellow
        gradient.addColorStop(1, '#ff5722');   // Orange/red at top

        ctx.fillStyle = gradient;

        // Draw rounded bar
        const radius = Math.min(barWidth / 2, 4);
        ctx.beginPath();
        ctx.roundRect(x, y, barWidth, barHeight, [radius, radius, 0, 0]);
        ctx.fill();

        // Add glow effect for high values
        if (value > 200) {
            ctx.shadowColor = '#4caf50';
            ctx.shadowBlur = 10;
        } else {
            ctx.shadowBlur = 0;
        }
    }

    // Draw center line
    ctx.strokeStyle = 'rgba(76, 175, 80, 0.3)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();

    // Schedule next frame
    visualizerAnimationId = requestAnimationFrame(drawVisualizer);
}

/**
 * Draw waveform style visualizer (alternative)
 */
function drawWaveform() {
    if (!analyserNode || !audioVisualizerCanvas) {
        return;
    }

    const canvas = audioVisualizerCanvas;
    const ctx = canvas.getContext('2d');

    // Set canvas size
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    const width = rect.width;
    const height = rect.height;

    // Get time domain data (waveform)
    const bufferLength = analyserNode.fftSize;
    const dataArray = new Uint8Array(bufferLength);
    analyserNode.getByteTimeDomainData(dataArray);

    // Clear canvas
    ctx.fillStyle = '#0f0f1a';
    ctx.fillRect(0, 0, width, height);

    // Draw waveform
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#4caf50';
    ctx.beginPath();

    const sliceWidth = width / bufferLength;
    let x = 0;

    for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * height) / 2;

        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }

        x += sliceWidth;
    }

    ctx.lineTo(width, height / 2);
    ctx.stroke();

    // Add glow effect
    ctx.shadowColor = '#4caf50';
    ctx.shadowBlur = 5;

    // Schedule next frame
    visualizerAnimationId = requestAnimationFrame(drawWaveform);
}

/**
 * Stop audio visualizer
 */
function stopAudioVisualizer() {
    // Cancel animation
    if (visualizerAnimationId) {
        cancelAnimationFrame(visualizerAnimationId);
        visualizerAnimationId = null;
    }

    // Reset silence detection state
    resetSilenceDetection();

    // Close audio context
    if (audioContext && audioContext.state !== 'closed') {
        audioContext.close().catch(() => {});
        audioContext = null;
    }

    analyserNode = null;

    // Hide visualizer container
    if (audioVisualizerContainer) {
        audioVisualizerContainer.style.display = 'none';
    }
}

// =============================================================================
// DRAG-TO-SCROLL FOR MOUSE (DISABLED - interferes with text selection)
// =============================================================================
// This feature was disabled because it prevents users from selecting and
// copying text in the chat conversation area. Touch scrolling on mobile
// devices still works via native browser behavior and CSS touch-action.
//
// To re-enable, uncomment the initDragToScroll function below.
// =============================================================================

/*
(function initDragToScroll() {
    const scrollContainer = document.getElementById('chatContainer');
    if (!scrollContainer) return;

    let isDragging = false;
    let startY = 0;
    let scrollTop = 0;

    // Mouse down - start drag
    scrollContainer.addEventListener('mousedown', (e) => {
        // Don't initiate drag if clicking on interactive elements
        if (e.target.closest('button, a, input, textarea, select, .feedback-icon-btn')) {
            return;
        }

        isDragging = true;
        startY = e.pageY - scrollContainer.offsetTop;
        scrollTop = scrollContainer.scrollTop;
        scrollContainer.classList.add('dragging');

        // Prevent text selection during drag
        e.preventDefault();
    });

    // Mouse move - scroll while dragging
    scrollContainer.addEventListener('mousemove', (e) => {
        if (!isDragging) return;

        e.preventDefault();
        const y = e.pageY - scrollContainer.offsetTop;
        const walk = (y - startY) * 1.5; // Multiply for faster scroll speed
        scrollContainer.scrollTop = scrollTop - walk;
    });

    // Mouse up - stop drag
    scrollContainer.addEventListener('mouseup', () => {
        isDragging = false;
        scrollContainer.classList.remove('dragging');
    });

    // Mouse leave - stop drag if mouse leaves container
    scrollContainer.addEventListener('mouseleave', () => {
        if (isDragging) {
            isDragging = false;
            scrollContainer.classList.remove('dragging');
        }
    });

    // Prevent drag from interfering with clicks
    scrollContainer.addEventListener('click', (e) => {
        // If we were dragging, don't propagate click
        if (scrollContainer.classList.contains('was-dragging')) {
            e.stopPropagation();
            scrollContainer.classList.remove('was-dragging');
        }
    });
})();
*/

// ============================================================================
// DRAG/SWIPE SCROLLING FOR CONVERSATION PANEL
// ============================================================================
// Uses Pointer Events API for unified mouse, touch, and pen/trackpad support.
// Scoped to #chatContainer only — no other panels are affected.
// Distinguishes taps from drags: only activates scrolling after a 5px movement
// threshold, so clicks on FAQ items and other elements still work normally.

(function initDragScroll() {
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer) return;

    const DRAG_THRESHOLD = 5; // px — movement needed to start dragging

    let isPointerDown = false;
    let isDragging = false;
    let startY = 0;
    let startScrollTop = 0;
    let pointerId = null;

    chatContainer.addEventListener('pointerdown', (e) => {
        // Skip interactive elements (buttons, links, inputs)
        if (e.target.closest('button, a, input, textarea, select, .feedback-icon-btn')) {
            return;
        }
        isPointerDown = true;
        isDragging = false;
        startY = e.clientY;
        startScrollTop = chatContainer.scrollTop;
        pointerId = e.pointerId;
    });

    chatContainer.addEventListener('pointermove', (e) => {
        if (!isPointerDown || e.pointerId !== pointerId) return;

        const deltaY = startY - e.clientY;

        // Activate drag mode only after exceeding the threshold
        if (!isDragging) {
            if (Math.abs(deltaY) < DRAG_THRESHOLD) return;
            isDragging = true;
            chatContainer.setPointerCapture(e.pointerId);
            chatContainer.style.cursor = 'grabbing';
        }

        chatContainer.scrollTop = startScrollTop + deltaY;
    });

    chatContainer.addEventListener('pointerup', (e) => {
        if (e.pointerId !== pointerId) return;
        if (isDragging) {
            chatContainer.releasePointerCapture(e.pointerId);
            chatContainer.style.cursor = '';
        }
        isPointerDown = false;
        isDragging = false;
        pointerId = null;
    });

    chatContainer.addEventListener('pointercancel', (e) => {
        if (e.pointerId !== pointerId) return;
        if (isDragging) {
            chatContainer.releasePointerCapture(e.pointerId);
            chatContainer.style.cursor = '';
        }
        isPointerDown = false;
        isDragging = false;
        pointerId = null;
    });
})();

// ============================================================================
// FAQ ACCORDION SECTION
// ============================================================================

const FAQ_DEFAULT_VISIBLE = 3;
let faqData = [];
let faqExpanded = false; // Show More state
let faqConfig = {};
let faqInactivityTimer = null;
const FAQ_INACTIVITY_TIMEOUT = 600000; // 10 minutes

/**
 * Initialize the FAQ section
 */
async function initFAQSection() {
    console.log('[FAQ] Initializing FAQ section...');

    const faqSection = document.getElementById('faqSection');
    const faqToggleBtn = document.getElementById('faqToggleBtn');

    if (!faqSection) {
        console.warn('[FAQ] FAQ section not found in DOM');
        return;
    }

    // Load FAQs from API
    await loadFAQs();

    // Set up Show More/Less toggle
    if (faqToggleBtn) {
        faqToggleBtn.addEventListener('click', toggleFAQList);
    }

    console.log('[FAQ] FAQ section initialized');
}

/**
 * Load FAQs from API
 */
async function loadFAQs() {
    try {
        const response = await fetch('/api/faqs');
        if (!response.ok) throw new Error('Failed to load FAQs');

        const data = await response.json();
        faqData = data.faqs || [];
        faqConfig = data.config || { default_visible: FAQ_DEFAULT_VISIBLE };

        renderFAQs();
    } catch (error) {
        console.error('[FAQ] Error loading FAQs:', error);
        // Hide FAQ section if loading fails
        const faqSection = document.getElementById('faqSection');
        if (faqSection) faqSection.style.display = 'none';
    }
}

/**
 * Render FAQ items to the DOM
 * Uses container-based approach for Show More/Less animation
 */
function renderFAQs() {
    const faqSection = document.getElementById('faqSection');
    const faqList = document.getElementById('faqList');
    const faqToggleBtn = document.getElementById('faqToggleBtn');

    if (!faqSection || !faqList) return;

    // Hide section if no FAQs
    if (faqData.length === 0) {
        faqSection.style.display = 'none';
        return;
    }

    // Show section
    faqSection.style.display = 'block';

    const defaultVisible = faqConfig.default_visible || FAQ_DEFAULT_VISIBLE;
    const visibleFAQs = faqData.slice(0, defaultVisible);
    const overflowFAQs = faqData.slice(defaultVisible);

    // Helper to build FAQ item HTML
    const buildFAQItem = (faq, index) => `
        <div class="faq-item" data-faq-id="${faq.id}" data-faq-index="${index}">
            <div class="faq-question" onclick="toggleFAQItem('${faq.id}')">
                <span class="faq-question-text">${escapeHtml(faq.question)}</span>
                <svg class="faq-chevron" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/>
                </svg>
            </div>
            <div class="faq-answer">
                <div class="faq-answer-content">
                    <div class="faq-answer-inner">${formatAnswerText(faq.answer)}</div>
                </div>
            </div>
        </div>
    `;

    // Build visible items
    let html = visibleFAQs.map((faq, index) => buildFAQItem(faq, index)).join('');

    // Add overflow container if there are more items
    if (overflowFAQs.length > 0) {
        const collapsedClass = faqExpanded ? '' : 'collapsed';
        html += `
            <div class="faq-overflow-container ${collapsedClass}" id="faqOverflowContainer">
                <div class="faq-overflow-content">
                    ${overflowFAQs.map((faq, index) => buildFAQItem(faq, defaultVisible + index)).join('')}
                </div>
            </div>
        `;
    }

    faqList.innerHTML = html;

    // Show/hide toggle button
    updateFAQToggleButton();
}

/**
 * Update the Show More/Less button state
 */
function updateFAQToggleButton() {
    const faqToggleBtn = document.getElementById('faqToggleBtn');
    if (!faqToggleBtn) return;

    const defaultVisible = faqConfig.default_visible || FAQ_DEFAULT_VISIBLE;

    if (faqData.length > defaultVisible) {
        faqToggleBtn.style.display = 'flex';
        faqToggleBtn.querySelector('.faq-toggle-text').textContent = faqExpanded ? 'Show Less' : 'Show More';
        faqToggleBtn.classList.toggle('expanded', faqExpanded);
    } else {
        faqToggleBtn.style.display = 'none';
    }
}

/**
 * Toggle individual FAQ item (accordion behavior)
 * @param {string} faqId - The FAQ ID to toggle
 */
function toggleFAQItem(faqId) {
    const faqList = document.getElementById('faqList');
    if (!faqList) return;

    const items = faqList.querySelectorAll('.faq-item');

    items.forEach(item => {
        if (item.dataset.faqId === faqId) {
            // Toggle this item
            item.classList.toggle('expanded');
        } else {
            // Close other items (accordion behavior)
            item.classList.remove('expanded');
        }
    });

    // Reset FAQ inactivity timer on any FAQ item interaction
    resetFAQInactivityTimer();
}

/**
 * Toggle Show More / Show Less with animation
 */
function toggleFAQList() {
    const overflowContainer = document.getElementById('faqOverflowContainer');
    if (!overflowContainer) return;

    faqExpanded = !faqExpanded;

    if (faqExpanded) {
        // Expand: remove collapsed class
        overflowContainer.classList.remove('collapsed');
    } else {
        // Collapse: first close any expanded answers inside overflow
        const expandedItems = overflowContainer.querySelectorAll('.faq-item.expanded');
        expandedItems.forEach(item => item.classList.remove('expanded'));
        // Then collapse container
        overflowContainer.classList.add('collapsed');
    }

    // Update button text
    updateFAQToggleButton();

    // Reset FAQ inactivity timer on Show More/Less interaction
    resetFAQInactivityTimer();
}

/**
 * Check if any FAQ content is currently expanded
 * @returns {boolean} True if any FAQ item is expanded or Show More is active
 */
function isFAQExpanded() {
    if (faqExpanded) return true;
    const faqList = document.getElementById('faqList');
    if (!faqList) return false;
    return faqList.querySelector('.faq-item.expanded') !== null;
}

/**
 * Collapse all FAQ items and the Show More overflow container.
 * Called by the inactivity timer after 10 minutes of no FAQ interaction.
 */
function collapseAllFAQs() {
    const faqList = document.getElementById('faqList');
    if (faqList) {
        faqList.querySelectorAll('.faq-item.expanded')
            .forEach(item => item.classList.remove('expanded'));
    }
    const overflowContainer = document.getElementById('faqOverflowContainer');
    if (overflowContainer) {
        overflowContainer.classList.add('collapsed');
    }
    faqExpanded = false;
    updateFAQToggleButton();
    stopFAQInactivityTimer();
}

/**
 * Reset the FAQ inactivity timer.
 * Starts or restarts the 10-minute countdown on every FAQ interaction.
 * If nothing is expanded after the interaction, stops the timer instead.
 */
function resetFAQInactivityTimer() {
    stopFAQInactivityTimer();
    if (isFAQExpanded()) {
        faqInactivityTimer = setTimeout(collapseAllFAQs, FAQ_INACTIVITY_TIMEOUT);
    }
}

/**
 * Stop the FAQ inactivity timer.
 */
function stopFAQInactivityTimer() {
    if (faqInactivityTimer) {
        clearTimeout(faqInactivityTimer);
        faqInactivityTimer = null;
    }
}

/**
 * Escape HTML to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Expose toggle function globally for onclick handlers
window.toggleFAQItem = toggleFAQItem;

// ============================================================================
// VIRTUAL KEYBOARD (Web-based, for fullscreen kiosk mode)
// ============================================================================

(function initVirtualKeyboard() {
    const vkb = document.getElementById('virtualKeyboard');
    if (!vkb) return;

    const lettersLayer = document.getElementById('vkbLetters');
    const symbolsLayer = document.getElementById('vkbSymbols');
    const layerToggleBtn = vkb.querySelector('.vkb-layer-toggle');
    const kioskAdminPassword = document.getElementById('kioskAdminPassword');
    const kioskWifiPassword = document.getElementById('kioskWifiPassword');

    // Track all VKB-enabled inputs so blur handler knows when to hide
    const vkbInputs = new Set();

    let activeInput = null; // Currently targeted input field
    let shiftActive = false;
    let capsLockActive = false; // Double-click shift = persistent caps
    let lastShiftTime = 0;     // For double-click detection
    const DOUBLE_CLICK_MS = 400;
    let symbolsActive = false;

    /**
     * Check if we're in fullscreen mode.
     * Detects both the DOM Fullscreen API (user tapped fullscreen button)
     * and Chromium --start-fullscreen / --kiosk (window fills screen without API).
     */
    function isFullscreen() {
        return detectFullscreen();
    }

    /**
     * Show the virtual keyboard for a specific input field.
     * @param {HTMLInputElement} inputEl - The input to target
     * @param {object} [opts] - Options: { centered: boolean }
     */
    function showVKB(inputEl, opts) {
        if (!isFullscreen()) return;
        activeInput = inputEl || userInput;
        vkb.classList.add('vkb-visible');
        vkb.classList.toggle('vkb-centered', !!(opts && opts.centered));
        document.body.classList.add('vkb-active');
    }

    /**
     * Hide the virtual keyboard.
     */
    function hideVKB() {
        vkb.classList.remove('vkb-visible');
        vkb.classList.remove('vkb-centered');
        document.body.classList.remove('vkb-active');
        activeInput = null;
    }

    /**
     * Toggle between letters and symbols layers.
     */
    function toggleLayer() {
        symbolsActive = !symbolsActive;
        if (lettersLayer) lettersLayer.style.display = symbolsActive ? 'none' : '';
        if (symbolsLayer) symbolsLayer.style.display = symbolsActive ? '' : 'none';
        if (layerToggleBtn) {
            layerToggleBtn.textContent = symbolsActive ? 'ABC' : '#+=';
            layerToggleBtn.classList.toggle('active', symbolsActive);
        }
        // Reset shift/caps lock when switching to symbols
        if (symbolsActive && (shiftActive || capsLockActive)) {
            shiftActive = false;
            capsLockActive = false;
            updateShiftDisplay();
        }
    }

    /**
     * Update key labels for shift/caps lock state (letters layer only).
     */
    function updateShiftDisplay() {
        if (!lettersLayer) return;
        const isUpper = shiftActive || capsLockActive;
        lettersLayer.querySelectorAll('.vkb-key[data-key]').forEach(key => {
            const ch = key.getAttribute('data-key');
            if (ch.length === 1 && ch.match(/[a-z]/i)) {
                key.textContent = isUpper ? ch.toUpperCase() : ch.toLowerCase();
            }
        });
        const shiftBtn = vkb.querySelector('.vkb-shift');
        if (shiftBtn) {
            shiftBtn.classList.toggle('active', isUpper);
            // Visual distinction: underline for caps lock mode
            shiftBtn.style.textDecoration = capsLockActive ? 'underline' : '';
        }
    }

    /**
     * Insert a character into the active input field at cursor position.
     */
    function insertChar(ch) {
        const target = activeInput;
        if (!target) return;
        const start = target.selectionStart;
        const end = target.selectionEnd;
        const value = target.value;
        // Shift/caps lock only applies to letters, not symbols/punctuation
        const isLetter = ch.length === 1 && ch.match(/[a-z]/i);
        const isUpper = isLetter && (shiftActive || capsLockActive);
        const charToInsert = isUpper ? ch.toUpperCase() : ch;

        target.value = value.substring(0, start) + charToInsert + value.substring(end);
        const newPos = start + 1;
        target.setSelectionRange(newPos, newPos);
        target.scrollLeft = target.scrollWidth;

        // Auto-disable one-shot shift (but NOT caps lock)
        if (shiftActive && !capsLockActive && isLetter) {
            shiftActive = false;
            updateShiftDisplay();
        }

        target.focus();
    }

    /**
     * Handle special action keys.
     */
    function handleAction(action) {
        switch (action) {
            case 'shift': {
                const now = Date.now();
                if (capsLockActive) {
                    // Already in caps lock — disable everything
                    capsLockActive = false;
                    shiftActive = false;
                } else if (shiftActive && (now - lastShiftTime) < DOUBLE_CLICK_MS) {
                    // Double-click: activate caps lock
                    capsLockActive = true;
                    shiftActive = false;
                } else {
                    // Single click: one-shot shift
                    shiftActive = !shiftActive;
                }
                lastShiftTime = now;
                updateShiftDisplay();
                break;
            }

            case 'symbols':
                toggleLayer();
                break;

            case 'backspace': {
                const target = activeInput;
                if (!target) return;
                const bsStart = target.selectionStart;
                const bsEnd = target.selectionEnd;
                const bsValue = target.value;
                let newCursorPos = bsStart;

                if (bsStart !== bsEnd) {
                    target.value = bsValue.substring(0, bsStart) + bsValue.substring(bsEnd);
                    newCursorPos = bsStart;
                } else if (bsStart > 0) {
                    target.value = bsValue.substring(0, bsStart - 1) + bsValue.substring(bsStart);
                    newCursorPos = bsStart - 1;
                }
                target.setSelectionRange(newCursorPos, newCursorPos);
                target.focus();
                break;
            }

            case 'space':
                insertChar(' ');
                break;

            case 'send':
                // Only submit the chat form if the active input is the chat input
                if (activeInput === userInput && chatForm) {
                    hideVKB();
                    chatForm.dispatchEvent(new Event('submit', { cancelable: true }));
                } else {
                    // For other inputs (e.g., admin password), just hide the keyboard
                    hideVKB();
                }
                break;
        }
    }

    // --- Event Listeners ---

    // Key press handling (use touchstart for responsiveness on touchscreens)
    vkb.addEventListener('touchstart', function(e) {
        const key = e.target.closest('.vkb-key');
        if (!key) return;
        e.preventDefault(); // Prevent focus stealing from input

        const action = key.getAttribute('data-action');
        if (action) {
            handleAction(action);
        } else {
            const ch = key.getAttribute('data-key');
            if (ch) insertChar(ch);
        }
    }, { passive: false });

    // Mouse fallback (for development/testing on desktop)
    vkb.addEventListener('mousedown', function(e) {
        const key = e.target.closest('.vkb-key');
        if (!key) return;
        e.preventDefault(); // Prevent focus stealing from input

        const action = key.getAttribute('data-action');
        if (action) {
            handleAction(action);
        } else {
            const ch = key.getAttribute('data-key');
            if (ch) insertChar(ch);
        }
    });

    /**
     * Attach VKB focus/blur listeners to an input element.
     * @param {HTMLInputElement} inputEl - The input element
     * @param {object} [opts] - Options passed to showVKB (e.g., { centered: true })
     */
    function attachVKBInput(inputEl, opts) {
        if (!inputEl) return;
        vkbInputs.add(inputEl);
        inputEl.addEventListener('focus', function() {
            showVKB(inputEl, opts);
        });
        inputEl.addEventListener('blur', function() {
            setTimeout(function() {
                // Only hide if focus didn't go to another VKB-enabled input
                if (!vkbInputs.has(document.activeElement)) {
                    hideVKB();
                }
            }, 200);
        });
    }

    // Attach VKB to chat input (left-aligned, default)
    attachVKBInput(userInput);
    // Attach VKB to admin password input (center-aligned)
    attachVKBInput(kioskAdminPassword, { centered: true });
    // Attach VKB to WiFi password input (center-aligned)
    attachVKBInput(kioskWifiPassword, { centered: true });

    // Hide keyboard when exiting fullscreen
    document.addEventListener('fullscreenchange', function() {
        if (!isFullscreen()) hideVKB();
    });
    document.addEventListener('webkitfullscreenchange', function() {
        if (!isFullscreen()) hideVKB();
    });

    // If keyboard somehow steals focus, redirect it back to active input
    vkb.addEventListener('focusin', function() {
        if (activeInput) activeInput.focus();
    });

    console.log('[VKB] Virtual keyboard initialized');
})();
