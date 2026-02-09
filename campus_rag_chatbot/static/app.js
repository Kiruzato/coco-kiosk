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

// Helper to update sessionId both in memory and sessionStorage
function updateSessionId(newId) {
    sessionId = newId;
    if (newId) {
        sessionStorage.setItem('chatSessionId', newId);
    }
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
const kioskContainer = document.querySelector('.kiosk-container');

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Set up event listeners
    chatForm.addEventListener('submit', handleSubmit);
    resetBtn.addEventListener('click', handleReset);

    // Set up fullscreen toggle
    if (fullscreenBtn) {
        fullscreenBtn.addEventListener('click', toggleFullscreen);
    }

    // Listen for fullscreen changes to update button icon
    document.addEventListener('fullscreenchange', updateFullscreenButton);
    document.addEventListener('webkitfullscreenchange', updateFullscreenButton);

    // Note: Auto-focus disabled to prevent virtual keyboard from obstructing view on RPi
});

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

    // Confidence badge
    const confidenceClass = `confidence-${data.confidence_level.toLowerCase()}`;
    html += `
        <div class="confidence-badge ${confidenceClass}">
            Confidence: ${data.confidence_level}
        </div>
        <div class="confidence-score">
            Score: ${data.confidence_score}/100
        </div>
    `;

    // Mode transparency badge (Phase 6)
    if (data.mode === 'campus') {
        html += `<div class="mode-badge mode-campus">📚 Based on campus documents</div>`;
    } else if (data.mode === 'general') {
        html += `<div class="mode-badge mode-general">🤖 Based on general AI knowledge</div>`;
    } else if (data.mode === 'clarification') {
        html += `<div class="mode-badge mode-clarification">❓ Needs clarification</div>`;
    }

    // Sources
    if (data.sources && data.sources.length > 0) {
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

    // Feedback buttons (only for non-rejected answers)
    if (!data.rejected) {
        const feedbackId = `feedback-${Date.now()}`;
        html += `
            <div class="feedback-container" id="${feedbackId}">
                <div class="feedback-question">Was this answer helpful?</div>
                <div class="feedback-buttons">
                    <button class="feedback-btn helpful" onclick="submitFeedback('${feedbackId}', true)">
                        &#10003; Yes, helpful
                    </button>
                    <button class="feedback-btn not-helpful" onclick="submitFeedback('${feedbackId}', false)">
                        &#10007; Not helpful
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

/**
 * Submit feedback for a response
 */
async function submitFeedback(feedbackId, isHelpful) {
    try {
        const response = await fetch('/feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionId,
                query_id: lastQueryId || 'unknown',
                is_helpful: isHelpful
            })
        });

        if (response.ok) {
            // Disable feedback buttons and show thank you
            const feedbackContainer = document.getElementById(feedbackId);
            if (feedbackContainer) {
                feedbackContainer.innerHTML = `
                    <div class="feedback-thanks">
                        ✓ Thank you for your feedback!
                    </div>
                `;
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

    if (isWaiting) {
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

    // Show loading indicator
    loadingIndicator.style.display = 'flex';

    try {
        // Send to API
        const data = await sendMessage(message);

        // Store query ID for feedback
        lastQueryId = data.timestamp;

        // Phase 41: Synchronized text-voice delivery
        // If TTS enabled, synthesize audio BEFORE showing text
        // Note: TTS plays for ALL answers including graceful refusals (rejected=true)
        console.log('[Phase 41] TTS check:', { ttsEnabled, hasAnswer: !!data.answer });
        if (ttsEnabled && data.answer) {
            // Update loading text to indicate preparing response
            if (loadingText) loadingText.textContent = 'Preparing response...';

            // Synthesize TTS (keep loading indicator visible)
            console.log('[Phase 41] Synthesizing TTS for typed input...');
            const audioBlob = await synthesizeTTSOnly(data.answer);
            console.log('[Phase 41] TTS synthesis result:', audioBlob ? `Blob size: ${audioBlob.size}` : 'null');

            // Add TTS engine info to debug_info for text input (mirrors voice input behavior)
            if (audioBlob && data.debug_info) {
                data.debug_info.tts_engine = 'edge-tts';
                data.debug_info.tts_fallback_used = false;
            }

            // Hide loading indicator
            loadingIndicator.style.display = 'none';

            // Show text and play audio together
            addAssistantMessage(data);
            if (audioBlob) {
                console.log('[Phase 41] Playing audio blob...');
                playAudioBlob(audioBlob);
            } else {
                console.log('[Phase 41] No audio blob to play');
            }
        } else {
            // No TTS - show text immediately
            console.log('[Phase 41] Skipping TTS:', { ttsEnabled, hasAnswer: !!data.answer });
            loadingIndicator.style.display = 'none';
            addAssistantMessage(data);
        }

    } catch (error) {
        // Hide loading indicator
        loadingIndicator.style.display = 'none';

        // Show error message
        addErrorMessage('Sorry, I encountered an error processing your request. Please try again.');
    } finally {
        // Re-enable input
        isWaiting = false;
        userInput.disabled = false;
        sendBtn.disabled = false;
        // Note: Auto-focus disabled to prevent virtual keyboard from obstructing view on RPi
    }
}

/**
 * Handle reset button click
 */
async function handleReset(event) {
    event.preventDefault();

    if (confirm('Start a new conversation? This will clear the current chat history.')) {
        await resetConversation();
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
// FULLSCREEN TOGGLE
// ============================================================================

/**
 * Toggle fullscreen mode for the kiosk container
 */
function toggleFullscreen() {
    if (!document.fullscreenElement && !document.webkitFullscreenElement) {
        // Enter fullscreen
        const elem = kioskContainer || document.documentElement;
        if (elem.requestFullscreen) {
            elem.requestFullscreen();
        } else if (elem.webkitRequestFullscreen) {
            elem.webkitRequestFullscreen();
        }
    } else {
        // Exit fullscreen
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        }
    }
}

/**
 * Update fullscreen button icon based on current state
 */
function updateFullscreenButton() {
    const isFullscreen = document.fullscreenElement || document.webkitFullscreenElement;
    const icon = fullscreenBtn?.querySelector('.fullscreen-icon');

    if (icon) {
        // &#x26F6; = square with corners (expand), &#x2716; = X mark (exit)
        // Using different symbols: ⛶ for expand, ⮌ for minimize
        icon.innerHTML = isFullscreen ? '&#x2716;' : '&#x26F6;';
    }

    // Update container class for fullscreen-specific styling
    if (kioskContainer) {
        kioskContainer.classList.toggle('fullscreen-mode', isFullscreen);
    }
    document.body.classList.toggle('fullscreen-active', isFullscreen);
}

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
        : (ttsEnabled ? 'edge-tts' : 'Disabled');

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
            voiceBtn.disabled = !voiceEnabled;
            voiceStatus.style.display = 'none';
            // Phase 40: voiceIndicator removed - TTS now silent
            loadingIndicator.style.display = 'none';
            // Re-enable typed input when voice returns to idle (unless waiting for chat response)
            if (!isWaiting) {
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
            voiceStatus.style.display = 'flex';
            voiceStatus.classList.add('processing');
            if (voiceStatusText) voiceStatusText.textContent = message || 'Processing...';
            loadingIndicator.style.display = 'flex';
            if (loadingText) loadingText.textContent = 'Processing your voice...';
            break;

        case VoiceState.RESPONDING:
            // Phase 40: Silent TTS - no visual indicator, audio plays in background
            // Keep UI in normal state so user can read response while listening
            voiceBtn.disabled = !voiceEnabled;
            voiceStatus.style.display = 'none';
            loadingIndicator.style.display = 'none';
            // Phase 41 fix: Re-enable inputs during RESPONDING so user can interact
            // while TTS plays (this is the "silent TTS" UX - user can type new query)
            userInput.disabled = false;
            sendBtn.disabled = false;
            break;

        case VoiceState.ERROR:
            voiceBtn.classList.add('error');
            voiceBtn.disabled = false;
            voiceStatus.style.display = 'flex';
            voiceStatus.classList.add('error');
            if (voiceStatusText) voiceStatusText.textContent = message || 'Error occurred';
            // Re-enable typed input on error so user can fall back to typing
            if (!isWaiting) {
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

        // Send to voice chat endpoint
        const response = await fetch('/voice/chat', {
            method: 'POST',
            body: formData
        });

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

        // Build response object for addAssistantMessage
        const chatResponse = data.answer ? {
            answer: data.answer,
            mode: data.mode || 'campus',
            confidence_level: data.confidence || 'Medium',
            confidence_score: Math.round(data.transcription_confidence * 100) || 50,
            sources: data.sources || [],
            rejected: data.rejected || false,
            structured_answer: data.structured_answer || null,
            debug_info: data.debug_info || null
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
            lastQueryId = Date.now();

            if (audioBlob) {
                playAudioBlob(audioBlob);
            } else {
                setVoiceState(VoiceState.IDLE);
            }
        } else {
            // No TTS - show text immediately
            if (chatResponse) {
                addAssistantMessage(chatResponse);
                lastQueryId = Date.now();
            }
            setVoiceState(VoiceState.IDLE);
        }

    } catch (error) {
        console.error('Voice processing error:', error);
        setVoiceState(VoiceState.ERROR, error.message || 'Voice processing failed');

        // Show error in chat
        addErrorMessage('Voice processing failed. Please try again or type your question.');
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
 * @returns {Promise<Blob|null>} Audio blob or null on failure/timeout
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

        return await response.blob();
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
        loadingIndicator.style.display = 'flex';
        if (loadingText) loadingText.textContent = 'Searching campus information...';

        try {
            const data = await sendMessage(message);
            loadingIndicator.style.display = 'none';
            addAssistantMessage(data);
            lastQueryId = data.timestamp;
        } catch (error) {
            loadingIndicator.style.display = 'none';
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
