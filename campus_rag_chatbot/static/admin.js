/**
 * Admin Document Management System - Phase 36
 * Frontend JavaScript for managing documents, entities, analytics, and voice config
 */

// ==============================================================================
// STATE MANAGEMENT
// ==============================================================================

let isUploading = false;
let isDeleting = false;
let isSavingEntity = false;
let editingEntityId = null;  // Track which entity is being edited
let currentSection = 'analytics';  // Current active section
let voiceConfigChanged = false;  // Track unsaved voice config changes

// Phase 42: Test Harness state
let testQuestions = [];
let testResults = [];
let isRunningTests = false;
let testEventSource = null;

// ==============================================================================
// SECTION NAVIGATION (Phase 36)
// ==============================================================================

/**
 * Switch to a different admin section
 */
function switchSection(sectionId) {
    // Validate section exists
    const section = document.getElementById(`section-${sectionId}`);
    if (!section) {
        console.warn(`Section not found: ${sectionId}`);
        return;
    }

    // Hide all sections
    document.querySelectorAll('.admin-section').forEach(s => {
        s.classList.remove('active');
    });

    // Show target section
    section.classList.add('active');

    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.section === sectionId) {
            item.classList.add('active');
        }
    });

    // Update URL hash (without triggering hashchange)
    history.replaceState(null, '', `#${sectionId}`);

    // Save to sessionStorage
    sessionStorage.setItem('adminSection', sectionId);

    // Update current section
    currentSection = sectionId;

    // Load section data if needed (lazy loading)
    loadSectionData(sectionId);
}

/**
 * Load data for a section if not already loaded
 */
function loadSectionData(sectionId) {
    switch (sectionId) {
        case 'analytics':
            loadAnalytics();
            break;
        case 'documents':
            loadDocuments();
            break;
        case 'entities':
            loadEntities();
            break;
        case 'voice':
            loadVoiceConfig();
            break;
        case 'developer':
            loadDebugSettings();
            break;
        case 'test-harness':
            loadTestHarness();
            break;
        // 'upload' section doesn't need data loading
    }
}

/**
 * Initialize section navigation
 */
function initSectionNavigation() {
    // Add click handlers to nav items
    document.querySelectorAll('.nav-item[data-section]').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const sectionId = item.dataset.section;
            switchSection(sectionId);
        });
    });

    // Determine initial section from URL hash or sessionStorage
    let initialSection = 'analytics';  // Default

    // Check URL hash first
    if (window.location.hash) {
        const hashSection = window.location.hash.substring(1);
        if (document.getElementById(`section-${hashSection}`)) {
            initialSection = hashSection;
        }
    }
    // Then check sessionStorage
    else {
        const savedSection = sessionStorage.getItem('adminSection');
        if (savedSection && document.getElementById(`section-${savedSection}`)) {
            initialSection = savedSection;
        }
    }

    // Switch to initial section
    switchSection(initialSection);

    // Handle browser back/forward
    window.addEventListener('hashchange', () => {
        const hashSection = window.location.hash.substring(1);
        if (hashSection && document.getElementById(`section-${hashSection}`)) {
            switchSection(hashSection);
        }
    });
}

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
        document.getElementById('fileName').textContent = 'Choose a file';
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

/**
 * Format answer text with markdown-like formatting (same as chatbot)
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

        // Phase 55: Also load index stats
        await loadIndexStats();

    } catch (error) {
        showNotification(`Failed to load entities: ${error.message}`, 'error');
        tableBody.innerHTML = '<tr><td colspan="6" class="error-state">Failed to load entities. Please try again.</td></tr>';
        statsDiv.textContent = '';
    } finally {
        loadingIndicator.classList.add('hidden');
    }
}

/**
 * Phase 55: Load and display CQE index statistics
 */
async function loadIndexStats() {
    try {
        const data = await apiCall('/admin/index/stats');

        if (data.stats) {
            const stats = data.stats;
            const roomsEl = document.getElementById('indexStatRooms');
            const outdoorEl = document.getElementById('indexStatOutdoor');
            const buildingsEl = document.getElementById('indexStatBuildings');
            const campusesEl = document.getElementById('indexStatCampuses');
            const aliasesEl = document.getElementById('indexStatAliases');

            if (roomsEl) roomsEl.textContent = stats.rooms || 0;
            if (outdoorEl) outdoorEl.textContent = stats.outdoor_locations || 0;
            if (buildingsEl) buildingsEl.textContent = stats.buildings || 0;
            if (campusesEl) campusesEl.textContent = stats.campuses || 0;
            if (aliasesEl) aliasesEl.textContent = stats.total_aliases || 0;
        }
    } catch (error) {
        console.error('Failed to load index stats:', error);
    }
}

/**
 * Phase 55: Rebuild CQE index manually
 */
