/**
 * Admin Document Management System - Phase 7
 * Frontend JavaScript for managing document uploads, listing, and deletion
 */

// ==============================================================================
// STATE MANAGEMENT
// ==============================================================================

let isUploading = false;
let isDeleting = false;

// ==============================================================================
// API KEY MANAGEMENT
// ==============================================================================

/**
 * Save API key to sessionStorage
 */
function saveApiKey() {
    const apiKeyInput = document.getElementById('apiKeyInput');
    const apiKey = apiKeyInput.value.trim();

    if (!apiKey) {
        showNotification('Please enter an API key', 'error');
        return;
    }

    sessionStorage.setItem('admin_api_key', apiKey);
    updateApiKeyStatus(true);
    showNotification('API key saved for this session', 'success');

    // Load documents after saving API key
    loadDocuments();
}

/**
 * Get API key from sessionStorage
 */
function getApiKey() {
    return sessionStorage.getItem('admin_api_key');
}

/**
 * Update API key status indicator
 */
function updateApiKeyStatus(isSet) {
    const statusDiv = document.getElementById('apiKeyStatus');

    if (isSet) {
        statusDiv.textContent = '✓ API key is saved';
        statusDiv.className = 'api-key-status success';
    } else {
        statusDiv.textContent = '⚠ API key not set';
        statusDiv.className = 'api-key-status warning';
    }
}

/**
 * Toggle API key visibility
 */
function toggleApiKeyVisibility() {
    const apiKeyInput = document.getElementById('apiKeyInput');
    const toggleIcon = document.getElementById('toggleIcon');

    if (apiKeyInput.type === 'password') {
        apiKeyInput.type = 'text';
        toggleIcon.textContent = '🙈';
    } else {
        apiKeyInput.type = 'password';
        toggleIcon.textContent = '👁️';
    }
}

// ==============================================================================
// NOTIFICATION SYSTEM
// ==============================================================================

/**
 * Show notification message
 */
function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type}`;

    // Auto-hide after 5 seconds
    setTimeout(() => {
        notification.className = 'notification hidden';
    }, 5000);
}

// ==============================================================================
// API CALLS
// ==============================================================================

/**
 * Generic API call with authentication
 */
async function apiCall(endpoint, options = {}) {
    const apiKey = getApiKey();

    if (!apiKey) {
        showNotification('Please save your API key first', 'error');
        throw new Error('No API key set');
    }

    const response = await fetch(endpoint, {
        ...options,
        headers: {
            'X-API-Key': apiKey,
            ...options.headers
        }
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.detail || errorData.message || `Request failed with status ${response.status}`;
        throw new Error(errorMessage);
    }

    return response.json();
}

/**
 * Upload document to server
 */
async function uploadDocument(file) {
    if (isUploading) return;

    isUploading = true;
    const uploadBtn = document.getElementById('uploadBtn');
    const originalText = uploadBtn.textContent;
    uploadBtn.textContent = 'Uploading...';
    uploadBtn.disabled = true;

    try {
        const formData = new FormData();
        formData.append('file', file);

        const data = await apiCall('/admin/upload', {
            method: 'POST',
            body: formData
        });

        showNotification(`Document "${data.document.document_name}" uploaded successfully`, 'success');

        // Reset file input
        const fileInput = document.getElementById('fileInput');
        fileInput.value = '';
        document.getElementById('fileName').textContent = 'Choose a file or drag here';
        uploadBtn.disabled = true;

        // Reload documents table
        await loadDocuments();

    } catch (error) {
        showNotification(`Upload failed: ${error.message}`, 'error');
    } finally {
        isUploading = false;
        uploadBtn.textContent = originalText;
        uploadBtn.disabled = !document.getElementById('fileInput').files.length;
    }
}

/**
 * Load and display all documents
 */
async function loadDocuments() {
    const apiKey = getApiKey();
    if (!apiKey) {
        return; // Silently return if no API key
    }

    const loadingIndicator = document.getElementById('loadingIndicator');
    const tableBody = document.getElementById('documentsBody');

    loadingIndicator.classList.remove('hidden');

    try {
        const data = await apiCall('/admin/documents');

        tableBody.innerHTML = '';

        if (data.documents.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="empty-state">No documents loaded. Upload a document to get started.</td></tr>';
        } else {
            data.documents.forEach(doc => {
                const row = createDocumentRow(doc);
                tableBody.appendChild(row);
            });
        }

    } catch (error) {
        showNotification(`Failed to load documents: ${error.message}`, 'error');
        tableBody.innerHTML = '<tr><td colspan="5" class="error-state">Failed to load documents. Please check your API key and try again.</td></tr>';
    } finally {
        loadingIndicator.classList.add('hidden');
    }
}

/**
 * Create table row for a document
 */
function createDocumentRow(doc) {
    const row = document.createElement('tr');

    // Format date
    const date = new Date(doc.ingestion_timestamp);
    const formattedDate = date.toLocaleString();

    row.innerHTML = `
        <td class="filename">${escapeHtml(doc.document_name)}</td>
        <td>${escapeHtml(doc.file_type)}</td>
        <td>${doc.num_chunks}</td>
        <td>${formattedDate}</td>
        <td>
            <button class="btn-danger" onclick="deleteDocument('${doc.document_id}', '${escapeHtml(doc.document_name)}')">
                Delete
            </button>
        </td>
    `;

    return row;
}

/**
 * Delete a document
 */
async function deleteDocument(documentId, documentName) {
    if (isDeleting) return;

    // Confirmation dialog
    const confirmed = confirm(
        `Are you sure you want to delete "${documentName}"?\n\nThis will:\n- Remove the document from the vector store\n- Delete the file from disk\n- Rebuild the vector store\n\nThis action cannot be undone.`
    );

    if (!confirmed) return;

    isDeleting = true;
    showNotification(`Deleting "${documentName}"...`, 'info');

    try {
        const data = await apiCall(`/admin/documents/${documentId}`, {
            method: 'DELETE'
        });

        showNotification(`Document "${data.document_name}" deleted successfully`, 'success');

        // Reload documents table
        await loadDocuments();

    } catch (error) {
        showNotification(`Delete failed: ${error.message}`, 'error');
    } finally {
        isDeleting = false;
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==============================================================================
// EVENT LISTENERS
// ==============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // API Key Management
    document.getElementById('saveApiKey').addEventListener('click', saveApiKey);
    document.getElementById('toggleApiKey').addEventListener('click', toggleApiKeyVisibility);

    // API key input - Enter key to save
    document.getElementById('apiKeyInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            saveApiKey();
        }
    });

    // File Input
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            document.getElementById('fileName').textContent = file.name;
            uploadBtn.disabled = false;
        } else {
            document.getElementById('fileName').textContent = 'Choose a file or drag here';
            uploadBtn.disabled = true;
        }
    });

    // Upload Form
    document.getElementById('uploadForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const file = fileInput.files[0];
        if (file) {
            uploadDocument(file);
        }
    });

    // Refresh Button
    document.getElementById('refreshBtn').addEventListener('click', loadDocuments);

    // Check if API key is already saved
    const savedApiKey = getApiKey();
    if (savedApiKey) {
        updateApiKeyStatus(true);
        document.getElementById('apiKeyInput').value = savedApiKey;
        // Auto-load documents if API key exists
        loadDocuments();
    } else {
        updateApiKeyStatus(false);
    }
});

// Make deleteDocument available globally for onclick handlers
window.deleteDocument = deleteDocument;
