/**
 * Admin Document Management System - Phase 36
 * Frontend JavaScript for managing documents, analytics, and voice config
 */

// ==============================================================================
// STATE MANAGEMENT
// ==============================================================================

let isUploading = false;
let isDeleting = false;
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
            ConversationViewer.init();
            break;
        case 'documents':
            loadDocuments();
            break;
        case 'advertisements':
            loadAdvertisements();
            break;
        case 'welcome':
            loadWelcomeMessageAdmin();
            break;
        case 'faqs':
            loadFAQsAdmin();
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
 * Check if Developer section should be visible in sidebar
 */
async function checkDevSectionVisibility() {
    try {
        const response = await fetch('/api/settings/dev-section-visible');
        if (response.ok) {
            const data = await response.json();
            const devNavItem = document.querySelector('.nav-item[data-section="developer"]');
            const devSection = document.getElementById('section-developer');
            if (devNavItem) {
                if (!data.dev_section_visible) {
                    devNavItem.style.display = 'none';
                    if (devSection) devSection.style.display = 'none';
                    // If currently on developer section, switch to first available
                    if (currentSection === 'developer') {
                        switchSection('analytics');
                    }
                } else {
                    devNavItem.style.display = '';
                    if (devSection) devSection.style.display = '';
                }
            }
        }
    } catch (error) {
        console.warn('[ADMIN] Failed to check dev section visibility:', error);
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
    // DEPRECATED: Document upload is no longer supported
    // Use uploadRAGPackage instead
    showNotification('Document upload is no longer supported. Use RAG Package upload instead.', 'error');
}

/**
 * Upload RAG Package (vector store .zip) to server
 */
async function uploadRAGPackage(file) {
    if (isUploading) return;

    // Validate file type
    if (!file.name.endsWith('.zip')) {
        showNotification('File must be a .zip archive', 'error');
        return;
    }

    isUploading = true;
    const uploadBtn = document.getElementById('ragUploadBtn');
    const statusDiv = document.getElementById('ragUploadStatus');
    const originalText = uploadBtn.textContent;

    uploadBtn.textContent = 'Uploading...';
    uploadBtn.disabled = true;
    statusDiv.innerHTML = '<span class="status-loading">Uploading and processing package...</span>';

    try {
        const formData = new FormData();
        formData.append('file', file);

        const data = await apiCall('/admin/upload_rag_package', {
            method: 'POST',
            body: formData
        });

        const docCount = data.documents || 0;
        statusDiv.innerHTML = `<span class="status-success">Package uploaded successfully! ${docCount} documents loaded.</span>`;
        showNotification(`RAG package uploaded successfully! ${docCount} documents loaded.`, 'success');

        // Reset file input
        const ragFileInput = document.getElementById('ragFileInput');
        ragFileInput.value = '';
        document.getElementById('ragFileName').textContent = 'Choose a .zip file or drag & drop';
        uploadBtn.disabled = true;

        // Reload documents table
        await loadDocuments();

    } catch (error) {
        statusDiv.innerHTML = `<span class="status-error">Upload failed: ${error.message}</span>`;
        showNotification(`RAG package upload failed: ${error.message}`, 'error');
    } finally {
        isUploading = false;
        uploadBtn.textContent = originalText;
        uploadBtn.disabled = !document.getElementById('ragFileInput').files.length;
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
    // Total conversations (derived from conversations.jsonl)
    document.getElementById('stat-total-conversations').textContent =
        (data.total_conversations || 0).toLocaleString();

    // Feedback breakdown
    const feedbackDiv = document.getElementById('feedback-breakdown');
    const feedback = data.feedback || {};
    feedbackDiv.innerHTML = [
        { label: 'Liked', count: feedback.liked || 0 },
        { label: 'Not Helpful', count: feedback.disliked || 0 },
        { label: 'No Feedback', count: feedback.no_feedback || 0 },
    ].map(item => `
        <div class="breakdown-item">
            <span class="breakdown-label">${item.label}</span>
            <span class="breakdown-value">${item.count}</span>
        </div>
    `).join('');
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
 * Phase 50: Also loads metadata visibility settings
 */
async function loadDebugSettings() {
    try {
        console.log('[DEBUG] Loading debug settings...');
        const data = await apiCall('/admin/debug/status');
        console.log('[DEBUG] Debug settings loaded:', data);
        updateDebugToggleUI(data.debug_enabled);

        // Phase 50: Also load metadata visibility settings
        await loadMetadataSettings();
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
// PHASE 50: METADATA VISIBILITY SETTINGS
// ==============================================================================

/**
 * Phase 50: Load metadata visibility settings from server
 */
async function loadMetadataSettings() {
    try {
        console.log('[METADATA] Loading metadata settings...');
        const data = await apiCall('/admin/metadata/status');
        console.log('[METADATA] Settings loaded:', data);
        updateMetadataToggleUI(data.metadata_visible);
    } catch (error) {
        console.error('[METADATA] Failed to load settings:', error);
        // Default to visible on error
        updateMetadataToggleUI(true);
    }
}

/**
 * Phase 50: Update metadata toggle UI state
 */
function updateMetadataToggleUI(enabled) {
    const toggle = document.getElementById('metadataVisibleToggle');
    const label = document.getElementById('metadataToggleLabel');

    if (toggle) {
        toggle.checked = enabled;
    }
    if (label) {
        label.textContent = enabled ? 'Metadata Visible' : 'Metadata Hidden';
        label.className = enabled ? 'toggle-label active' : 'toggle-label';
    }
}

/**
 * Phase 50: Toggle metadata visibility on/off
 */
async function toggleMetadataVisibility(enabled) {
    try {
        console.log('[METADATA] Toggling metadata visibility to:', enabled);
        const data = await apiCall('/admin/metadata/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled })
        });
        console.log('[METADATA] Toggle response:', data);

        if (data.success) {
            updateMetadataToggleUI(data.metadata_visible);
            showNotification(data.message, 'success');
        } else {
            // Revert toggle if failed
            updateMetadataToggleUI(!enabled);
            showNotification('Failed to update metadata visibility', 'error');
        }
    } catch (error) {
        // Revert toggle on error
        updateMetadataToggleUI(!enabled);
        showNotification(`Failed to toggle metadata visibility: ${error.message}`, 'error');
    }
}

// ==============================================================================
// PHASE 48: ADVERTISEMENT MANAGEMENT
// ==============================================================================

/**
 * Load advertisements for admin management
 * Phase 54: Supports both image and text advertisements
 */
async function loadAdvertisements() {
    const grid = document.getElementById('adGrid');
    const stats = document.getElementById('adsStats');
    const loading = document.getElementById('adsLoadingIndicator');

    if (!grid) return;

    // Show loading
    if (loading) loading.classList.remove('hidden');

    try {
        const data = await apiCall('/admin/advertisements');
        const ads = data.advertisements || [];

        if (ads.length === 0) {
            grid.innerHTML = '<div class="ad-empty-state">No advertisements uploaded yet</div>';
        } else {
            grid.innerHTML = ads.map((ad, index) => renderAdCard(ad, index)).join('');
            // Set up drag-and-drop handlers
            setupAdDragAndDrop(grid);
        }

        // Update stats
        if (stats) {
            const activeCount = ads.filter(a => a.status === 'active').length;
            const imageCount = ads.filter(a => a.ad_type === 'image').length;
            const textCount = ads.filter(a => a.ad_type === 'text').length;
            stats.textContent = `${ads.length} ad${ads.length !== 1 ? 's' : ''} (${imageCount} image, ${textCount} text) • ${activeCount} active • Drag to reorder`;
        }
    } catch (error) {
        grid.innerHTML = `<div class="ad-error-state">Failed to load advertisements: ${error.message}</div>`;
        showNotification(`Failed to load advertisements: ${error.message}`, 'error');
    } finally {
        if (loading) loading.classList.add('hidden');
    }
}

/**
 * Render an advertisement card (image or text)
 * Includes draggable attribute for drag-and-drop reordering
 */
function renderAdCard(ad, index) {
    const isImage = ad.ad_type === 'image';
    const typeBadge = `<span class="ad-type-badge">${isImage ? 'IMG' : 'TXT'}</span>`;
    const orderBadge = `<span class="ad-order-badge">${index + 1}</span>`;

    if (isImage) {
        return `
            <div class="ad-card" data-id="${ad.id}" draggable="true">
                ${typeBadge}
                ${orderBadge}
                <img src="${ad.url}" alt="${ad.original_name}" loading="lazy">
                <div class="ad-card-overlay">
                    <span class="ad-card-name">${ad.original_name}</span>
                    <span class="ad-card-size">${formatFileSize(ad.file_size)}</span>
                </div>
                <div class="ad-card-actions">
                    <button class="ad-delete-btn" onclick="deleteAdvertisement('${ad.id}')" title="Delete">
                        &#10005;
                    </button>
                </div>
                <div class="ad-drag-handle" title="Drag to reorder">&#9776;</div>
            </div>
        `;
    } else {
        // Text advertisement
        const truncatedText = ad.content.length > 100 ? ad.content.substring(0, 100) + '...' : ad.content;
        return `
            <div class="ad-card text-ad" data-id="${ad.id}" draggable="true">
                ${typeBadge}
                ${orderBadge}
                <div class="ad-text-content">${escapeHtml(truncatedText)}</div>
                <div class="ad-card-overlay">
                    <span class="ad-card-name">Text Ad</span>
                    <span class="ad-card-size">${ad.content.length} chars</span>
                </div>
                <div class="ad-card-actions">
                    <button class="ad-delete-btn" onclick="deleteAdvertisement('${ad.id}')" title="Delete">
                        &#10005;
                    </button>
                </div>
                <div class="ad-drag-handle" title="Drag to reorder">&#9776;</div>
            </div>
        `;
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
 * Format file size for display
 */
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/**
 * Upload a new advertisement image
 */
async function uploadAdvertisement(file) {
    const statusEl = document.getElementById('adUploadStatus');

    // Validate file type
    const validTypes = ['image/jpeg', 'image/png'];
    if (!validTypes.includes(file.type)) {
        showNotification('Invalid file type. Please upload JPG, JPEG, or PNG.', 'error');
        return;
    }

    // Validate file size (5MB max)
    const maxSize = 5 * 1024 * 1024;
    if (file.size > maxSize) {
        showNotification('File too large. Maximum size is 5MB.', 'error');
        return;
    }

    // Show uploading status
    if (statusEl) {
        statusEl.textContent = `Uploading ${file.name}...`;
        statusEl.className = 'upload-status uploading';
    }

    try {
        const formData = new FormData();
        formData.append('file', file);

        const data = await apiCall('/admin/advertisements/upload', {
            method: 'POST',
            body: formData
        });

        showNotification(`Advertisement "${file.name}" uploaded successfully`, 'success');

        // Clear status
        if (statusEl) {
            statusEl.textContent = '';
            statusEl.className = 'upload-status';
        }

        // Reload the grid
        loadAdvertisements();
    } catch (error) {
        showNotification(`Upload failed: ${error.message}`, 'error');
        if (statusEl) {
            statusEl.textContent = `Failed: ${error.message}`;
            statusEl.className = 'upload-status error';
        }
    }
}

/**
 * Delete an advertisement
 */
async function deleteAdvertisement(adId) {
    if (!confirm('Are you sure you want to delete this advertisement?')) {
        return;
    }

    try {
        await apiCall(`/admin/advertisements/${adId}`, {
            method: 'DELETE'
        });

        showNotification('Advertisement deleted successfully', 'success');
        loadAdvertisements();
    } catch (error) {
        showNotification(`Delete failed: ${error.message}`, 'error');
    }
}

// Make deleteAdvertisement available globally for onclick handlers
window.deleteAdvertisement = deleteAdvertisement;

// ==============================================================================
// ADVERTISEMENT DRAG-AND-DROP REORDERING
// ==============================================================================

// Track drag state
let draggedAdCard = null;
let draggedAdId = null;

/**
 * Set up drag-and-drop event handlers for advertisement cards
 */
function setupAdDragAndDrop(grid) {
    const cards = grid.querySelectorAll('.ad-card[draggable="true"]');

    cards.forEach(card => {
        // Drag start
        card.addEventListener('dragstart', handleAdDragStart);
        card.addEventListener('dragend', handleAdDragEnd);

        // Drop targets
        card.addEventListener('dragover', handleAdDragOver);
        card.addEventListener('dragenter', handleAdDragEnter);
        card.addEventListener('dragleave', handleAdDragLeave);
        card.addEventListener('drop', handleAdDrop);
    });
}

/**
 * Handle drag start event
 */
function handleAdDragStart(e) {
    draggedAdCard = this;
    draggedAdId = this.dataset.id;

    // Set drag data
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', draggedAdId);

    // Add visual feedback
    setTimeout(() => {
        this.classList.add('dragging');
    }, 0);
}

/**
 * Handle drag end event
 */
function handleAdDragEnd(e) {
    this.classList.remove('dragging');

    // Remove all drag-over states
    document.querySelectorAll('.ad-card.drag-over').forEach(card => {
        card.classList.remove('drag-over');
    });

    draggedAdCard = null;
    draggedAdId = null;
}

/**
 * Handle drag over event (allow drop)
 */
function handleAdDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
}

/**
 * Handle drag enter event (visual feedback)
 */
function handleAdDragEnter(e) {
    e.preventDefault();
    if (this !== draggedAdCard) {
        this.classList.add('drag-over');
    }
}

/**
 * Handle drag leave event (remove visual feedback)
 */
function handleAdDragLeave(e) {
    // Only remove if actually leaving the card (not entering a child element)
    if (!this.contains(e.relatedTarget)) {
        this.classList.remove('drag-over');
    }
}

/**
 * Handle drop event (reorder)
 */
function handleAdDrop(e) {
    e.preventDefault();
    e.stopPropagation();

    this.classList.remove('drag-over');

    if (this === draggedAdCard) return;

    const grid = document.getElementById('adGrid');
    const cards = Array.from(grid.querySelectorAll('.ad-card'));
    const fromIndex = cards.indexOf(draggedAdCard);
    const toIndex = cards.indexOf(this);

    if (fromIndex === -1 || toIndex === -1) return;

    // Reorder in DOM
    if (fromIndex < toIndex) {
        this.parentNode.insertBefore(draggedAdCard, this.nextSibling);
    } else {
        this.parentNode.insertBefore(draggedAdCard, this);
    }

    // Update order badges
    updateOrderBadges();

    // Save new order to backend
    saveAdOrder();
}

/**
 * Update order badges after reordering
 */
function updateOrderBadges() {
    const grid = document.getElementById('adGrid');
    const cards = grid.querySelectorAll('.ad-card');

    cards.forEach((card, index) => {
        const badge = card.querySelector('.ad-order-badge');
        if (badge) {
            badge.textContent = index + 1;
        }
    });
}

/**
 * Save the current advertisement order to the backend
 */
async function saveAdOrder() {
    const grid = document.getElementById('adGrid');
    const cards = grid.querySelectorAll('.ad-card');
    const adIds = Array.from(cards).map(card => card.dataset.id);

    try {
        await apiCall('/admin/advertisements/reorder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ad_ids: adIds })
        });

        showNotification('Advertisement order saved', 'success');
    } catch (error) {
        showNotification(`Failed to save order: ${error.message}`, 'error');
        // Reload to restore correct order
        loadAdvertisements();
    }
}

// ==============================================================================
// PHASE 54: TEXT ADVERTISEMENT MANAGEMENT
// ==============================================================================

/**
 * Create a new text advertisement
 */
async function createTextAdvertisement(content) {
    const statusEl = document.getElementById('textAdStatus');

    if (!content || !content.trim()) {
        showNotification('Please enter advertisement text', 'error');
        return false;
    }

    content = content.trim();
    if (content.length > 2000) {
        showNotification('Text too long. Maximum 2000 characters allowed.', 'error');
        return false;
    }

    // Show status
    if (statusEl) {
        statusEl.textContent = 'Publishing text advertisement...';
        statusEl.className = 'upload-status uploading';
    }

    try {
        await apiCall('/admin/advertisements/text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        });

        showNotification('Text advertisement published successfully', 'success');

        // Clear the form
        const textInput = document.getElementById('textAdInput');
        if (textInput) textInput.value = '';
        updateTextAdCharCount();

        // Clear status
        if (statusEl) {
            statusEl.textContent = '';
            statusEl.className = 'upload-status';
        }

        // Reload the grid
        loadAdvertisements();
        return true;
    } catch (error) {
        showNotification(`Failed to publish: ${error.message}`, 'error');
        if (statusEl) {
            statusEl.textContent = `Failed: ${error.message}`;
            statusEl.className = 'upload-status error';
        }
        return false;
    }
}

/**
 * Enhance text advertisement using AI
 */
async function enhanceTextAdvertisement(content) {
    const statusEl = document.getElementById('textAdStatus');
    const previewEl = document.getElementById('enhancementPreview');
    const enhancedTextEl = document.getElementById('enhancedText');
    const enhanceBtn = document.getElementById('enhanceTextBtn');

    if (!content || !content.trim()) {
        showNotification('Please enter text to enhance', 'error');
        return;
    }

    // Disable button during enhancement
    if (enhanceBtn) {
        enhanceBtn.disabled = true;
        enhanceBtn.innerHTML = '<span class="btn-icon">⏳</span> Enhancing...';
    }

    if (statusEl) {
        statusEl.textContent = 'AI is enhancing your text...';
        statusEl.className = 'upload-status uploading';
    }

    try {
        const response = await apiCall('/admin/advertisements/enhance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content.trim() })
        });

        // Show the enhanced text preview
        // Store raw text in data attribute for later use, display formatted HTML
        if (enhancedTextEl) {
            enhancedTextEl.dataset.rawText = response.enhanced;
            enhancedTextEl.innerHTML = formatAdText(response.enhanced);
        }
        if (previewEl) {
            previewEl.classList.remove('hidden');
        }

        if (statusEl) {
            statusEl.textContent = '';
            statusEl.className = 'upload-status';
        }
    } catch (error) {
        showNotification(`AI enhancement failed: ${error.message}`, 'error');
        if (statusEl) {
            statusEl.textContent = `Enhancement failed: ${error.message}`;
            statusEl.className = 'upload-status error';
        }
    } finally {
        if (enhanceBtn) {
            enhanceBtn.disabled = false;
            enhanceBtn.innerHTML = '<span class="btn-icon">✨</span> Enhance with AI';
        }
    }
}

/**
 * Use the enhanced text (copy back to input for editing)
 * Uses raw text from data attribute to preserve original formatting
 */
function useEnhancedText() {
    const enhancedTextEl = document.getElementById('enhancedText');
    const textInput = document.getElementById('textAdInput');
    const previewEl = document.getElementById('enhancementPreview');

    if (enhancedTextEl && textInput) {
        // Use raw text from data attribute (preserves newlines)
        textInput.value = enhancedTextEl.dataset.rawText || enhancedTextEl.textContent;
        updateTextAdCharCount();
    }

    if (previewEl) {
        previewEl.classList.add('hidden');
    }
}

/**
 * Publish the enhanced text directly
 * Uses raw text from data attribute to preserve original formatting
 */
async function publishEnhancedText() {
    const enhancedTextEl = document.getElementById('enhancedText');
    const previewEl = document.getElementById('enhancementPreview');

    if (enhancedTextEl) {
        // Use raw text from data attribute (preserves newlines)
        const content = enhancedTextEl.dataset.rawText || enhancedTextEl.textContent;
        const success = await createTextAdvertisement(content);
        if (success && previewEl) {
            previewEl.classList.add('hidden');
        }
    }
}

/**
 * Cancel the enhancement preview
 */
function cancelEnhancement() {
    const previewEl = document.getElementById('enhancementPreview');
    if (previewEl) {
        previewEl.classList.add('hidden');
    }
}

/**
 * Update the character count for text ad input
 */
function updateTextAdCharCount() {
    const textInput = document.getElementById('textAdInput');
    const charCount = document.getElementById('textAdCharCount');
    if (textInput && charCount) {
        charCount.textContent = textInput.value.length;
    }
}

/**
 * Switch between image, text, and trivia ad tabs
 */
function switchAdTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.ad-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });

    // Update tab content
    document.querySelectorAll('.ad-tab-content').forEach(content => {
        content.classList.remove('active');
    });

    // Handle tab name mapping (trivia tab uses 'triviaTab' id)
    const tabIdMap = {
        'image': 'imageAdTab',
        'text': 'textAdTab',
        'trivia': 'triviaTab'
    };

    const targetTabId = tabIdMap[tabName] || (tabName + 'AdTab');
    const targetTab = document.getElementById(targetTabId);
    if (targetTab) {
        targetTab.classList.add('active');
    }

    // Phase 56B: Hide ad grid and stats when trivia tab is active
    const adGrid = document.getElementById('adGrid');
    const adsStats = document.getElementById('adsStats');
    const isTriviaTab = tabName === 'trivia';

    if (adGrid) {
        adGrid.style.display = isTriviaTab ? 'none' : '';
    }
    if (adsStats) {
        adsStats.style.display = isTriviaTab ? 'none' : '';
    }

    // Load trivia content when trivia tab is selected
    if (isTriviaTab) {
        loadTriviaContent();
    }
}

// ==============================================================================
// PHASE 56: TRIVIA & QUOTES MANAGEMENT
// ==============================================================================

/**
 * Load trivia content for admin viewing
 */
async function loadTriviaContent() {
    try {
        const data = await apiCall('/admin/trivia/content');

        // Update status card
        updateTriviaStatus(data.status);

        // Render trivia list
        renderTriviaList(data.trivia, 'triviaList', 'triviaCount', 'Day');

        // Render study tips list
        renderTriviaList(data.study_tips, 'tipsList', 'tipsCount', 'Day');

        // Render quotes list
        renderQuotesList(data.quotes);

    } catch (error) {
        console.error('[ADMIN] Failed to load trivia content:', error);
        showNotification(`Failed to load trivia content: ${error.message}`, 'error');
    }
}

/**
 * Update trivia status display
 */
function updateTriviaStatus(status) {
    const genStatus = document.getElementById('triviaGenStatus');
    const month = document.getElementById('triviaMonth');
    const genDate = document.getElementById('triviaGenDate');

    if (genStatus) {
        genStatus.textContent = status.generated ? 'Generated' : 'Not Generated';
    }

    if (month && status.month && status.year) {
        const monthNames = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December'];
        month.textContent = `${monthNames[status.month]} ${status.year}`;
    } else if (month) {
        month.textContent = '--';
    }

    if (genDate && status.generated_at) {
        genDate.textContent = new Date(status.generated_at).toLocaleString();
    } else if (genDate) {
        genDate.textContent = '--';
    }
}

/**
 * Render trivia or study tips list
 */
function renderTriviaList(items, listId, countId, labelPrefix) {
    const list = document.getElementById(listId);
    const count = document.getElementById(countId);

    if (!list) return;

    const itemsArray = Object.entries(items || {});

    if (count) {
        count.textContent = `(${itemsArray.length})`;
    }

    if (itemsArray.length === 0) {
        list.innerHTML = '<div class="trivia-empty">No content generated yet</div>';
        return;
    }

    // Sort by day number
    itemsArray.sort((a, b) => parseInt(a[0]) - parseInt(b[0]));

    list.innerHTML = itemsArray.map(([day, content]) => `
        <div class="trivia-item">
            <div class="day-label">${labelPrefix} ${day}</div>
            <div class="item-content">${escapeHtml(content)}</div>
        </div>
    `).join('');
}

/**
 * Render quotes list
 */
function renderQuotesList(quotes) {
    const list = document.getElementById('quotesList');
    const count = document.getElementById('quotesCount');

    if (!list) return;

    const quotesArray = quotes || [];

    if (count) {
        count.textContent = `(${quotesArray.length})`;
    }

    if (quotesArray.length === 0) {
        list.innerHTML = '<div class="trivia-empty">No quotes generated yet</div>';
        return;
    }

    list.innerHTML = quotesArray.map((quote, index) => `
        <div class="trivia-item quote-item">
            <div class="quote-number">Quote #${index + 1}</div>
            <div class="item-content">${escapeHtml(quote)}</div>
        </div>
    `).join('');
}

/**
 * Regenerate trivia content (admin action)
 */
async function regenerateTriviaContent() {
    if (!confirm('This will regenerate all trivia, study tips, and quotes for the current month. Continue?')) {
        return;
    }

    const btn = document.getElementById('regenerateTriviaBtn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Generating...';
    }

    try {
        await apiCall('/admin/trivia/regenerate', {
            method: 'POST'
        });

        showNotification('Trivia content regenerated successfully', 'success');
        loadTriviaContent();

    } catch (error) {
        console.error('[ADMIN] Failed to regenerate trivia:', error);
        showNotification(`Failed to regenerate trivia: ${error.message}`, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '↻ Regenerate';
        }
    }
}

// ==============================================================================
// PHASE 49: WELCOME MESSAGE MANAGEMENT
// ==============================================================================

/**
 * Load welcome message for admin editing
 */
async function loadWelcomeMessageAdmin() {
    const loadingIndicator = document.getElementById('welcomeLoadingIndicator');
    const textarea = document.getElementById('welcomeMessageInput');
    const lastUpdated = document.getElementById('welcomeLastUpdated');

    if (loadingIndicator) loadingIndicator.classList.remove('hidden');

    try {
        const data = await apiCall('/admin/welcome');
        if (textarea) {
            textarea.value = data.message || '';
        }
        if (lastUpdated) {
            lastUpdated.textContent = data.updated_at
                ? `Last updated: ${new Date(data.updated_at).toLocaleString()}`
                : '';
        }
        updateWelcomePreview();
    } catch (error) {
        showNotification(`Failed to load welcome message: ${error.message}`, 'error');
    } finally {
        if (loadingIndicator) loadingIndicator.classList.add('hidden');
    }
}

/**
 * Save welcome message
 */
async function saveWelcomeMessage() {
    const textarea = document.getElementById('welcomeMessageInput');
    const saveBtn = document.getElementById('saveWelcomeBtn');
    const message = textarea ? textarea.value.trim() : '';

    if (!message) {
        showNotification('Please enter a welcome message', 'error');
        return;
    }

    if (saveBtn) {
        saveBtn.textContent = 'Saving...';
        saveBtn.disabled = true;
    }

    try {
        await apiCall('/admin/welcome', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });
        showNotification('Welcome message saved successfully', 'success');
        await loadWelcomeMessageAdmin();
    } catch (error) {
        showNotification(`Save failed: ${error.message}`, 'error');
    } finally {
        if (saveBtn) {
            saveBtn.textContent = 'Save Changes';
            saveBtn.disabled = false;
        }
    }
}