async function rebuildIndex() {
    const btn = document.getElementById('rebuildIndexBtn');
    const originalText = btn.textContent;

    btn.textContent = 'Rebuilding...';
    btn.disabled = true;

    try {
        const data = await apiCall('/admin/index/rebuild', {
            method: 'POST'
        });

        showNotification('Index rebuilt successfully', 'success');
        await loadIndexStats();

    } catch (error) {
        showNotification(`Failed to rebuild index: ${error.message}`, 'error');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
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
    const form = document.getElementById('entityForm');

    // Reset form
    form.reset();

    // Phase 55: Reset entity type to room
    const roomRadio = document.querySelector('input[name="entityType"][value="room"]');
    const outdoorRadio = document.querySelector('input[name="entityType"][value="outdoor"]');
    if (roomRadio) roomRadio.checked = true;
    toggleEntityType();  // Update visibility

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

        // Phase 55: Handle tags
        const tagsInput = document.getElementById('tags');
        if (tagsInput) {
            tagsInput.value = (entity.tags || []).join(', ');
        }

        // Phase 55: Detect outdoor location
        if (entity.building === '_OUTDOOR' || entity.floor === '_OUTDOOR') {
            if (outdoorRadio) outdoorRadio.checked = true;
            toggleEntityType();
        }
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
 * Phase 55: Toggle entity type (show/hide building/floor for outdoor locations)
 */
function toggleEntityType() {
    const entityType = document.querySelector('input[name="entityType"]:checked')?.value || 'room';
    const buildingFloorRow = document.getElementById('buildingFloorRow');
    const buildingInput = document.getElementById('building');
    const floorInput = document.getElementById('floor');
    const form = document.getElementById('entityForm');

    if (entityType === 'outdoor') {
        // Hide building/floor row for outdoor locations
        if (buildingFloorRow) buildingFloorRow.style.display = 'none';
        if (buildingInput) buildingInput.required = false;
        if (floorInput) floorInput.required = false;
        if (form) form.classList.add('outdoor-mode');
    } else {
        // Show building/floor row for regular rooms
        if (buildingFloorRow) buildingFloorRow.style.display = 'flex';
        if (buildingInput) buildingInput.required = true;
        if (floorInput) floorInput.required = true;
        if (form) form.classList.remove('outdoor-mode');
    }
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
    const campus = document.getElementById('campus').value.trim();
    const department = document.getElementById('department').value.trim();
    const landmarks = document.getElementById('landmarks').value.trim();
    const description = document.getElementById('description').value.trim();
    const status = document.getElementById('entityStatus').value;

    // Phase 55: Get entity type and tags
    const entityType = document.querySelector('input[name="entityType"]:checked')?.value || 'room';
    const tagsInput = document.getElementById('tags')?.value.trim() || '';

    // Phase 55: Handle building and floor based on entity type
    let building, floor, room;
    if (entityType === 'outdoor') {
        building = '_OUTDOOR';
        floor = '_OUTDOOR';
        room = '';
    } else {
        building = document.getElementById('building').value.trim();
        floor = document.getElementById('floor').value.trim();
        room = document.getElementById('room').value.trim();
    }

    // Parse aliases
    const aliases = aliasesInput
        ? aliasesInput.split(',').map(a => a.trim()).filter(a => a)
        : [];

    // Phase 55: Parse tags (normalize to lowercase)
    const tags = tagsInput
        ? tagsInput.split(',').map(t => t.trim().toLowerCase()).filter(t => t)
        : [];

    // Validation
    const isOutdoor = entityType === 'outdoor';
    if (!entityId || !canonicalName || !campus) {
        showNotification('Please fill in all required fields', 'error');
        return;
    }
    if (!isOutdoor && (!building || !floor)) {
        showNotification('Building and Floor are required for room entities', 'error');
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
// ANALYTICS FUNCTIONS - Phase 16
// ==============================================================================

/**
 * Load and display analytics data
 */
async function loadAnalytics() {
    const loadingIndicator = document.getElementById('analyticsLoadingIndicator');
    loadingIndicator.classList.remove('hidden');

    try {
        const data = await apiCall('/admin/analytics');
        displayAnalytics(data);
    } catch (error) {
        showNotification(`Failed to load analytics: ${error.message}`, 'error');
    } finally {
        loadingIndicator.classList.add('hidden');
    }
}

/**
 * Display analytics data in the UI
 */
function displayAnalytics(data) {
    // Summary stats
    document.getElementById('stat-total-queries').textContent =
        data.summary.total_queries.toLocaleString();
    document.getElementById('stat-clarification-rate').textContent =
        data.summary.clarification_rate + '%';
    document.getElementById('stat-refusal-rate').textContent =
        data.summary.refusal_rate + '%';
    document.getElementById('stat-clarification-success').textContent =
        data.summary.clarification_success_rate + '%';

    // Query type breakdown
    const queryTypeDiv = document.getElementById('query-type-breakdown');
    queryTypeDiv.innerHTML = Object.entries(data.by_query_type)
        .map(([type, count]) => `
            <div class="breakdown-item">
                <span class="breakdown-label">${type}</span>
                <span class="breakdown-value">${count}</span>
            </div>
        `).join('');

    // Confidence breakdown
    const confidenceDiv = document.getElementById('confidence-breakdown');
    confidenceDiv.innerHTML = Object.entries(data.by_confidence)
        .map(([level, count]) => `
            <div class="breakdown-item">
                <span class="breakdown-label">${level}</span>
                <span class="breakdown-value">${count}</span>
            </div>
        `).join('');

    // Refusal reasons
    const refusalDiv = document.getElementById('refusal-reasons-breakdown');
    const refusalReasons = data.refusal_reasons || {};
    if (Object.keys(refusalReasons).length === 0) {
        refusalDiv.innerHTML = '<div class="breakdown-item"><span class="breakdown-label">No refusals</span></div>';
    } else {
        refusalDiv.innerHTML = Object.entries(refusalReasons)
            .map(([reason, count]) => `
                <div class="breakdown-item">
                    <span class="breakdown-label">${reason.replace(/_/g, ' ')}</span>
                    <span class="breakdown-value">${count}</span>
                </div>
            `).join('');
    }
}

// ==============================================================================
// VOICE CONFIGURATION (Phase 36/37)
// ==============================================================================

let selectedSTTProvider = null;
let selectedTTSProvider = null;
// Phase 37: Track fallback selections and provider data
let selectedSTTFallback = null;
let selectedTTSFallback = null;
let sttProvidersData = [];
let ttsProvidersData = [];

/**
 * Load voice configuration from server
 */
async function loadVoiceConfig() {
    const loadingIndicator = document.getElementById('voiceLoadingIndicator');
    const sttProviders = document.getElementById('sttProviders');
    const ttsProviders = document.getElementById('ttsProviders');
    const saveBtn = document.getElementById('saveVoiceConfigBtn');
    const statusSpan = document.getElementById('voiceConfigStatus');

    loadingIndicator.classList.remove('hidden');
    statusSpan.textContent = '';

    try {
        const data = await apiCall('/admin/voice/providers');

        // Phase 37: Store provider data for fallback population
        sttProvidersData = data.stt_providers || [];
        ttsProvidersData = data.tts_providers || [];

        // Render STT providers
        sttProviders.innerHTML = renderProviderList(data.stt_providers, 'stt');

        // Render TTS providers
        ttsProviders.innerHTML = renderProviderList(data.tts_providers, 'tts');

        // Set current selections
        selectedSTTProvider = data.current_config?.stt_provider || null;
        selectedTTSProvider = data.current_config?.tts_provider || null;

        // Phase 37: Set fallback selections
        selectedSTTFallback = data.current_config?.stt_fallback_provider || null;
        selectedTTSFallback = data.current_config?.tts_fallback_provider || null;

        // Update selected state in UI
        updateProviderSelection();

        // Phase 37: Populate and set fallback dropdowns
        populateFallbackOptions('stt', sttProvidersData, selectedSTTProvider, selectedSTTFallback);
        populateFallbackOptions('tts', ttsProvidersData, selectedTTSProvider, selectedTTSFallback);

        // Add click handlers (Phase 37: only for selectable providers)
        document.querySelectorAll('.provider-item').forEach(item => {
            item.addEventListener('click', () => handleProviderClick(item));
        });

        // Phase 37: Add fallback change listeners
        const sttFallbackSelect = document.getElementById('sttFallbackSelect');
        const ttsFallbackSelect = document.getElementById('ttsFallbackSelect');

        if (sttFallbackSelect) {
            sttFallbackSelect.addEventListener('change', (e) => {
                selectedSTTFallback = e.target.value || null;
                markVoiceConfigChanged();
            });
        }

        if (ttsFallbackSelect) {
            ttsFallbackSelect.addEventListener('change', (e) => {
                selectedTTSFallback = e.target.value || null;
                markVoiceConfigChanged();
            });
        }

        // Reset change tracking
        voiceConfigChanged = false;
        saveBtn.disabled = true;

        // Phase 38: Load usage and credentials status
        loadSTTUsage();
        loadCredentialsStatus();

    } catch (error) {
        console.error('Failed to load voice config:', error);
        sttProviders.innerHTML = '<div class="provider-loading">Voice configuration unavailable</div>';
        ttsProviders.innerHTML = '<div class="provider-loading">Voice configuration unavailable</div>';
    } finally {
        loadingIndicator.classList.add('hidden');
    }
}

/**
 * Phase 37: Populate fallback dropdown options
 */
function populateFallbackOptions(type, providers, primaryId, currentFallbackId) {
    const selectId = type === 'stt' ? 'sttFallbackSelect' : 'ttsFallbackSelect';
    const select = document.getElementById(selectId);
    if (!select) return;

    // Clear existing options except first (Auto-select)
    while (select.options.length > 1) {
        select.remove(1);
    }

    // Add eligible fallback providers (can_be_fallback=true, available, not the primary)
    providers
        .filter(p => p.can_be_fallback && p.is_available && p.id !== primaryId)
        .forEach(p => {
            const option = document.createElement('option');
            option.value = p.id;
            option.textContent = `${p.name} (${p.pricing_tier})`;
            if (p.id === currentFallbackId) {
                option.selected = true;
            }
            select.appendChild(option);
        });
}

/**
 * Phase 37: Mark voice config as changed
 */
function markVoiceConfigChanged() {
    voiceConfigChanged = true;
    document.getElementById('saveVoiceConfigBtn').disabled = false;
    document.getElementById('voiceConfigStatus').textContent = 'Unsaved changes';
    document.getElementById('voiceConfigStatus').className = 'config-status';
}

/**
 * Render provider list HTML
 * Phase 37: Added pricing badges, non-selectable provider handling, status labels
 */
function renderProviderList(providers, type) {
    if (!providers || providers.length === 0) {
        return '<div class="provider-loading">No providers available</div>';
    }

    return providers.map(provider => {
        // Phase 37: Determine if provider is truly selectable
        const isSelectable = provider.is_selectable && provider.is_available;

        // Build CSS classes
        const itemClasses = [
            'provider-item',
            provider.is_active ? 'selected' : '',
            !provider.is_available ? 'unavailable' : '',
            !provider.is_selectable ? 'not-selectable' : ''
        ].filter(Boolean).join(' ');

        // Phase 37: Pricing badge
        const pricingBadge = `<span class="pricing-badge ${provider.pricing_tier}">${provider.pricing_tier}</span>`;

        // Phase 37: Status display - show status_label for non-selectable, Online/Offline for others
        let statusHtml;
        if (!provider.is_selectable && provider.status_label) {
            statusHtml = `<span class="status-label">${escapeHtml(provider.status_label)}</span>`;
        } else {
            statusHtml = `
                <div class="provider-status ${provider.is_available ? 'online' : 'offline'}">
                    <span class="status-dot ${provider.is_available ? 'online' : 'offline'}"></span>
                    ${provider.is_available ? 'Online' : 'Offline'}
                </div>
            `;
        }

        // Phase 37: Only show radio button for selectable providers
        const radioHtml = isSelectable ? `
            <input type="radio"
                   name="${type}-provider"
                   value="${provider.id}"
                   class="provider-radio"
                   ${provider.is_active ? 'checked' : ''}>
        ` : '';

        return `
            <div class="${itemClasses}"
                 data-provider-id="${provider.id}"
                 data-provider-type="${type}"
                 data-selectable="${isSelectable}">
                ${radioHtml}
                <div class="provider-info">
                    <div class="provider-name">${escapeHtml(provider.name)}${pricingBadge}</div>
                    <div class="provider-type">${provider.is_local ? 'Local' : 'Cloud'}</div>
                </div>
                ${statusHtml}
            </div>
        `;
    }).join('');
}

/**
 * Handle provider selection click
 * Phase 37: Check selectability before allowing selection
 */
function handleProviderClick(item) {
    const providerId = item.dataset.providerId;
    const providerType = item.dataset.providerType;
    const isSelectable = item.dataset.selectable === 'true';

    // Phase 37: Block selection of non-selectable providers
    if (!isSelectable) {
        showNotification('This provider is not available for selection', 'info');
        return;
    }

    // Update radio button
    const radio = item.querySelector('.provider-radio');
    if (radio && !radio.disabled) {
        radio.checked = true;
    }

    // Update selection state
    if (providerType === 'stt') {
        selectedSTTProvider = providerId;
        // Phase 37: Update fallback options when primary changes
        populateFallbackOptions('stt', sttProvidersData, providerId, selectedSTTFallback);
    } else if (providerType === 'tts') {
        selectedTTSProvider = providerId;
        // Phase 37: Update fallback options when primary changes
        populateFallbackOptions('tts', ttsProvidersData, providerId, selectedTTSFallback);
    }

    // Update UI
    updateProviderSelection();

    // Mark as changed
    markVoiceConfigChanged();
}

/**
 * Update provider selection UI
 */
function updateProviderSelection() {
    // Update STT selection
    document.querySelectorAll('.provider-item[data-provider-type="stt"]').forEach(item => {
        const isSelected = item.dataset.providerId === selectedSTTProvider;
        item.classList.toggle('selected', isSelected);
        const radio = item.querySelector('.provider-radio');
        if (radio) radio.checked = isSelected;
    });

    // Update TTS selection
    document.querySelectorAll('.provider-item[data-provider-type="tts"]').forEach(item => {
        const isSelected = item.dataset.providerId === selectedTTSProvider;
        item.classList.toggle('selected', isSelected);
        const radio = item.querySelector('.provider-radio');
        if (radio) radio.checked = isSelected;
    });
}

// ==============================================================================
// PHASE 38: STT USAGE TRACKING & CREDENTIALS
// ==============================================================================

/**
 * Phase 38: Load STT usage statistics from backend
 */
async function loadSTTUsage() {
    try {
        const data = await apiCall('/admin/voice/usage');
        displaySTTUsage(data);
    } catch (error) {
        console.error('Failed to load STT usage:', error);
        // Show default empty state
        displaySTTUsage(null);
    }
}

/**
 * Phase 38: Display STT usage in the UI
 */
function displaySTTUsage(data) {
    const usageBar = document.getElementById('usageBar');
    const usageUsed = document.getElementById('usageUsed');
    const usageQuota = document.getElementById('usageQuota');
    const usagePercent = document.getElementById('usagePercent');

    if (!usageBar || !usageUsed || !usageQuota || !usagePercent) {
        return; // Elements not in DOM
    }

    if (!data || !data.google_cloud_stt) {
        // No usage data available
        usageBar.style.width = '0%';
        usageUsed.textContent = '0:00';
        usageQuota.textContent = '60:00';
        usagePercent.textContent = '0%';
        usageBar.className = 'usage-bar';
        return;
    }

    const usage = data.google_cloud_stt;
    const usedSeconds = usage.used_seconds || 0;
    const quotaSeconds = usage.quota_seconds || 3600;
    const percent = usage.usage_percent || 0;

    // Format time as M:SS
    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    // Update display
    usageBar.style.width = `${Math.min(percent, 100)}%`;
    usageUsed.textContent = formatTime(usedSeconds);
    usageQuota.textContent = formatTime(quotaSeconds);
    usagePercent.textContent = `${Math.round(percent)}%`;

    // Apply warning/danger classes based on usage
    usageBar.className = 'usage-bar';
    if (percent >= 90) {
        usageBar.classList.add('danger');
    } else if (percent >= 80) {
        usageBar.classList.add('warning');
    }
}

/**
 * Phase 38: Load credentials status from backend
 */
async function loadCredentialsStatus() {
    try {
        const data = await apiCall('/admin/voice/credentials/status');
        displayCredentialsStatus(data);
    } catch (error) {
        console.error('Failed to load credentials status:', error);
        // Show default unconfigured state
        displayCredentialsStatus(null);
    }
}

/**
 * Phase 38/39A: Display credentials status in the UI
 */
function displayCredentialsStatus(data) {
    // Google Cloud STT credentials
    const googlePath = document.getElementById('googleCredentialPath');
    const googleStatus = document.getElementById('googleCredentialStatus');
    const googleProjectId = document.getElementById('googleProjectId');
    const googleUpdatedAt = document.getElementById('googleUpdatedAt');

    if (googlePath && googleStatus) {
        if (data && data.google_cloud_stt) {
            const cred = data.google_cloud_stt;
            if (cred.is_configured) {
                googlePath.textContent = cred.masked_path || 'Configured';
                if (cred.is_valid) {
                    googleStatus.textContent = 'Valid';
                    googleStatus.className = 'status-badge valid';
                } else {
                    googleStatus.textContent = 'Invalid';
                    googleStatus.className = 'status-badge invalid';
                }
                // Phase 39A: Show project ID and updated timestamp
                if (googleProjectId) {
                    googleProjectId.textContent = cred.project_id ? `Project: ${cred.project_id}` : '';
                }
                if (googleUpdatedAt && cred.updated_at) {
                    googleUpdatedAt.textContent = `Updated: ${formatTimestamp(cred.updated_at)}`;
                }
            } else {
                googlePath.textContent = 'Not configured';
                googleStatus.textContent = '--';
                googleStatus.className = 'status-badge';
                if (googleProjectId) googleProjectId.textContent = '';
                if (googleUpdatedAt) googleUpdatedAt.textContent = '';
            }
        } else {
            googlePath.textContent = 'Not configured';
            googleStatus.textContent = '--';
            googleStatus.className = 'status-badge';
            if (googleProjectId) googleProjectId.textContent = '';
            if (googleUpdatedAt) googleUpdatedAt.textContent = '';
        }
    }

    // OpenAI credentials
    const openaiKey = document.getElementById('openaiCredentialKey');
    const openaiStatus = document.getElementById('openaiCredentialStatus');
    const openaiUpdatedAt = document.getElementById('openaiUpdatedAt');

    if (openaiKey && openaiStatus) {
        if (data && data.openai) {
            const cred = data.openai;
            if (cred.is_configured) {
                openaiKey.textContent = cred.masked_key || 'Configured';
                if (cred.is_valid) {
                    openaiStatus.textContent = 'Valid';
                    openaiStatus.className = 'status-badge valid';
                } else {
                    openaiStatus.textContent = 'Invalid';
                    openaiStatus.className = 'status-badge invalid';
                }
                // Phase 39A: Show updated timestamp
                if (openaiUpdatedAt && cred.updated_at) {
                    openaiUpdatedAt.textContent = `Updated: ${formatTimestamp(cred.updated_at)}`;
                }
            } else {
                openaiKey.textContent = 'Not configured';
                openaiStatus.textContent = '--';
                openaiStatus.className = 'status-badge';
                if (openaiUpdatedAt) openaiUpdatedAt.textContent = '';
            }
        } else {
            openaiKey.textContent = 'Not configured';
            openaiStatus.textContent = '--';
            openaiStatus.className = 'status-badge';
            if (openaiUpdatedAt) openaiUpdatedAt.textContent = '';
        }
    }
}

/**
 * Phase 39A: Format ISO timestamp for display
 */
function formatTimestamp(isoString) {
    if (!isoString) return '';
    try {
        const date = new Date(isoString);
        return date.toLocaleString();
    } catch (e) {
        return isoString;
    }
}

// ==============================================================================
// PHASE 39A: CREDENTIAL INPUT HANDLERS
// ==============================================================================

// Track Google credential file content
let pendingGoogleCredentialJson = null;

/**
 * Phase 39A: Toggle password visibility for OpenAI key input
 */
function toggleOpenaiKeyVisibility() {
    const input = document.getElementById('openaiApiKeyInput');
    const btn = document.getElementById('toggleOpenaiKeyBtn');
    if (input.type === 'password') {
        input.type = 'text';
        btn.innerHTML = '<span class="eye-icon">&#128064;</span>';
    } else {
        input.type = 'password';
        btn.innerHTML = '<span class="eye-icon">&#128065;</span>';
    }
}

/**
 * Phase 39A: Verify OpenAI API key
 */
async function verifyOpenaiKey() {
    const input = document.getElementById('openaiApiKeyInput');
    const key = input.value.trim();

    if (!key) {
        showNotification('Please enter an API key to verify', 'error');
        return;
    }

    try {
        const data = await apiCall('/admin/voice/credentials/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                provider: 'openai',
                api_key: key
            })
        });

        if (data.valid) {
            showNotification('API key format is valid', 'success');
        } else {
            showNotification(`Invalid: ${data.error}`, 'error');
        }
    } catch (error) {
        showNotification(`Verification failed: ${error.message}`, 'error');
    }
}

/**
 * Phase 39A: Save OpenAI API key
 */
async function saveOpenaiKey() {
    const input = document.getElementById('openaiApiKeyInput');
    const key = input.value.trim();

    if (!key) {
        showNotification('Please enter an API key', 'error');
        return;
    }

    const saveBtn = document.getElementById('saveOpenaiKeyBtn');
    const originalText = saveBtn.textContent;
    saveBtn.textContent = 'Saving...';
    saveBtn.disabled = true;

    try {
        const data = await apiCall('/admin/voice/credentials', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                provider: 'openai',
                api_key: key
            })
        });

        if (data.success) {
            const storageMsg = data.persisted ? ' (encrypted)' : ' (runtime only)';
            showNotification(`OpenAI API key saved${storageMsg}`, 'success');
            input.value = '';  // Clear input
            loadCredentialsStatus();  // Reload status
        } else {
            showNotification('Failed to save API key', 'error');
        }
    } catch (error) {
        showNotification(`Save failed: ${error.message}`, 'error');
    } finally {
        saveBtn.textContent = originalText;
        saveBtn.disabled = false;
    }
}

