/**
 * Campus Information Kiosk - Frontend JavaScript
 * ================================================
 * Handles chat interactions, API calls, and feedback submission
 */

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

let sessionId = null;
let lastQueryId = null;
let isWaiting = false;

// ============================================================================
// DOM ELEMENTS
// ============================================================================

const chatContainer = document.getElementById('chatContainer');
const chatForm = document.getElementById('chatForm');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const resetBtn = document.getElementById('resetBtn');
const loadingIndicator = document.getElementById('loadingIndicator');

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Set up event listeners
    chatForm.addEventListener('submit', handleSubmit);
    resetBtn.addEventListener('click', handleReset);

    // Focus input
    userInput.focus();
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
 * Add an assistant message to the chat
 */
function addAssistantMessage(data) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant-message';

    // Build message content
    let html = `<div class="message-content">`;

    // Answer text
    html += `<p class="large-text">${escapeHtml(data.answer)}</p>`;

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
                ⚠ This answer was generated with low confidence. Please try rephrasing your question or ask about a different topic.
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
                        👍 Yes, helpful
                    </button>
                    <button class="feedback-btn not-helpful" onclick="submitFeedback('${feedbackId}', false)">
                        👎 Not helpful
                    </button>
                </div>
            </div>
        `;
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
                ❌ ${escapeHtml(message)}
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

        // Store session ID
        if (data.session_id) {
            sessionId = data.session_id;
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
        lastQueryId = null;

        // Clear chat (keep welcome message)
        const messages = chatContainer.querySelectorAll('.message');
        messages.forEach((msg, index) => {
            if (index > 0) {  // Keep first message (welcome)
                msg.remove();
            }
        });

        // Focus input
        userInput.focus();
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

        // Hide loading indicator
        loadingIndicator.style.display = 'none';

        // Show assistant response
        addAssistantMessage(data);

        // Store query ID for feedback
        lastQueryId = data.timestamp; // Use timestamp as query ID for now

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
        userInput.focus();
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
 * Make submitFeedback available globally for onclick handlers
 */
window.submitFeedback = submitFeedback;