/**
 * Update welcome message preview in real-time
 */
function updateWelcomePreview() {
    const textarea = document.getElementById('welcomeMessageInput');
    const previewText = document.getElementById('welcomePreviewText');

    if (textarea && previewText) {
        previewText.innerHTML = formatWelcomeTextAdmin(textarea.value);
    }
}

/**
 * Format welcome message text to HTML for preview
 */
function formatWelcomeTextAdmin(text) {
    if (!text) return '<p class="preview-placeholder">Enter a welcome message above to see preview</p>';

    const lines = text.split('\n');
    let html = '';
    let inList = false;

    for (const line of lines) {
        const trimmed = line.trim();

        if (trimmed.startsWith('- ')) {
            if (!inList) {
                html += '<ul class="examples-list">';
                inList = true;
            }
            html += `<li>${escapeHtmlAdmin(trimmed.substring(2))}</li>`;
        } else {
            if (inList) {
                html += '</ul>';
                inList = false;
            }
            if (trimmed) {
                html += `<p class="large-text">${escapeHtmlAdmin(trimmed)}</p>`;
            }
        }
    }

    if (inList) html += '</ul>';
    return html;
}

/**
 * Escape HTML characters for safe display
 */
function escapeHtmlAdmin(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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

        return `
        <div class="result-item ${r.passed ? 'passed' : 'failed'}">
            <div class="result-header">
                <span class="result-number">Q${index + 1}</span>
                <span class="result-status ${r.passed ? 'pass' : 'fail'}">${r.passed ? 'PASS' : 'FAIL'}</span>
            </div>
            <div class="result-question">${escapeHtml(r.query)}</div>
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

    const resultHtml = `
        <div class="result-item ${result.passed ? 'passed' : 'failed'}">
            <div class="result-header">
                <span class="result-number">Q${index + 1}</span>
                <span class="result-status ${result.passed ? 'pass' : 'fail'}">${result.passed ? 'PASS' : 'FAIL'}</span>
            </div>
            <div class="result-question">${escapeHtml(result.query)}</div>
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

    // RAG Package Upload
    const ragFileInput = document.getElementById('ragFileInput');
    const ragUploadBtn = document.getElementById('ragUploadBtn');
    const ragUploadArea = document.getElementById('ragUploadArea');

    if (ragFileInput && ragUploadBtn) {
        ragFileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                document.getElementById('ragFileName').textContent = file.name;
                ragUploadBtn.disabled = false;
            } else {
                document.getElementById('ragFileName').textContent = 'Choose a .zip file or drag & drop';
                ragUploadBtn.disabled = true;
            }
        });

        ragUploadBtn.addEventListener('click', () => {
            const file = ragFileInput.files[0];
            if (file) {
                uploadRAGPackage(file);
            }
        });

        // Drag and drop support
        if (ragUploadArea) {
            ragUploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                ragUploadArea.classList.add('dragover');
            });

            ragUploadArea.addEventListener('dragleave', () => {
                ragUploadArea.classList.remove('dragover');
            });

            ragUploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                ragUploadArea.classList.remove('dragover');
                if (e.dataTransfer.files.length) {
                    const file = e.dataTransfer.files[0];
                    document.getElementById('ragFileName').textContent = file.name;
                    ragUploadBtn.disabled = false;
                    ragFileInput.files = e.dataTransfer.files;
                }
            });
        }
    }

    // Refresh Button
    document.getElementById('refreshBtn').addEventListener('click', loadDocuments);

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
    // METADATA VISIBILITY EVENT LISTENERS - Phase 50
    // ==============================================================================

    const metadataVisibleToggle = document.getElementById('metadataVisibleToggle');
    if (metadataVisibleToggle) {
        metadataVisibleToggle.addEventListener('change', (e) => {
            toggleMetadataVisibility(e.target.checked);
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
    // ADVERTISEMENT MANAGEMENT EVENT LISTENERS (Phase 48/54)
    // ==============================================================================

    // Refresh Advertisements Button
    const refreshAdsBtn = document.getElementById('refreshAdsBtn');
    if (refreshAdsBtn) {
        refreshAdsBtn.addEventListener('click', loadAdvertisements);
    }

    // Advertisement File Input
    const adFileInput = document.getElementById('adFileInput');
    if (adFileInput) {
        adFileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                uploadAdvertisement(file);
                e.target.value = ''; // Reset for next upload
            }
        });
    }

    // Advertisement Upload Area - Drag and Drop
    const adUploadLabel = document.querySelector('.ad-upload-label');
    if (adUploadLabel) {
        adUploadLabel.addEventListener('dragover', (e) => {
            e.preventDefault();
            adUploadLabel.classList.add('dragover');
        });
        adUploadLabel.addEventListener('dragleave', (e) => {
            e.preventDefault();
            adUploadLabel.classList.remove('dragover');
        });
        adUploadLabel.addEventListener('drop', (e) => {
            e.preventDefault();
            adUploadLabel.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file) {
                uploadAdvertisement(file);
            }
        });
    }

    // Phase 54: Text Advertisement Tab Switching
    document.querySelectorAll('.ad-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            if (tabName) {
                switchAdTab(tabName);
            }
        });
    });

    // Phase 56: Trivia Regenerate Button
    const regenerateTriviaBtn = document.getElementById('regenerateTriviaBtn');
    if (regenerateTriviaBtn) {
        regenerateTriviaBtn.addEventListener('click', regenerateTriviaContent);
    }

    // Phase 54: Text Ad Input - Character Count
    const textAdInput = document.getElementById('textAdInput');
    if (textAdInput) {
        textAdInput.addEventListener('input', updateTextAdCharCount);
    }

    // Phase 54: Enhance with AI Button
    const enhanceTextBtn = document.getElementById('enhanceTextBtn');
    if (enhanceTextBtn) {
        enhanceTextBtn.addEventListener('click', () => {
            const textInput = document.getElementById('textAdInput');
            if (textInput) {
                enhanceTextAdvertisement(textInput.value);
            }
        });
    }

    // Phase 54: Publish Text Ad Button
    const publishTextAdBtn = document.getElementById('publishTextAdBtn');
    if (publishTextAdBtn) {
        publishTextAdBtn.addEventListener('click', () => {
            const textInput = document.getElementById('textAdInput');
            if (textInput) {
                createTextAdvertisement(textInput.value);
            }
        });
    }

    // Phase 54: Use Enhanced Text Button (copy to input for editing)
    const useEnhancedBtn = document.getElementById('useEnhancedBtn');
    if (useEnhancedBtn) {
        useEnhancedBtn.addEventListener('click', useEnhancedText);
    }

    // Phase 54: Publish Enhanced Text Button
    const publishEnhancedBtn = document.getElementById('publishEnhancedBtn');
    if (publishEnhancedBtn) {
        publishEnhancedBtn.addEventListener('click', publishEnhancedText);
    }

    // Phase 54: Cancel Enhancement Button
    const cancelEnhancementBtn = document.getElementById('cancelEnhancementBtn');
    if (cancelEnhancementBtn) {
        cancelEnhancementBtn.addEventListener('click', cancelEnhancement);
    }

    // ==============================================================================
    // WELCOME MESSAGE EVENT LISTENERS (Phase 49)
    // ==============================================================================

    // Save Welcome Message Button
    const saveWelcomeBtn = document.getElementById('saveWelcomeBtn');
    if (saveWelcomeBtn) {
        saveWelcomeBtn.addEventListener('click', saveWelcomeMessage);
    }

    // Refresh Welcome Message Button
    const refreshWelcomeBtn = document.getElementById('refreshWelcomeBtn');
    if (refreshWelcomeBtn) {
        refreshWelcomeBtn.addEventListener('click', loadWelcomeMessageAdmin);
    }

    // Welcome Message Input - Live Preview
    const welcomeMessageInput = document.getElementById('welcomeMessageInput');
    if (welcomeMessageInput) {
        welcomeMessageInput.addEventListener('input', updateWelcomePreview);
    }

    // ==============================================================================
    // INITIALIZATION - Phase 36: Section-based navigation
    // ==============================================================================

    // Check authentication first
    checkAuth().then(isAuthenticated => {
        if (isAuthenticated) {
            // Initialize section navigation (will load initial section data)
            initSectionNavigation();
            // Check if Developer section should be visible in sidebar
            checkDevSectionVisibility();
        }
    });
});