/**
 * Phase 39A: Handle Google credential file selection
 */
function handleGoogleCredentialFile(event) {
    const file = event.target.files[0];
    const filenameDisplay = document.getElementById('googleCredentialFilename');
    const saveBtn = document.getElementById('saveGoogleCredBtn');
    const verifyBtn = document.getElementById('verifyGoogleCredBtn');

    if (!file) {
        filenameDisplay.textContent = 'No file selected';
        saveBtn.disabled = true;
        verifyBtn.disabled = true;
        pendingGoogleCredentialJson = null;
        return;
    }

    filenameDisplay.textContent = file.name;

    // Read file content
    const reader = new FileReader();
    reader.onload = function(e) {
        try {
            // Validate JSON
            const json = JSON.parse(e.target.result);
            pendingGoogleCredentialJson = e.target.result;
            saveBtn.disabled = false;
            verifyBtn.disabled = false;
        } catch (err) {
            showNotification('Invalid JSON file', 'error');
            filenameDisplay.textContent = 'Invalid file';
            pendingGoogleCredentialJson = null;
            saveBtn.disabled = true;
            verifyBtn.disabled = true;
        }
    };
    reader.readAsText(file);
}

/**
 * Phase 39A: Verify Google Cloud credentials
 */
async function verifyGoogleCredential() {
    if (!pendingGoogleCredentialJson) {
        showNotification('Please select a credentials file first', 'error');
        return;
    }

    try {
        const data = await apiCall('/admin/voice/credentials/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                provider: 'google-cloud-stt',
                credentials_json: pendingGoogleCredentialJson
            })
        });

        if (data.valid) {
            showNotification(`Valid! Project: ${data.project_id}`, 'success');
        } else {
            showNotification(`Invalid: ${data.error}`, 'error');
        }
    } catch (error) {
        showNotification(`Verification failed: ${error.message}`, 'error');
    }
}

