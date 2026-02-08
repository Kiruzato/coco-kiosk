/**
 * Kiosk UI Sandbox - Mock Data & Logic
 * ====================================
 */

// Hardcoded mock responses for testing design
const MOCK_DATA = {
    "library": {
        answer: "The Library is located in the Main Building, 2nd Floor. Hours are Mon-Fri 7 AM - 7 PM.",
        structured_answer: {
            full_answer: "The Library is located in the Main Building, 2nd Floor. Hours are Mon-Fri 7 AM - 7 PM.",
            direct_answer: "Main Building, 2nd Floor. Mon-Fri 7 AM - 7 PM.",
        },
        confidence_level: "HIGH",
        confidence_score: 95,
        mode: "campus",
        sources: [
            { document_name: "Student_Handbook_2024.pdf", section: "Campus Facilities" },
            { document_name: "Library_Services.pdf", section: "Hours" }
        ]
    },
    "cafeteria": {
        answer: "The Cafeteria is in the Student Center on the Ground Floor. Breakfast is served 7-9 AM, Lunch 11-1 PM.",
        structured_answer: {
            full_answer: "The Cafeteria is in the Student Center on the Ground Floor.\n\nService Hours:\n- Breakfast: 7:00 AM - 9:00 AM\n- Lunch: 11:00 AM - 1:00 PM\n- Snacks: 2:00 PM - 5:00 PM",
            direct_answer: "Student Center, Ground Floor.",
        },
        confidence_level: "MEDIUM",
        confidence_score: 82,
        mode: "campus",
        sources: [
            { document_name: "Campus_Map.jpg", section: "Dining" }
        ]
    },
    "default": {
        answer: "I'm not sure about that. This is a design sandbox demonstrating the layout.",
        structured_answer: {
            full_answer: "I'm not sure about that. This is a design sandbox demonstrating the layout. Try asking about 'library' or 'cafeteria' to see varied responses.",
            direct_answer: "Unknown topic.",
        },
        confidence_level: "LOW",
        confidence_score: 45,
        mode: "general",
        sources: []
    }
};

document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chatForm');
    const userInput = document.getElementById('userInput');
    const resetBtn = document.getElementById('resetBtn');

    // Auto-focus input
    userInput.focus();

    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = userInput.value.trim();
        if (!text) return;

        // Add user message
        addMessage(text, 'user');
        userInput.value = '';
        userInput.disabled = true;

        // Show loading state
        const loading = document.getElementById('loadingIndicator');
        loading.style.display = 'flex';

        // Simulate network delay
        setTimeout(() => {
            loading.style.display = 'none';
            userInput.disabled = false;
            userInput.focus();

            // Simple keyword matching for mock data
            let key = 'default';
            const lowerText = text.toLowerCase();
            if (lowerText.includes('library') || lowerText.includes('book')) key = 'library';
            if (lowerText.includes('cafe') || lowerText.includes('food')) key = 'cafeteria';

            addAssistantResponse(MOCK_DATA[key]);
        }, 800);
    });

    resetBtn.addEventListener('click', () => {
        const container = document.getElementById('chatContainer');
        // Keep welcome message (first child)
        while (container.children.length > 1) {
            container.removeChild(container.lastChild);
        }
        userInput.value = '';
        userInput.focus();
    });
});

function addMessage(text, type) {
    const container = document.getElementById('chatContainer');
    const div = document.createElement('div');
    div.className = `message ${type}-message`;
    div.innerHTML = `<div class="message-content">${escapeHtml(text)}</div>`;
    container.appendChild(div);
    scrollToBottom();
}

function addAssistantResponse(data) {
    const container = document.getElementById('chatContainer');
    const div = document.createElement('div');
    div.className = 'message assistant-message';

    let html = `<div class="message-content">`;
    html += `<div class="answer-text">${formatText(data.structured_answer.full_answer)}</div>`;

    // Badges
    html += `<div class="meta-row">`;
    html += `<span class="badge confidence-${data.confidence_level.toLowerCase()}">Confidence: ${data.confidence_level}</span>`;
    html += `<span class="badge mode-${data.mode}">${data.mode.toUpperCase()} Mode</span>`;
    html += `</div>`;

    // Sources
    if (data.sources.length > 0) {
        html += `<div class="sources-list"><strong>Sources:</strong><ul>`;
        data.sources.forEach(s => {
            html += `<li>${escapeHtml(s.document_name)} (${escapeHtml(s.section)})</li>`;
        });
        html += `</ul></div>`;
    }

    html += `</div>`;

    div.innerHTML = html;
    container.appendChild(div);
    scrollToBottom();
}

function scrollToBottom() {
    const container = document.getElementById('chatContainer');
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatText(text) {
    // Simple mock markdown-ish formatting for line breaks
    return escapeHtml(text).replace(/\n/g, '<br>');
}