// Make deleteDocument available globally for onclick handlers
window.deleteDocument = deleteDocument;

// ============================================================================
// FAQ ADMIN SECTION
// ============================================================================

let faqAdminData = [];
let faqAdminConfig = {};
let editingFaqId = null;

/**
 * Load FAQs for admin management
 */
async function loadFAQsAdmin() {
    const loadingIndicator = document.getElementById('faqLoadingIndicator');
    const faqList = document.getElementById('faqList');
    const emptyState = document.getElementById('faqEmptyState');
    const countBadge = document.getElementById('faqCount');

    if (loadingIndicator) loadingIndicator.classList.remove('hidden');

    try {
        const response = await fetch('/admin/faqs', {
            credentials: 'include'
        });

        if (!response.ok) throw new Error('Failed to load FAQs');

        const data = await response.json();
        faqAdminData = data.faqs || [];
        faqAdminConfig = data.config || {};

        renderFAQsAdmin();

        // Update count badge
        if (countBadge) {
            countBadge.textContent = `${faqAdminConfig.current_count || 0} / ${faqAdminConfig.max_count || 20}`;
        }
    } catch (error) {
        console.error('[FAQ Admin] Error loading FAQs:', error);
        showNotification('Failed to load FAQs', 'error');
    } finally {
        if (loadingIndicator) loadingIndicator.classList.add('hidden');
    }
}