/**
 * Phase 39A: Save Google Cloud credentials
 */
async function saveGoogleCredential() {
    if (!pendingGoogleCredentialJson) {
        showNotification('Please select a credentials file first', 'error');
        return;
    }

    const saveBtn = document.getElementById('saveGoogleCredBtn');
    const originalText = saveBtn.textContent;
    saveBtn.textContent = 'Saving...';
    saveBtn.disabled = true;

    try {
        const data = await apiCall('/admin/voice/credentials', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                provider: 'google-cloud-stt',
                credentials_json: pendingGoogleCredentialJson
            })
        });

        if (data.success) {
            const storageMsg = data.persisted ? ' (encrypted)' : ' (runtime only)';
            const projectMsg = data.validation?.project_id ? ` - Project: ${data.validation.project_id}` : '';
            showNotification(`Google credentials saved${storageMsg}${projectMsg}`, 'success');

            // Reset file input
            document.getElementById('googleCredentialFileInput').value = '';
            document.getElementById('googleCredentialFilename').textContent = 'No file selected';
            pendingGoogleCredentialJson = null;
            saveBtn.disabled = true;
            document.getElementById('verifyGoogleCredBtn').disabled = true;

            loadCredentialsStatus();  // Reload status
        } else {
            showNotification('Failed to save credentials', 'error');
        }
    } catch (error) {
        showNotification(`Save failed: ${error.message}`, 'error');
    } finally {
        saveBtn.textContent = originalText;
        // Keep disabled if no pending credential
        if (!pendingGoogleCredentialJson) {
            saveBtn.disabled = true;
        }
    }
}

