/**
 * Admin Document Management System - Phase 7
 * Frontend JavaScript for managing document uploads, listing, and deletion
 */

// ==============================================================================
// STATE MANAGEMENT
// ==============================================================================

let isUploading = false;
let isDeleting = false;
let isSavingEntity = false;
let editingEntityId = null;  // Track which entity is being edited

// ==============================================================================
// SESSION MANAGEMENT
// ==============================================================================

/**
 * Check if user is authenticated, redirect to login if not
 */
async function checkAuth() {
    try {
        const response = await fetch('/admin/documents');
        if (response.status === 401) {
            window.location.href = '/admin/login';
            return false;
        }
        return true;
    } catch (error) {
        window.location.href = '/admin/login';
        return false;
    }
}

/**
 * Logout and redirect to login page
 */
async function logout() {
    try {
        await fetch('/admin/logout', { method: 'POST' });
    } catch (error) {
        // Ignore errors, redirect anyway
    }
    window.location.href = '/admin/login';
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
 * Generic API call with session authentication
 */
async function apiCall(endpoint, options = {}) {
    const response = await fetch(endpoint, {
        ...options,
        headers: {
            ...options.headers
        }
    });

    // Redirect to login if not authenticated
    if (response.status === 401) {
        window.location.href = '/admin/login';
        throw new Error('Not authenticated');
    }

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
        tableBody.innerHTML = '<tr><td colspan="5" class="error-state">Failed to load documents. Please try again.</td></tr>';
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
// ENTITY MANAGEMENT (Phase 10)
// ==============================================================================

/**
 * Load and display all directory entities
 */
async function loadEntities() {
    const loadingIndicator = document.getElementById('entitiesLoadingIndicator');
    const tableBody = document.getElementById('entitiesBody');
    const statsDiv = document.getElementById('entitiesStats');

    loadingIndicator.classList.remove('hidden');

    try {
        const data = await apiCall('/admin/entities');

        tableBody.innerHTML = '';

        if (data.entities.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="6" class="empty-state">No entities found.</td></tr>';
            statsDiv.textContent = '';
        } else {
            data.entities.forEach(entity => {
                const row = createEntityRow(entity);
                tableBody.appendChild(row);
            });
            statsDiv.textContent = `Total: ${data.total} entities (${data.active} active)`;
        }

    } catch (error) {
        showNotification(`Failed to load entities: ${error.message}`, 'error');
        tableBody.innerHTML = '<tr><td colspan="6" class="error-state">Failed to load entities. Please try again.</td></tr>';
        statsDiv.textContent = '';
    } finally {
        loadingIndicator.classList.add('hidden');
    }
}

/**
 * Create table row for an entity
 */
function createEntityRow(entity) {
    const row = document.createElement('tr');
    const isActive = entity.status === 'active';

    row.className = isActive ? '' : 'inactive-row';
    row.innerHTML = `
        <td class="entity-id">${escapeHtml(entity.entity_id)}</td>
        <td>${escapeHtml(entity.canonical_name)}</td>
        <td>${escapeHtml(entity.building)}</td>
        <td>${escapeHtml(entity.floor)}</td>
        <td>
            <span class="status-badge ${isActive ? 'status-active' : 'status-inactive'}">
                ${isActive ? 'Active' : 'Inactive'}
            </span>
        </td>
        <td class="action-buttons">
            <button class="btn-secondary btn-small" onclick="editEntity('${entity.entity_id}')">
                Edit
            </button>
            <button class="btn-${isActive ? 'warning' : 'success'} btn-small" onclick="toggleEntityStatus('${entity.entity_id}', ${isActive})">
                ${isActive ? 'Deactivate' : 'Activate'}
            </button>
        </td>
    `;

    return row;
}

/**
 * Show entity modal for adding or editing
 */
function showEntityModal(entity = null) {
    const modal = document.getElementById('entityModal');
    const title = document.getElementById('entityModalTitle');
    const entityIdInput = document.getElementById('entityId');
    const statusGroup = document.getElementById('statusGroup');

    // Reset form
    document.getElementById('entityForm').reset();

    if (entity) {
        // Edit mode
        editingEntityId = entity.entity_id;
        title.textContent = 'Edit Entity';
        entityIdInput.value = entity.entity_id;
        entityIdInput.disabled = true;  // Can't change entity ID
        document.getElementById('canonicalName').value = entity.canonical_name || '';
        document.getElementById('aliases').value = (entity.aliases || []).join(', ');
        document.getElementById('building').value = entity.building || '';
        document.getElementById('floor').value = entity.floor || '';
        document.getElementById('room').value = entity.room || '';
        document.getElementById('campus').value = entity.campus || 'Main Campus';
        document.getElementById('department').value = entity.department || '';
        document.getElementById('landmarks').value = entity.landmarks || '';
        document.getElementById('description').value = entity.description || '';
        document.getElementById('entityStatus').value = entity.status || 'active';
        statusGroup.style.display = 'block';
    } else {
        // Add mode
        editingEntityId = null;
        title.textContent = 'Add Entity';
        entityIdInput.disabled = false;
        document.getElementById('campus').value = 'Main Campus';  // Default value
        statusGroup.style.display = 'none';
    }

    modal.classList.remove('hidden');
}

/**
 * Hide entity modal
 */
function hideEntityModal() {
    const modal = document.getElementById('entityModal');
    modal.classList.add('hidden');
    editingEntityId = null;
}

/**
 * Save entity (create or update)
 */
async function saveEntity(e) {
    e.preventDefault();

    if (isSavingEntity) return;

    const entityId = document.getElementById('entityId').value.trim();
    const canonicalName = document.getElementById('canonicalName').value.trim();
    const aliasesInput = document.getElementById('aliases').value.trim();
    const building = document.getElementById('building').value.trim();
    const floor = document.getElementById('floor').value.trim();
    const room = document.getElementById('room').value.trim();
    const campus = document.getElementById('campus').value.trim();
    const department = document.getElementById('department').value.trim();
    const landmarks = document.getElementById('landmarks').value.trim();
    const description = document.getElementById('description').value.trim();
    const status = document.getElementById('entityStatus').value;

    // Parse aliases
    const aliases = aliasesInput
        ? aliasesInput.split(',').map(a => a.trim()).filter(a => a)
        : [];

    // Validation
    if (!entityId || !canonicalName || !building || !floor || !campus) {
        showNotification('Please fill in all required fields', 'error');
        return;
    }

    isSavingEntity = true;
    const saveBtn = document.getElementById('saveEntityBtn');
    const originalText = saveBtn.textContent;
    saveBtn.textContent = 'Saving...';
    saveBtn.disabled = true;

    try {
        let data;

        if (editingEntityId) {
            // Update existing entity
            const updateData = {
                canonical_name: canonicalName,
                aliases: aliases,
                building: building,
                floor: floor,
                room: room || null,
                campus: campus,
                department: department || null,
                landmarks: landmarks || null,
                description: description || null,
                status: status
            };

            data = await apiCall(`/admin/entities/${editingEntityId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updateData)
            });

            showNotification(`Entity "${entityId}" updated successfully`, 'success');
        } else {
            // Create new entity
            const createData = {
                entity_id: entityId,
                canonical_name: canonicalName,
                aliases: aliases,
                building: building,
                floor: floor,
                room: room || null,
                campus: campus,
                department: department || null,
                landmarks: landmarks || null,
                description: description || null
            };

            data = await apiCall('/admin/entities', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(createData)
            });

            showNotification(`Entity "${entityId}" created successfully`, 'success');
        }

        hideEntityModal();
        await loadEntities();

    } catch (error) {
        showNotification(`Failed to save entity: ${error.message}`, 'error');
    } finally {
        isSavingEntity = false;
        saveBtn.textContent = originalText;
        saveBtn.disabled = false;
    }
}

/**
 * Edit an existing entity
 */
async function editEntity(entityId) {
    try {
        const data = await apiCall(`/admin/entities/${entityId}`);
        showEntityModal(data.entity);
    } catch (error) {
        showNotification(`Failed to load entity: ${error.message}`, 'error');
    }
}

/**
 * Toggle entity status (active/inactive)
 */
async function toggleEntityStatus(entityId, currentlyActive) {
    const newStatus = currentlyActive ? 'inactive' : 'active';
    const action = currentlyActive ? 'deactivate' : 'activate';

    // Confirmation for deactivation
    if (currentlyActive) {
        const confirmed = confirm(
            `Are you sure you want to deactivate "${entityId}"?\n\nDeactivated entities will not appear in search results and the chatbot will not provide directions to this location.`
        );
        if (!confirmed) return;
    }

    try {
        await apiCall(`/admin/entities/${entityId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });

        showNotification(`Entity "${entityId}" ${action}d successfully`, 'success');
        await loadEntities();

    } catch (error) {
        showNotification(`Failed to ${action} entity: ${error.message}`, 'error');
    }
}

// Make entity functions available globally for onclick handlers
window.editEntity = editEntity;
window.toggleEntityStatus = toggleEntityStatus;

// ==============================================================================
// CSV IMPORT/EXPORT (Phase 10 Extension)
// ==============================================================================

/**
 * Export entities to CSV file
 */
async function exportEntities() {
    try {
        showNotification('Exporting entities...', 'info');

        const response = await fetch('/admin/entities/export');

        if (response.status === 401) {
            window.location.href = '/admin/login';
            return;
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Export failed');
        }

        // Get filename from Content-Disposition header or use default
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'directory_entities.csv';
        if (contentDisposition) {
            const match = contentDisposition.match(/filename=(.+)/);
            if (match) filename = match[1];
        }

        // Download the file
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showNotification('Entities exported successfully', 'success');

    } catch (error) {
        showNotification(`Export failed: ${error.message}`, 'error');
    }
}

/**
 * Import entities from CSV file
 */
async function importEntities(file) {
    if (!file) {
        showNotification('No file selected', 'error');
        return;
    }

    const importBtn = document.getElementById('importEntitiesTrigger');
    const originalText = importBtn.textContent;
    importBtn.textContent = 'Importing...';
    importBtn.disabled = true;

    try {
        showNotification('Importing entities...', 'info');

        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/admin/entities/import', {
            method: 'POST',
            body: formData
        });

        if (response.status === 401) {
            window.location.href = '/admin/login';
            return;
        }

        const data = await response.json();

        if (data.status === 'error') {
            // Show validation errors
            let errorMsg = data.message;
            if (data.stats && data.stats.errors && data.stats.errors.length > 0) {
                errorMsg += '\n' + data.stats.errors.slice(0, 5).join('\n');
                if (data.stats.errors.length > 5) {
                    errorMsg += `\n... and ${data.stats.errors.length - 5} more errors`;
                }
            }
            showNotification(errorMsg, 'error');
            return;
        }

        showNotification(data.message, 'success');

        // Reload entities to show changes
        await loadEntities();

    } catch (error) {
        showNotification(`Import failed: ${error.message}`, 'error');
    } finally {
        importBtn.textContent = originalText;
        importBtn.disabled = false;
        // Reset file input
        document.getElementById('importEntitiesInput').value = '';
    }
}

// ==============================================================================
// EVENT LISTENERS
// ==============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Logout Button
    document.getElementById('logoutBtn').addEventListener('click', logout);

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

    // ==============================================================================
    // ENTITY MANAGEMENT EVENT LISTENERS (Phase 10)
    // ==============================================================================

    // Add Entity Button
    document.getElementById('addEntityBtn').addEventListener('click', () => showEntityModal());

    // Refresh Entities Button
    document.getElementById('refreshEntitiesBtn').addEventListener('click', loadEntities);

    // Export Entities Button
    document.getElementById('exportEntitiesBtn').addEventListener('click', exportEntities);

    // Import Entities Button (trigger file input)
    document.getElementById('importEntitiesTrigger').addEventListener('click', () => {
        document.getElementById('importEntitiesInput').click();
    });

    // Import Entities File Input
    document.getElementById('importEntitiesInput').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            importEntities(file);
        }
    });

    // Entity Modal Close Button
    document.getElementById('closeEntityModal').addEventListener('click', hideEntityModal);

    // Entity Modal Cancel Button
    document.getElementById('cancelEntityBtn').addEventListener('click', hideEntityModal);

    // Entity Form Submit
    document.getElementById('entityForm').addEventListener('submit', saveEntity);

    // Close modal when clicking outside
    document.getElementById('entityModal').addEventListener('click', (e) => {
        if (e.target.id === 'entityModal') {
            hideEntityModal();
        }
    });

    // ==============================================================================
    // INITIALIZATION
    // ==============================================================================

    // Check authentication and load data
    checkAuth().then(isAuthenticated => {
        if (isAuthenticated) {
            loadDocuments();
            loadEntities();
        }
    });
});

// Make deleteDocument available globally for onclick handlers
window.deleteDocument = deleteDocument;