/**
 * Render FAQ items in admin list
 */
function renderFAQsAdmin() {
    const faqList = document.getElementById('faqList');
    const emptyState = document.getElementById('faqEmptyState');

    if (!faqList) return;

    if (faqAdminData.length === 0) {
        faqList.innerHTML = '';
        if (emptyState) emptyState.classList.remove('hidden');
        return;
    }

    if (emptyState) emptyState.classList.add('hidden');

    faqList.innerHTML = faqAdminData.map(faq => `
        <div class="faq-admin-item" data-faq-id="${faq.id}" draggable="true">
            <span class="faq-drag-handle" title="Drag to reorder">&#9776;</span>
            <div class="faq-admin-content">
                <div class="faq-admin-question">${escapeHtmlAdmin(faq.question)}</div>
                <div class="faq-admin-answer">${escapeHtmlAdmin(faq.answer)}</div>
            </div>
            <div class="faq-admin-actions">
                <button class="faq-edit-btn" onclick="editFaq('${faq.id}')">Edit</button>
                <button class="faq-delete-btn" onclick="deleteFaq('${faq.id}')">Delete</button>
            </div>
        </div>
    `).join('');

    // Set up drag-and-drop
    setupFaqDragDrop();
}

/**
 * Set up drag-and-drop for FAQ reordering
 */