// ==============================================================================
// PHASE 39B: DEBUG PANEL SETTINGS
// ==============================================================================

/**
 * Phase 39B: Load debug settings from server
 */
async function loadDebugSettings() {
    try {
        console.log('[DEBUG] Loading debug settings...');
        const data = await apiCall('/admin/debug/status');
        console.log('[DEBUG] Debug settings loaded:', data);
        updateDebugToggleUI(data.debug_enabled);
    } catch (error) {
        console.error('Failed to load debug settings:', error);
        updateDebugToggleUI(false);
    }
}

/**
 * Phase 39B: Update debug toggle UI state
 */
function updateDebugToggleUI(isEnabled) {
    const toggle = document.getElementById('debugModeToggle');
    const label = document.getElementById('debugModeLabel');

    if (toggle) {
        toggle.checked = isEnabled;
    }
    if (label) {
        label.textContent = isEnabled ? 'Debug Panel Visible' : 'Debug Panel Hidden';
        label.className = isEnabled ? 'toggle-label active' : 'toggle-label';
    }
}

/**
 * Phase 39B: Toggle debug mode on/off
 */
async function toggleDebugMode(enabled) {
    try {
        console.log('[DEBUG] Toggling debug mode to:', enabled);
        const data = await apiCall('/admin/debug/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled })
        });
        console.log('[DEBUG] Toggle response:', data);

        if (data.success) {
            updateDebugToggleUI(data.debug_enabled);
            showNotification(data.message, 'success');
        } else {
            // Revert toggle if failed
            updateDebugToggleUI(!enabled);
            showNotification('Failed to update debug mode', 'error');
        }
    } catch (error) {
        // Revert toggle on error
        updateDebugToggleUI(!enabled);
        showNotification(`Failed to toggle debug mode: ${error.message}`, 'error');
    }
}