function setupFaqDragDrop() {
    const items = document.querySelectorAll('.faq-admin-item');
    let draggedItem = null;

    items.forEach(item => {
        item.addEventListener('dragstart', (e) => {
            draggedItem = item;
            item.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
        });

        item.addEventListener('dragend', () => {
            item.classList.remove('dragging');
            draggedItem = null;

            // Remove drag-over class from all items
            items.forEach(i => i.classList.remove('drag-over'));

            // Save new order
            saveFaqOrder();
        });

        item.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (draggedItem && draggedItem !== item) {
                item.classList.add('drag-over');
            }
        });

        item.addEventListener('dragleave', () => {
            item.classList.remove('drag-over');
        });

        item.addEventListener('drop', (e) => {
            e.preventDefault();
            item.classList.remove('drag-over');

            if (draggedItem && draggedItem !== item) {
                const faqList = document.getElementById('faqList');
                const allItems = Array.from(faqList.querySelectorAll('.faq-admin-item'));
                const draggedIndex = allItems.indexOf(draggedItem);
                const dropIndex = allItems.indexOf(item);

                if (draggedIndex < dropIndex) {
                    item.parentNode.insertBefore(draggedItem, item.nextSibling);
                } else {
                    item.parentNode.insertBefore(draggedItem, item);
                }
            }
        });
    });
}