// ==============================================================================
// PHASE 42: TEST HARNESS
// ==============================================================================

/**
 * Phase 42: Load test harness data (questions and last results)
 */
async function loadTestHarness() {
    const questionsList = document.getElementById('testQuestionsList');
    const resultsContainer = document.getElementById('testResultsContainer');

    // Show loading state
    if (questionsList) {
        questionsList.innerHTML = '<div class="loading-state">Loading questions...</div>';
    }

    try {
        // Load questions
        const questionsData = await apiCall('/admin/test-harness/questions');
        testQuestions = questionsData.questions || [];
        renderTestQuestions();

        // Try to load last results (they may not exist)
        try {
            const resultsData = await apiCall('/admin/test-harness/results/last');
            if (resultsData.results && resultsData.results.length > 0) {
                testResults = resultsData.results;
                renderTestResults();
                updateTestSummary(resultsData.summary);
            } else {
                if (resultsContainer) {
                    resultsContainer.innerHTML = '<div class="empty-results">No test results yet. Run tests to see results here.</div>';
                }
                updateTestSummary(null);
            }
        } catch (e) {
            // No previous results, that's ok
            if (resultsContainer) {
                resultsContainer.innerHTML = '<div class="empty-results">No test results yet. Run tests to see results here.</div>';
            }
            updateTestSummary(null);
        }

    } catch (error) {
        showNotification(`Failed to load test harness: ${error.message}`, 'error');
        if (questionsList) {
            questionsList.innerHTML = '<div class="error-state">Failed to load questions</div>';
        }
    }
}

/**
 * Phase 42: Render test questions list
 */
function renderTestQuestions() {
    const questionsList = document.getElementById('testQuestionsList');
    if (!questionsList) return;

    if (testQuestions.length === 0) {
        questionsList.innerHTML = '<div class="empty-state">No questions added yet</div>';
        return;
    }

    questionsList.innerHTML = testQuestions.map((q, index) => `
        <div class="question-item" data-id="${q.id}">
            <span class="question-number">${index + 1}.</span>
            <span class="question-text">${escapeHtml(q.question)}</span>
            <button class="btn-danger btn-small delete-question-btn" onclick="deleteTestQuestion('${q.id}')">
                &times;
            </button>
        </div>
    `).join('');
}

/**
 * Phase 42: Render test results
 */
/**
 * Phase 44: Build orchestrator details HTML for test results
 */
function buildOrchestratorDetailsHtml(response) {
    if (!response) return '';

    const parts = [];

    // Response mode (Phase 44)
    const responseMode = response.response_mode || response.mode || 'unknown';
    parts.push(`<span class="detail-label">Response Mode:</span> <span class="detail-value mode-${responseMode}">${responseMode}</span>`);

    // Semantic relevance (Phase 44)
    if (response.semantic_relevance && response.semantic_relevance !== 'unknown') {
        parts.push(`<span class="detail-label">Semantic:</span> <span class="detail-value semantic-${response.semantic_relevance}">${response.semantic_relevance}</span>`);
    }

    // Extractor used (Phase 44)
    if (response.extractor_used) {
        parts.push(`<span class="detail-label">Extractor:</span> <span class="detail-value extractor">${response.extractor_used}</span>`);
    }

    // Confidence
    const confidence = response.confidence || 'N/A';
    const confidenceScore = response.confidence_score ? ` (${response.confidence_score.toFixed(1)}%)` : '';
    parts.push(`<span class="detail-label">Confidence:</span> <span class="detail-value">${confidence}${confidenceScore}</span>`);

    // Grounding
    if (response.grounding_mode && response.grounding_mode !== 'unknown') {
        const grounded = response.grounding_passed ? 'Yes' : 'No';
        parts.push(`<span class="detail-label">Grounding:</span> <span class="detail-value">${response.grounding_mode} (${grounded})</span>`);
    }

    return parts.length > 0 ? `<div class="result-orchestrator-details">${parts.join(' | ')}</div>` : '';
}

function renderTestResults() {
    const resultsContainer = document.getElementById('testResultsContainer');
    if (!resultsContainer) return;

    if (testResults.length === 0) {
        resultsContainer.innerHTML = '<div class="empty-results">No test results yet</div>';
        return;
    }

    resultsContainer.innerHTML = testResults.map((r, index) => {
        const response = r.response || {};
        const answerText = response.answer || 'No response';
        const orchestratorDetails = buildOrchestratorDetailsHtml(response);

        return `
        <div class="result-item ${r.passed ? 'passed' : 'failed'}">
            <div class="result-header">
                <span class="result-number">Q${index + 1}</span>
                <span class="result-category">${r.category || 'general'}</span>
                <span class="result-status ${r.passed ? 'pass' : 'fail'}">${r.passed ? 'PASS' : 'FAIL'}</span>
            </div>
            <div class="result-question">${escapeHtml(r.query)}</div>
            ${orchestratorDetails}
            <div class="result-response">${formatAnswerText(answerText)}</div>
            ${r.failures && r.failures.length > 0 ? `<div class="result-failures">Failures: ${r.failures.join(', ')}</div>` : ''}
        </div>
    `}).join('');
}

/**
 * Phase 42: Append a single result item (for streaming)
 */
function appendResultItem(result, index) {
    const resultsContainer = document.getElementById('testResultsContainer');
    if (!resultsContainer) return;

    // Clear empty state on first result
    if (index === 0) {
        resultsContainer.innerHTML = '';
    }

    const response = result.response || {};
    const answerText = response.answer || 'No response';
    const orchestratorDetails = buildOrchestratorDetailsHtml(response);

    const resultHtml = `
        <div class="result-item ${result.passed ? 'passed' : 'failed'}">
            <div class="result-header">
                <span class="result-number">Q${index + 1}</span>
                <span class="result-category">${result.category || 'general'}</span>
                <span class="result-status ${result.passed ? 'pass' : 'fail'}">${result.passed ? 'PASS' : 'FAIL'}</span>
            </div>
            <div class="result-question">${escapeHtml(result.query)}</div>
            ${orchestratorDetails}
            <div class="result-response">${formatAnswerText(answerText)}</div>
            ${result.failures && result.failures.length > 0 ? `<div class="result-failures">Failures: ${result.failures.join(', ')}</div>` : ''}
        </div>
    `;

    resultsContainer.insertAdjacentHTML('beforeend', resultHtml);

    // Auto-scroll to bottom
    resultsContainer.scrollTop = resultsContainer.scrollHeight;
}

/**
 * Phase 42: Update test summary stats
 */
function updateTestSummary(summary) {
    const totalEl = document.getElementById('testTotalCount');
    const passedEl = document.getElementById('testPassedCount');
    const failedEl = document.getElementById('testFailedCount');
    const rateEl = document.getElementById('testPassRate');

    if (!summary) {
        if (totalEl) totalEl.textContent = '0';
        if (passedEl) passedEl.textContent = '0';
        if (failedEl) failedEl.textContent = '0';
        if (rateEl) rateEl.textContent = '--';
        return;
    }

    if (totalEl) totalEl.textContent = summary.total || 0;
    if (passedEl) passedEl.textContent = summary.passed || 0;
    if (failedEl) failedEl.textContent = summary.failed || 0;
    if (rateEl) {
        const rate = summary.pass_rate !== undefined ? `${summary.pass_rate.toFixed(1)}%` : '--';
        rateEl.textContent = rate;
    }
}

/**
 * Phase 42: Add a test question
 */
async function addTestQuestion() {
    const input = document.getElementById('newQuestionInput');
    const question = input.value.trim();

    if (!question) {
        showNotification('Please enter a question', 'error');
        return;
    }

    const addBtn = document.getElementById('addQuestionBtn');
    addBtn.disabled = true;

    try {
        const data = await apiCall('/admin/test-harness/questions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: question })
        });

        testQuestions.push(data.question);
        renderTestQuestions();
        input.value = '';
        showNotification('Question added', 'success');

    } catch (error) {
        showNotification(`Failed to add question: ${error.message}`, 'error');
    } finally {
        addBtn.disabled = false;
    }
}

/**
 * Phase 42: Delete a test question
 */
async function deleteTestQuestion(questionId) {
    try {
        await apiCall(`/admin/test-harness/questions/${questionId}`, {
            method: 'DELETE'
        });

        testQuestions = testQuestions.filter(q => q.id !== questionId);
        renderTestQuestions();
        showNotification('Question deleted', 'success');

    } catch (error) {
        showNotification(`Failed to delete question: ${error.message}`, 'error');
    }
}

// Make deleteTestQuestion available globally for onclick handlers
window.deleteTestQuestion = deleteTestQuestion;

/**
 * Phase 42: Import questions from CSV file
 */
async function importTestQuestions(file) {
    if (!file) {
        showNotification('No file selected', 'error');
        return;
    }

    const importBtn = document.getElementById('importQuestionsBtn');
    const originalText = importBtn.textContent;
    importBtn.textContent = 'Importing...';
    importBtn.disabled = true;

    try {
        const formData = new FormData();
        formData.append('file', file);

        const data = await apiCall('/admin/test-harness/questions/import', {
            method: 'POST',
            body: formData
        });

        showNotification(`Imported ${data.imported} questions`, 'success');

        // Reload questions
        const questionsData = await apiCall('/admin/test-harness/questions');
        testQuestions = questionsData.questions || [];
        renderTestQuestions();

    } catch (error) {
        showNotification(`Import failed: ${error.message}`, 'error');
    } finally {
        importBtn.textContent = originalText;
        importBtn.disabled = false;
        document.getElementById('importQuestionsInput').value = '';
    }
}

/**
 * Phase 42: Run tests with SSE streaming
 */
async function runTests() {
    if (isRunningTests) {
        showNotification('Tests already running', 'info');
        return;
    }

    if (testQuestions.length === 0) {
        showNotification('No questions to test', 'error');
        return;
    }

    isRunningTests = true;
    testResults = [];

    const runBtn = document.getElementById('runTestsBtn');
    const progressBadge = document.getElementById('testProgressBadge');
    const resultsContainer = document.getElementById('testResultsContainer');

    runBtn.disabled = true;
    runBtn.textContent = 'Running...';
    progressBadge.classList.remove('hidden');
    progressBadge.textContent = '0/' + testQuestions.length;

    // Clear previous results
    if (resultsContainer) {
        resultsContainer.innerHTML = '<div class="running-state">Running tests...</div>';
    }
    updateTestSummary(null);

    // Open SSE connection
    testEventSource = new EventSource('/admin/test-harness/execute/stream');

    testEventSource.addEventListener('progress', (event) => {
        const data = JSON.parse(event.data);
        progressBadge.textContent = `${data.current}/${data.total}`;
    });

    testEventSource.addEventListener('result', (event) => {
        const result = JSON.parse(event.data);
        testResults.push(result);
        appendResultItem(result, testResults.length - 1);
    });

    testEventSource.addEventListener('complete', (event) => {
        const summary = JSON.parse(event.data);
        updateTestSummary(summary);
        finishTests();
        showNotification(`Tests complete: ${summary.passed}/${summary.total} passed (${summary.pass_rate.toFixed(1)}%)`, 'success');
    });

    testEventSource.addEventListener('error', (event) => {
        let errorMsg = 'Test execution error';
        try {
            const data = JSON.parse(event.data);
            errorMsg = data.message || errorMsg;
        } catch (e) {}
        showNotification(errorMsg, 'error');
        finishTests();
    });

    testEventSource.onerror = (event) => {
        // SSE connection error
        if (isRunningTests) {
            showNotification('Connection to server lost', 'error');
            finishTests();
        }
    };
}

/**
 * Phase 42: Clean up after tests complete
 */
function finishTests() {
    isRunningTests = false;

    if (testEventSource) {
        testEventSource.close();
        testEventSource = null;
    }

    const runBtn = document.getElementById('runTestsBtn');
    const progressBadge = document.getElementById('testProgressBadge');
    const downloadBtn = document.getElementById('downloadResultsBtn');

    if (runBtn) {
        runBtn.disabled = false;
        runBtn.textContent = 'Run Tests';
    }
    if (progressBadge) {
        progressBadge.classList.add('hidden');
    }
    if (downloadBtn && testResults.length > 0) {
        downloadBtn.disabled = false;
    }
}

/**
 * Phase 42: Download test results as .txt file
 */
async function downloadTestResults() {
    if (testResults.length === 0) {
        showNotification('No results to download', 'error');
        return;
    }

    try {
        const response = await fetch('/admin/test-harness/results/download');

        if (response.status === 401) {
            window.location.href = '/admin/login';
            return;
        }

        if (!response.ok) {
            throw new Error('Download failed');
        }

        // Get filename from header or use default
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'test_harness_results.txt';
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

        showNotification('Results downloaded', 'success');

    } catch (error) {
        showNotification(`Download failed: ${error.message}`, 'error');
    }
}