/**
 * Save FAQ order after drag-and-drop
 */
async function saveFaqOrder() {
    const faqList = document.getElementById('faqList');
    if (!faqList) return;

    const items = faqList.querySelectorAll('.faq-admin-item');
    const orderedIds = Array.from(items).map(item => item.dataset.faqId);

    try {
        const response = await fetch('/admin/faqs/reorder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ ordered_ids: orderedIds })
        });

        if (!response.ok) throw new Error('Failed to save order');

        const data = await response.json();
        faqAdminData = data.faqs || [];

        showNotification('FAQ order saved', 'success');
    } catch (error) {
        console.error('[FAQ Admin] Error saving order:', error);
        showNotification('Failed to save order', 'error');
        // Reload to restore original order
        loadFAQsAdmin();
    }
}

/**
 * Open FAQ modal for adding
 */
function openAddFaqModal() {
    editingFaqId = null;
    document.getElementById('faqModalTitle').textContent = 'Add FAQ';
    document.getElementById('faqEditId').value = '';
    document.getElementById('faqQuestionInput').value = '';
    document.getElementById('faqAnswerInput').value = '';
    hideGeneratedPreview();
    document.getElementById('faqModal').classList.remove('hidden');
}

/**
 * Open FAQ modal for editing
 */
function editFaq(faqId) {
    const faq = faqAdminData.find(f => f.id === faqId);
    if (!faq) return;

    editingFaqId = faqId;
    document.getElementById('faqModalTitle').textContent = 'Edit FAQ';
    document.getElementById('faqEditId').value = faqId;
    document.getElementById('faqQuestionInput').value = faq.question;
    document.getElementById('faqAnswerInput').value = faq.answer;
    hideGeneratedPreview();
    document.getElementById('faqModal').classList.remove('hidden');
}

/**
 * Close FAQ modal
 */
function closeFaqModal() {
    document.getElementById('faqModal').classList.add('hidden');
    editingFaqId = null;
}

/**
 * Save FAQ (create or update)
 */
async function saveFaq() {
    const question = document.getElementById('faqQuestionInput').value.trim();
    const answer = document.getElementById('faqAnswerInput').value.trim();

    if (!question) {
        showNotification('Question is required', 'error');
        return;
    }
    if (!answer) {
        showNotification('Answer is required', 'error');
        return;
    }

    const saveBtn = document.getElementById('saveFaqBtn');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    try {
        const url = editingFaqId ? `/admin/faqs/${editingFaqId}` : '/admin/faqs';
        const method = editingFaqId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ question, answer })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to save FAQ');
        }

        showNotification(editingFaqId ? 'FAQ updated' : 'FAQ created', 'success');
        closeFaqModal();
        loadFAQsAdmin();
    } catch (error) {
        console.error('[FAQ Admin] Error saving FAQ:', error);
        showNotification(error.message || 'Failed to save FAQ', 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save FAQ';
    }
}

/**
 * Delete FAQ
 */
async function deleteFaq(faqId) {
    if (!confirm('Are you sure you want to delete this FAQ?')) return;

    try {
        const response = await fetch(`/admin/faqs/${faqId}`, {
            method: 'DELETE',
            credentials: 'include'
        });

        if (!response.ok) throw new Error('Failed to delete FAQ');

        showNotification('FAQ deleted', 'success');
        loadFAQsAdmin();
    } catch (error) {
        console.error('[FAQ Admin] Error deleting FAQ:', error);
        showNotification('Failed to delete FAQ', 'error');
    }
}

/**
 * Ask CoCo for a suggested answer
 */
async function askCocoForAnswer() {
    const question = document.getElementById('faqQuestionInput').value.trim();

    if (!question) {
        showNotification('Please enter a question first', 'error');
        return;
    }

    const askBtn = document.getElementById('askCocoBtn');
    const statusText = document.getElementById('askCocoStatus');

    askBtn.disabled = true;
    statusText.textContent = 'Generating...';

    try {
        const response = await fetch('/admin/faqs/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ question })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate answer');
        }

        const data = await response.json();

        // Show generated answer preview
        showGeneratedPreview(data.generated_answer, data.confidence);
        statusText.textContent = '';
    } catch (error) {
        console.error('[FAQ Admin] Error generating answer:', error);
        statusText.textContent = 'Failed to generate';
        showNotification(error.message || 'Failed to generate answer', 'error');
    } finally {
        askBtn.disabled = false;
    }
}

/**
 * Show generated answer preview
 */
function showGeneratedPreview(answer, confidence) {
    const preview = document.getElementById('generatedAnswerPreview');
    const answerText = document.getElementById('generatedAnswerText');
    const confidenceBadge = document.getElementById('generatedConfidence');

    if (!preview || !answerText) return;

    answerText.textContent = answer;

    if (confidenceBadge) {
        confidenceBadge.textContent = confidence;
        confidenceBadge.className = 'confidence-badge ' + (confidence || 'medium').toLowerCase();
    }

    preview.classList.remove('hidden');
}

/**
 * Hide generated answer preview
 */
function hideGeneratedPreview() {
    const preview = document.getElementById('generatedAnswerPreview');
    if (preview) preview.classList.add('hidden');
}

/**
 * Use the generated answer
 */
function useGeneratedAnswer() {
    const answerText = document.getElementById('generatedAnswerText');
    const answerInput = document.getElementById('faqAnswerInput');

    if (answerText && answerInput) {
        answerInput.value = answerText.textContent;
    }

    hideGeneratedPreview();
}

/**
 * Escape HTML for admin display
 */
function escapeHtmlAdmin(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Make FAQ functions available globally
window.editFaq = editFaq;
window.deleteFaq = deleteFaq;
window.closeFaqModal = closeFaqModal;
window.saveFaq = saveFaq;
window.askCocoForAnswer = askCocoForAnswer;
window.useGeneratedAnswer = useGeneratedAnswer;
window.hideGeneratedPreview = hideGeneratedPreview;

// Add FAQ button event listener on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    const addFaqBtn = document.getElementById('addFaqBtn');
    if (addFaqBtn) {
        addFaqBtn.addEventListener('click', openAddFaqModal);
    }
});

// =============================================================================
// CONVERSATION VIEWER
// =============================================================================