/**
 * Save voice configuration
 * Phase 37: Include fallback provider selections
 */
async function saveVoiceConfig() {
    if (!voiceConfigChanged) return;

    const saveBtn = document.getElementById('saveVoiceConfigBtn');
    const statusSpan = document.getElementById('voiceConfigStatus');
    const originalText = saveBtn.textContent;

    saveBtn.textContent = 'Saving...';
    saveBtn.disabled = true;
    statusSpan.textContent = '';

    // Phase 37: Get fallback selections from dropdowns
    const sttFallbackSelect = document.getElementById('sttFallbackSelect');
    const ttsFallbackSelect = document.getElementById('ttsFallbackSelect');
    const sttFallback = sttFallbackSelect?.value || null;
    const ttsFallback = ttsFallbackSelect?.value || null;

    try {
        const data = await apiCall('/admin/voice/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                stt_provider: selectedSTTProvider,
                tts_provider: selectedTTSProvider,
                // Phase 37: Include fallback selections
                stt_fallback_provider: sttFallback,
                tts_fallback_provider: ttsFallback
            })
        });

        showNotification('Voice configuration saved successfully', 'success');
        statusSpan.textContent = 'Saved';
        statusSpan.className = 'config-status success';
        voiceConfigChanged = false;

        // Reload to get updated state
        await loadVoiceConfig();

    } catch (error) {
        showNotification(`Failed to save voice config: ${error.message}`, 'error');
        statusSpan.textContent = 'Save failed';
        statusSpan.className = 'config-status error';
        saveBtn.disabled = false;
    } finally {
        saveBtn.textContent = originalText;
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
            document.getElementById('fileName').textContent = 'Choose a file or drag & drop';
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

    // Phase 55: Rebuild Index Button
    const rebuildBtn = document.getElementById('rebuildIndexBtn');
    if (rebuildBtn) {
        rebuildBtn.addEventListener('click', rebuildIndex);
    }

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
    // ANALYTICS EVENT LISTENERS - Phase 16
    // ==============================================================================

    // Refresh Analytics Button
    document.getElementById('refreshAnalyticsBtn').addEventListener('click', loadAnalytics);

    // ==============================================================================
    // VOICE CONFIGURATION EVENT LISTENERS - Phase 36
    // ==============================================================================

    // Refresh Voice Config Button
    document.getElementById('refreshVoiceBtn').addEventListener('click', loadVoiceConfig);

    // Save Voice Config Button
    document.getElementById('saveVoiceConfigBtn').addEventListener('click', saveVoiceConfig);

    // ==============================================================================
    // CREDENTIAL INPUT EVENT LISTENERS - Phase 39A
    // ==============================================================================

    // OpenAI API Key handlers
    const toggleOpenaiBtn = document.getElementById('toggleOpenaiKeyBtn');
    if (toggleOpenaiBtn) {
        toggleOpenaiBtn.addEventListener('click', toggleOpenaiKeyVisibility);
    }

    const saveOpenaiBtn = document.getElementById('saveOpenaiKeyBtn');
    if (saveOpenaiBtn) {
        saveOpenaiBtn.addEventListener('click', saveOpenaiKey);
    }

    const verifyOpenaiBtn = document.getElementById('verifyOpenaiKeyBtn');
    if (verifyOpenaiBtn) {
        verifyOpenaiBtn.addEventListener('click', verifyOpenaiKey);
    }

    // Google Cloud credentials handlers
    const uploadGoogleBtn = document.getElementById('uploadGoogleCredBtn');
    if (uploadGoogleBtn) {
        uploadGoogleBtn.addEventListener('click', () => {
            document.getElementById('googleCredentialFileInput').click();
        });
    }

    const googleFileInput = document.getElementById('googleCredentialFileInput');
    if (googleFileInput) {
        googleFileInput.addEventListener('change', handleGoogleCredentialFile);
    }

    const saveGoogleBtn = document.getElementById('saveGoogleCredBtn');
    if (saveGoogleBtn) {
        saveGoogleBtn.addEventListener('click', saveGoogleCredential);
    }

    const verifyGoogleBtn = document.getElementById('verifyGoogleCredBtn');
    if (verifyGoogleBtn) {
        verifyGoogleBtn.addEventListener('click', verifyGoogleCredential);
    }

    // ==============================================================================
    // DEBUG PANEL EVENT LISTENERS - Phase 39B
    // ==============================================================================

    const debugModeToggle = document.getElementById('debugModeToggle');
    if (debugModeToggle) {
        debugModeToggle.addEventListener('change', (e) => {
            toggleDebugMode(e.target.checked);
        });
    }

    // ==============================================================================
    // TEST HARNESS EVENT LISTENERS - Phase 42
    // ==============================================================================

    // Add Question Button
    const addQuestionBtn = document.getElementById('addQuestionBtn');
    if (addQuestionBtn) {
        addQuestionBtn.addEventListener('click', addTestQuestion);
    }

    // New Question Input - Enter key to add
    const newQuestionInput = document.getElementById('newQuestionInput');
    if (newQuestionInput) {
        newQuestionInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                addTestQuestion();
            }
        });
    }

    // Import Questions Button (trigger file input)
    const importQuestionsBtn = document.getElementById('importQuestionsBtn');
    if (importQuestionsBtn) {
        importQuestionsBtn.addEventListener('click', () => {
            document.getElementById('importQuestionsInput').click();
        });
    }

    // Import Questions File Input
    const importQuestionsInput = document.getElementById('importQuestionsInput');
    if (importQuestionsInput) {
        importQuestionsInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                importTestQuestions(file);
            }
        });
    }

    // Run Tests Button
    const runTestsBtn = document.getElementById('runTestsBtn');
    if (runTestsBtn) {
        runTestsBtn.addEventListener('click', runTests);
    }

    // Download Results Button
    const downloadResultsBtn = document.getElementById('downloadResultsBtn');
    if (downloadResultsBtn) {
        downloadResultsBtn.addEventListener('click', downloadTestResults);
    }

    // ==============================================================================
    // INITIALIZATION - Phase 36: Section-based navigation
    // ==============================================================================

    // Check authentication first
    checkAuth().then(isAuthenticated => {
        if (isAuthenticated) {
            // Initialize section navigation (will load initial section data)
            initSectionNavigation();
        }
    });
});

// Make deleteDocument available globally for onclick handlers
window.deleteDocument = deleteDocument;