const ConversationViewer = (function () {
    'use strict';

    // State
    let currentPage  = 1;
    let totalPages   = 1;
    let totalCount   = 0;
    const PER_PAGE   = 20;
    let searchDebounceTimer = null;
    let initialized  = false;

    // ── DOM refs (resolved once on init) ─────────────────────────────────────
    let tableBody, emptyState, metaEl, pageInfo,
        prevBtn, nextBtn, loadingEl,
        monthInput, searchInput, feedbackFilter, clearBtn, refreshBtn;

    function escAdm(str) {
        if (!str) return '';
        return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    function formatTs(iso) {
        if (!iso) return '\u2014';
        try {
            const d = new Date(iso);
            return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
        } catch { return iso; }
    }

    // ── Format answer text (mirrors app.js formatAnswerText) ────────────────
    function formatAnswerHtml(text) {
        if (!text) return '';

        // HTML-escape first
        let html = escAdm(text);

        // **bold** → <strong>
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Numbered lists: "1. item" → <li value="1">item</li>
        html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<li value="$1">$2</li>');

        // Bullet lists: "- item" or "* item" → <li>item</li>
        html = html.replace(/^[-*]\s+(.+)$/gm, '<li>$1</li>');

        // Wrap consecutive <li> in <ol> or <ul>
        html = html.replace(/((?:<li[^>]*>.*<\/li>\s*)+)/g, function (match) {
            if (match.includes('value="')) {
                return '<ol class="conv-answer-list">' + match + '</ol>';
            }
            return '<ul class="conv-answer-list">' + match + '</ul>';
        });

        // Double newlines → paragraph breaks
        html = html.replace(/\n\n+/g, '</p><p>');

        // Single newlines → <br> (but not before HTML tags)
        html = html.replace(/\n(?![<])/g, '<br>');

        // Wrap in <p> if not starting with list
        if (!html.startsWith('<ol') && !html.startsWith('<ul') && !html.startsWith('<p>')) {
            html = '<p>' + html + '</p>';
        }

        // Clean empty paragraphs
        html = html.replace(/<p>\s*<\/p>/g, '');

        return html;
    }

    // ── Render one table row ──────────────────────────────────────────────────
    function buildRow(c) {
        const rowId = 'crow-' + CSS.escape(c.query_id || Math.random());
        const ansHtml = formatAnswerHtml(c.answer || '');

        // Feedback icon
        let fbIcon  = '&mdash;';
        let fbClass = 'conv-fb-unrated';
        if (c.feedback === 'liked') {
            fbIcon  = '&#128077;';
            fbClass = 'conv-fb-liked';
        } else if (c.feedback === 'disliked') {
            fbIcon  = '&#128078;';
            fbClass = 'conv-fb-disliked';
        }

        return `
        <tr data-rowid="${rowId}">
            <td class="conv-td-time">${formatTs(c.timestamp)}</td>
            <td class="conv-td-query">${escAdm(c.query)}</td>
            <td class="conv-td-answer">
                <div class="conv-text-clamp" id="${rowId}-text">${ansHtml}</div>
                <button class="conv-expand-btn hidden" data-target="${rowId}-text">
                    Show more
                </button>
            </td>
            <td class="conv-td-feedback ${fbClass}">${fbIcon}</td>
        </tr>`;
    }

    // ── Post-render: show "Show more" only when content overflows ────────────
    function checkOverflow() {
        requestAnimationFrame(() => {
            const clamps = document.querySelectorAll('#convTableBody .conv-text-clamp');
            clamps.forEach(el => {
                const btn = el.nextElementSibling;
                if (!btn || !btn.classList.contains('conv-expand-btn')) return;
                if (el.scrollHeight > el.clientHeight + 1) {
                    btn.classList.remove('hidden');
                } else {
                    btn.classList.add('hidden');
                }
            });
        });
    }

    // ── Fetch & render ────────────────────────────────────────────────────────
    async function fetchPage(page) {
        setLoading(true);

        const params = new URLSearchParams({
            page,
            per_page: PER_PAGE,
        });

        const month  = monthInput  ? monthInput.value.trim()  : '';
        const search = searchInput ? searchInput.value.trim() : '';
        const fb     = feedbackFilter ? feedbackFilter.value.trim() : '';
        if (month)  params.set('month',    month);
        if (search) params.set('search',   search);
        if (fb)     params.set('feedback', fb);

        try {
            const res = await fetch(`/admin/analytics/conversations?${params}`, {
                credentials: 'include',
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            currentPage = data.page;
            totalPages  = data.total_pages;
            totalCount  = data.total;

            renderTable(data.conversations);
            renderPagination();
            renderMeta(data.total, data.page, data.total_pages, data.per_page);

        } catch (err) {
            console.error('[ConversationViewer] Fetch error:', err);
            if (tableBody) tableBody.innerHTML = '';
            showEmpty('Failed to load conversations. Check the console.');
        } finally {
            setLoading(false);
        }
    }

    function renderTable(rows) {
        if (!tableBody) return;
        if (!rows || rows.length === 0) {
            tableBody.innerHTML = '';
            showEmpty();
            return;
        }
        hideEmpty();
        tableBody.innerHTML = rows.map(buildRow).join('');
        checkOverflow();
    }

    function renderPagination() {
        if (pageInfo)  pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
        if (prevBtn)   prevBtn.disabled = currentPage <= 1;
        if (nextBtn)   nextBtn.disabled = currentPage >= totalPages;
    }

    function renderMeta(total, page, pages, perPage) {
        if (!metaEl) return;
        if (total === 0) {
            metaEl.textContent = 'No conversations found.';
            return;
        }
        const start = (page - 1) * perPage + 1;
        const end   = Math.min(page * perPage, total);
        metaEl.textContent = `Showing ${start}\u2013${end} of ${total} conversations`;
    }

    // ── UI helpers ─────────────────────────────────────────────────────────────
    function setLoading(on) {
        if (loadingEl) loadingEl.classList.toggle('hidden', !on);
    }

    function showEmpty(msg) {
        if (emptyState) {
            emptyState.textContent = msg || 'No conversations found.';
            emptyState.classList.remove('hidden');
        }
    }

    function hideEmpty() {
        if (emptyState) emptyState.classList.add('hidden');
    }

    // ── Public: expand/collapse answer text ──────────────────────────────────
    function toggleExpand(btn, targetId) {
        const el = document.getElementById(targetId);
        if (!el) return;
        const isExpanded = el.classList.toggle('expanded');
        btn.textContent = isExpanded ? 'Show less' : 'Show more';
    }

    // ── Wire events (called once) ──────────────────────────────────────────────
    function wireEvents() {
        // Event delegation for expand/collapse buttons (survives re-renders)
        if (tableBody) {
            tableBody.addEventListener('click', (e) => {
                const btn = e.target.closest('.conv-expand-btn');
                if (!btn) return;
                const targetId = btn.getAttribute('data-target');
                if (targetId) toggleExpand(btn, targetId);
            });
        }

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (currentPage > 1) fetchPage(currentPage - 1);
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                if (currentPage < totalPages) fetchPage(currentPage + 1);
            });
        }

        if (monthInput) {
            monthInput.addEventListener('change', () => {
                currentPage = 1;
                fetchPage(1);
            });
        }

        if (feedbackFilter) {
            feedbackFilter.addEventListener('change', () => {
                currentPage = 1;
                fetchPage(1);
            });
        }

        if (searchInput) {
            searchInput.addEventListener('input', () => {
                clearTimeout(searchDebounceTimer);
                searchDebounceTimer = setTimeout(() => {
                    currentPage = 1;
                    fetchPage(1);
                }, 400);
            });
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                if (monthInput)      monthInput.value      = '';
                if (searchInput)     searchInput.value     = '';
                if (feedbackFilter)  feedbackFilter.value  = '';
                currentPage = 1;
                fetchPage(1);
            });
        }

        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => fetchPage(currentPage));
        }
    }

    // ── Init (idempotent) ─────────────────────────────────────────────────────
    function init() {
        // Resolve DOM refs
        tableBody      = document.getElementById('convTableBody');
        emptyState     = document.getElementById('convEmptyState');
        metaEl         = document.getElementById('convMeta');
        pageInfo       = document.getElementById('convPageInfo');
        prevBtn        = document.getElementById('convPrevBtn');
        nextBtn        = document.getElementById('convNextBtn');
        loadingEl      = document.getElementById('convLoadingIndicator');
        monthInput     = document.getElementById('convMonthFilter');
        searchInput    = document.getElementById('convSearchInput');
        feedbackFilter = document.getElementById('convFeedbackFilter');
        clearBtn       = document.getElementById('convClearFiltersBtn');
        refreshBtn     = document.getElementById('refreshConversationsBtn');

        if (!tableBody) return; // Section not in DOM

        if (!initialized) {
            wireEvents();
            initialized = true;
        }

        fetchPage(1);
    }

    // Public API
    return { init };
})();
