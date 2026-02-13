/**
 * CQE Admin - Campus Entity Management
 * Phase 62-65: Frontend Implementation
 */

// =============================================================================
// State Management
// =============================================================================

const state = {
    campuses: [],
    buildings: [],
    floors: [],
    rooms: [],
    outdoorLocations: [],
    departments: [],
    tags: [],
    currentSection: 'campus',
    deleteTarget: null
};

// Tag state for Room and Outdoor modals
const roomTags = [];
const outdoorTags = [];

// =============================================================================
// API Calls
// =============================================================================

async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        },
        credentials: 'include'
    };

    if (data && method !== 'GET') {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(endpoint, options);

        if (response.status === 401) {
            window.location.href = '/admin/login';
            return null;
        }

        const result = await response.json();

        if (!response.ok) {
            // HTTP error - surface it with error property for callers to detect
            return { error: result.detail || `HTTP ${response.status}`, detail: result.detail, _httpError: true };
        }

        return result;
    } catch (err) {
        console.error(`[apiCall] ${method} ${endpoint} failed:`, err);
        return { error: err.message, _networkError: true };
    }
}

// =============================================================================
// Data Loading
// =============================================================================

async function loadCampuses() {
    const data = await apiCall('/admin/cqe/campus');
    if (data && !data.error) {
        state.campuses = data.campuses;
        renderCampusTable();
        populateCampusDropdowns();
    }
}

async function loadBuildings() {
    const data = await apiCall('/admin/cqe/building');
    if (data && !data.error) {
        state.buildings = data.buildings;
        renderBuildingTable();
        populateBuildingDropdowns();
    }
}

async function loadFloors() {
    const data = await apiCall('/admin/cqe/floor');
    if (data && !data.error) {
        state.floors = data.floors;
        renderFloorTable();
    }
}

async function loadRooms() {
    // Build query params from filters
    const params = new URLSearchParams();
    const campusFilter = document.getElementById('room-campus-filter').value;
    const buildingFilter = document.getElementById('room-building-filter').value;
    const typeFilter = document.getElementById('room-type-filter').value;
    const statusFilter = document.getElementById('room-status-filter').value;
    const searchQuery = document.getElementById('room-search').value;

    if (campusFilter) params.set('campus_id', campusFilter);
    if (buildingFilter) params.set('building_id', buildingFilter);
    if (typeFilter) params.set('primary_type', typeFilter);
    if (statusFilter) params.set('status', statusFilter);
    if (searchQuery) params.set('q', searchQuery);

    const data = await apiCall(`/admin/cqe/room?${params}`);
    if (data && !data.error) {
        state.rooms = data.rooms;
        renderRoomTable();
    }
}

async function loadOutdoorLocations() {
    const params = new URLSearchParams();
    const campusFilter = document.getElementById('outdoor-campus-filter').value;
    const statusFilter = document.getElementById('outdoor-status-filter').value;
    const searchQuery = document.getElementById('outdoor-search').value;

    if (campusFilter) params.set('campus_id', campusFilter);
    if (statusFilter) params.set('status', statusFilter);
    if (searchQuery) params.set('q', searchQuery);

    const data = await apiCall(`/admin/cqe/outdoor?${params}`);
    if (data && !data.error) {
        state.outdoorLocations = data.outdoor_locations;
        renderOutdoorTable();
    }
}

async function loadDepartments() {
    const data = await apiCall('/admin/cqe/department');
    if (data && !data.error) {
        state.departments = data.departments;
        renderDepartmentTable();
        populateDepartmentDropdowns();
    }
}

async function loadTags() {
    const data = await apiCall('/admin/cqe/tags');
    if (data && !data.error) {
        state.tags = data.tags;
    }
}

async function loadAllData() {
    await Promise.all([
        loadCampuses(),
        loadBuildings(),
        loadFloors(),
        loadDepartments(),
        loadTags()
    ]);
    // Rooms and outdoor need other data loaded first for filters
    await loadRooms();
    await loadOutdoorLocations();
}

// =============================================================================
// Table Rendering
// =============================================================================

function renderCampusTable() {
    const tbody = document.getElementById('campus-table-body');
    const searchQuery = document.getElementById('campus-search').value.toLowerCase();

    const filtered = state.campuses.filter(c =>
        c.name.toLowerCase().includes(searchQuery) ||
        c.aliases.some(a => a.toLowerCase().includes(searchQuery))
    );

    if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No campuses found</td></tr>';
        return;
    }

    tbody.innerHTML = filtered.map(c => `
        <tr>
            <td>${escapeHtml(c.name)}</td>
            <td>${c.aliases.map(a => `<span class="tag">${escapeHtml(a)}</span>`).join(' ')}</td>
            <td>${c.building_ids.length}</td>
            <td class="actions">
                <button class="btn-icon" onclick="editCampus('${c.campus_id}')" title="Edit">Edit</button>
            </td>
        </tr>
    `).join('');
}

function renderBuildingTable() {
    const tbody = document.getElementById('building-table-body');
    const searchQuery = document.getElementById('building-search').value.toLowerCase();
    const campusFilter = document.getElementById('building-campus-filter').value;

    const filtered = state.buildings.filter(b => {
        if (campusFilter && b.campus_id !== campusFilter) return false;
        return b.name.toLowerCase().includes(searchQuery) ||
            b.aliases.some(a => a.toLowerCase().includes(searchQuery));
    });

    if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No buildings found</td></tr>';
        return;
    }

    tbody.innerHTML = filtered.map(b => {
        const campus = state.campuses.find(c => c.campus_id === b.campus_id);
        return `
            <tr>
                <td>${escapeHtml(b.name)}</td>
                <td>${campus ? escapeHtml(campus.name) : '-'}</td>
                <td>${b.aliases.map(a => `<span class="tag">${escapeHtml(a)}</span>`).join(' ')}</td>
                <td>${b.floor_ids.length}</td>
                <td class="actions">
                    <button class="btn-icon" onclick="editBuilding('${b.building_id}')" title="Edit">Edit</button>
                </td>
            </tr>
        `;
    }).join('');
}

function renderFloorTable() {
    const tbody = document.getElementById('floor-table-body');
    const searchQuery = document.getElementById('floor-search').value.toLowerCase();
    const buildingFilter = document.getElementById('floor-building-filter').value;

    const filtered = state.floors.filter(f => {
        if (buildingFilter && f.building_id !== buildingFilter) return false;
        return f.display_name.toLowerCase().includes(searchQuery);
    });

    if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No floors found</td></tr>';
        return;
    }

    tbody.innerHTML = filtered.map(f => {
        const building = state.buildings.find(b => b.building_id === f.building_id);
        return `
            <tr>
                <td>${escapeHtml(f.display_name)}</td>
                <td>${building ? escapeHtml(building.name) : '-'}</td>
                <td>${f.level_number}</td>
                <td>${f.aliases.map(a => `<span class="tag">${escapeHtml(a)}</span>`).join(' ')}</td>
                <td class="actions">
                    <button class="btn-icon" onclick="editFloor('${f.floor_id}')" title="Edit">Edit</button>
                </td>
            </tr>
        `;
    }).join('');
}

function renderRoomTable() {
    const tbody = document.getElementById('room-table-body');

    if (!state.rooms || state.rooms.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No rooms found</td></tr>';
        return;
    }

    tbody.innerHTML = state.rooms.map(r => {
        const building = state.buildings.find(b => b.building_id === r.building_id);
        const floor = state.floors.find(f => f.floor_id === r.floor_id);
        return `
            <tr>
                <td>${escapeHtml(r.canonical_name)}</td>
                <td>${building ? escapeHtml(building.name) : '-'}</td>
                <td>${floor ? escapeHtml(floor.display_name) : '-'}</td>
                <td>${escapeHtml(r.primary_type)}</td>
                <td>${r.tags.slice(0, 3).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join(' ')}${r.tags.length > 3 ? '...' : ''}</td>
                <td><span class="tag status-${r.status}">${r.status}</span></td>
                <td class="actions">
                    <button class="btn-icon" onclick="editRoom('${r.room_id}')" title="Edit">Edit</button>
                </td>
            </tr>
        `;
    }).join('');
}

function renderOutdoorTable() {
    const tbody = document.getElementById('outdoor-table-body');

    if (!state.outdoorLocations || state.outdoorLocations.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No outdoor locations found</td></tr>';
        return;
    }

    tbody.innerHTML = state.outdoorLocations.map(o => {
        const campus = state.campuses.find(c => c.campus_id === o.campus_id);
        return `
            <tr>
                <td>${escapeHtml(o.canonical_name)}</td>
                <td>${campus ? escapeHtml(campus.name) : '-'}</td>
                <td>${o.tags.slice(0, 3).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join(' ')}${o.tags.length > 3 ? '...' : ''}</td>
                <td><span class="tag status-${o.status}">${o.status}</span></td>
                <td class="actions">
                    <button class="btn-icon" onclick="editOutdoor('${o.location_id}')" title="Edit">Edit</button>
                </td>
            </tr>
        `;
    }).join('');
}

function renderDepartmentTable() {
    const tbody = document.getElementById('department-table-body');
    const searchQuery = document.getElementById('department-search').value.toLowerCase();

    const filtered = state.departments.filter(d =>
        d.name.toLowerCase().includes(searchQuery) ||
        d.aliases.some(a => a.toLowerCase().includes(searchQuery))
    );

    if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No departments found</td></tr>';
        return;
    }

    tbody.innerHTML = filtered.map(d => {
        const campus = state.campuses.find(c => c.campus_id === d.campus_id);
        return `
            <tr>
                <td>${escapeHtml(d.name)}</td>
                <td>${campus ? escapeHtml(campus.name) : 'All'}</td>
                <td>${d.aliases.map(a => `<span class="tag">${escapeHtml(a)}</span>`).join(' ')}</td>
                <td class="actions">
                    <button class="btn-icon" onclick="editDepartment('${d.department_id}')" title="Edit">Edit</button>
                </td>
            </tr>
        `;
    }).join('');
}

// =============================================================================
// Dropdown Population
// =============================================================================

function populateCampusDropdowns() {
    const dropdowns = [
        'building-campus',
        'building-campus-filter',
        'room-campus',
        'room-campus-filter',
        'outdoor-campus',
        'outdoor-campus-filter',
        'department-campus'
    ];

    dropdowns.forEach(id => {
        const select = document.getElementById(id);
        if (!select) return;

        const currentValue = select.value;
        const isFilter = id.includes('filter');

        select.innerHTML = isFilter
            ? '<option value="">All Campuses</option>'
            : '<option value="">Select Campus</option>';

        state.campuses.forEach(c => {
            const option = document.createElement('option');
            option.value = c.campus_id;
            option.textContent = c.name;
            select.appendChild(option);
        });

        select.value = currentValue;
    });
}

function populateBuildingDropdowns() {
    const dropdowns = [
        'floor-building',
        'floor-building-filter',
        'room-building',
        'room-building-filter'
    ];

    dropdowns.forEach(id => {
        const select = document.getElementById(id);
        if (!select) return;

        const currentValue = select.value;
        const isFilter = id.includes('filter');

        select.innerHTML = isFilter
            ? '<option value="">All Buildings</option>'
            : '<option value="">Select Building</option>';

        state.buildings.forEach(b => {
            const option = document.createElement('option');
            option.value = b.building_id;
            option.textContent = b.name;
            select.appendChild(option);
        });

        select.value = currentValue;
    });
}

function populateDepartmentDropdowns() {
    const select = document.getElementById('room-department');
    if (!select) return;

    const currentValue = select.value;
    select.innerHTML = '<option value="">None</option>';

    state.departments.forEach(d => {
        const option = document.createElement('option');
        option.value = d.department_id;
        option.textContent = d.name;
        select.appendChild(option);
    });

    select.value = currentValue;
}

// =============================================================================
// Section Navigation
// =============================================================================

function switchSection(section) {
    // Update nav
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.section === section);
    });

    // Update sections
    document.querySelectorAll('.entity-section').forEach(sec => {
        sec.classList.toggle('active', sec.id === `${section}-section`);
    });

    state.currentSection = section;

    // Phase 4: Update URL hash for bookmarking/linking
    if (window.location.hash.slice(1) !== section) {
        history.replaceState(null, '', `#${section}`);
    }
}

// =============================================================================
// Modal Management
// =============================================================================

function showModal(type, editData = null) {
    const modal = document.getElementById(`${type}-modal`);
    const title = document.getElementById(`${type}-modal-title`);
    const form = document.getElementById(`${type}-form`);

    form.reset();

    if (editData) {
        title.textContent = `Edit ${capitalize(type)}`;
        populateModalForm(type, editData);
    } else {
        title.textContent = `Add ${capitalize(type)}`;
        // Clear hidden edit IDs and enable ID fields for creation
        if (type === 'campus') {
            document.getElementById('campus-edit-id').value = '';
        }
        if (type === 'building') {
            document.getElementById('building-edit-id').value = '';
        }
        if (type === 'floor') {
            document.getElementById('floor-edit-id').value = '';
        }
        if (type === 'room') {
            document.getElementById('room-edit-id').value = '';
            document.getElementById('room-id').value = '';
            document.getElementById('room-id').disabled = false;
            roomTags.length = 0;
            renderRoomTags();
            document.getElementById('room-delete-btn').style.display = 'none';
        }
        if (type === 'outdoor') {
            document.getElementById('outdoor-edit-id').value = '';
            document.getElementById('outdoor-id').value = '';
            document.getElementById('outdoor-id').disabled = false;
            outdoorTags.length = 0;
            renderOutdoorTags();
            document.getElementById('outdoor-delete-btn').style.display = 'none';
        }
        if (type === 'department') {
            document.getElementById('department-edit-id').value = '';
        }
    }

    modal.classList.add('active');
}

function closeModal(type) {
    const modal = document.getElementById(`${type}-modal`);
    modal.classList.remove('active');

    // Always clear edit IDs when closing to prevent stale state
    if (type === 'room') {
        document.getElementById('room-edit-id').value = '';
        document.getElementById('room-id').disabled = false;
    }
    if (type === 'outdoor') {
        document.getElementById('outdoor-edit-id').value = '';
        document.getElementById('outdoor-id').disabled = false;
    }
    if (type === 'floor') {
        document.getElementById('floor-edit-id').value = '';
    }
    if (type === 'building') {
        document.getElementById('building-edit-id').value = '';
    }
    if (type === 'campus') {
        document.getElementById('campus-edit-id').value = '';
    }
    if (type === 'department') {
        document.getElementById('department-edit-id').value = '';
    }
}

function populateModalForm(type, data) {
    switch (type) {
        case 'campus':
            document.getElementById('campus-edit-id').value = data.campus_id;
            document.getElementById('campus-name').value = data.name;
            document.getElementById('campus-aliases').value = data.aliases.join(', ');
            break;

        case 'building':
            document.getElementById('building-edit-id').value = data.building_id;
            document.getElementById('building-campus').value = data.campus_id;
            document.getElementById('building-name').value = data.name;
            document.getElementById('building-aliases').value = data.aliases.join(', ');
            break;

        case 'floor':
            document.getElementById('floor-edit-id').value = data.floor_id;
            document.getElementById('floor-building').value = data.building_id;
            document.getElementById('floor-level').value = data.level_number;
            document.getElementById('floor-display-name').value = data.display_name;
            document.getElementById('floor-aliases').value = data.aliases.join(', ');
            break;

        case 'room':
            document.getElementById('room-edit-id').value = data.room_id;
            document.getElementById('room-id').value = data.room_id;
            document.getElementById('room-id').disabled = true;
            document.getElementById('room-canonical-name').value = data.canonical_name;
            document.getElementById('room-campus').value = data.campus_id;
            onRoomCampusChange().then(() => {
                document.getElementById('room-building').value = data.building_id;
                return onRoomBuildingChange();
            }).then(() => {
                document.getElementById('room-floor').value = data.floor_id;
            });
            document.getElementById('room-number').value = data.room_number || '';
            document.getElementById('room-primary-type').value = data.primary_type;
            document.getElementById('room-department').value = data.department_id || '';
            document.getElementById('room-aliases').value = data.aliases.join(', ');
            document.getElementById('room-landmarks').value = data.landmarks || '';
            document.getElementById('room-description').value = data.description || '';
            document.getElementById('room-status').value = data.status;
            // Populate tags
            roomTags.length = 0;
            roomTags.push(...data.tags);
            renderRoomTags();
            document.getElementById('room-delete-btn').style.display = 'block';
            break;

        case 'outdoor':
            document.getElementById('outdoor-edit-id').value = data.location_id;
            document.getElementById('outdoor-id').value = data.location_id;
            document.getElementById('outdoor-id').disabled = true;
            document.getElementById('outdoor-canonical-name').value = data.canonical_name;
            document.getElementById('outdoor-campus').value = data.campus_id;
            document.getElementById('outdoor-aliases').value = data.aliases.join(', ');
            document.getElementById('outdoor-landmarks').value = data.landmarks || '';
            document.getElementById('outdoor-description').value = data.description || '';
            document.getElementById('outdoor-status').value = data.status;
            // Populate tags
            outdoorTags.length = 0;
            outdoorTags.push(...data.tags);
            renderOutdoorTags();
            document.getElementById('outdoor-delete-btn').style.display = 'block';
            break;

        case 'department':
            document.getElementById('department-edit-id').value = data.department_id;
            document.getElementById('department-name').value = data.name;
            document.getElementById('department-campus').value = data.campus_id || '';
            document.getElementById('department-aliases').value = data.aliases.join(', ');
            document.getElementById('department-description').value = data.description || '';
            break;
    }
}

// Edit functions
function editCampus(id) {
    const campus = state.campuses.find(c => c.campus_id === id);
    if (campus) showModal('campus', campus);
}

function editBuilding(id) {
    const building = state.buildings.find(b => b.building_id === id);
    if (building) showModal('building', building);
}

function editFloor(id) {
    const floor = state.floors.find(f => f.floor_id === id);
    if (floor) showModal('floor', floor);
}

function editRoom(id) {
    const room = state.rooms.find(r => r.room_id === id);
    if (room) showModal('room', room);
}

function editOutdoor(id) {
    const outdoor = state.outdoorLocations.find(o => o.location_id === id);
    if (outdoor) showModal('outdoor', outdoor);
}

function editDepartment(id) {
    const dept = state.departments.find(d => d.department_id === id);
    if (dept) showModal('department', dept);
}

// =============================================================================
// CRUD Operations
// =============================================================================

async function saveCampus(e) {
    e.preventDefault();
    const editId = document.getElementById('campus-edit-id').value;
    const name = document.getElementById('campus-name').value.trim();
    const aliases = parseCommaList(document.getElementById('campus-aliases').value);

    const data = { name, aliases };
    let result;

    if (editId) {
        result = await apiCall(`/admin/cqe/campus/${editId}`, 'PUT', data);
    } else {
        result = await apiCall('/admin/cqe/campus', 'POST', data);
    }

    if (result && result.status === 'success') {
        showToast(result.message, 'success');
        closeModal('campus');
        await loadCampuses();
    } else {
        showToast(result?.detail || result?.error || 'Failed to save campus', 'error');
    }
}

async function saveBuilding(e) {
    e.preventDefault();
    const editId = document.getElementById('building-edit-id').value;
    const campus_id = document.getElementById('building-campus').value;
    const name = document.getElementById('building-name').value.trim();
    const aliases = parseCommaList(document.getElementById('building-aliases').value);

    const data = { campus_id, name, aliases };
    let result;

    if (editId) {
        result = await apiCall(`/admin/cqe/building/${editId}`, 'PUT', data);
    } else {
        result = await apiCall('/admin/cqe/building', 'POST', data);
    }

    if (result && result.status === 'success') {
        showToast(result.message, 'success');
        closeModal('building');
        await loadBuildings();
    } else {
        showToast(result?.detail || result?.error || 'Failed to save building', 'error');
    }
}

async function saveFloor(e) {
    e.preventDefault();
    const editId = document.getElementById('floor-edit-id').value;
    const building_id = document.getElementById('floor-building').value;
    const level_number = parseInt(document.getElementById('floor-level').value);
    const display_name = document.getElementById('floor-display-name').value.trim();
    const aliases = parseCommaList(document.getElementById('floor-aliases').value);

    const data = { building_id, level_number, display_name, aliases };
    let result;

    if (editId) {
        result = await apiCall(`/admin/cqe/floor/${editId}`, 'PUT', data);
    } else {
        result = await apiCall('/admin/cqe/floor', 'POST', data);
    }

    if (result && result.status === 'success') {
        showToast(result.message, 'success');
        closeModal('floor');
        await loadFloors();
    } else {
        showToast(result?.detail || result?.error || 'Failed to save floor', 'error');
    }
}

async function saveRoom(e) {
    e.preventDefault();
    const editId = document.getElementById('room-edit-id').value;
    const room_id = document.getElementById('room-id').value.trim().toUpperCase();
    const canonical_name = document.getElementById('room-canonical-name').value.trim();
    const campus_id = document.getElementById('room-campus').value;
    const building_id = document.getElementById('room-building').value;
    const floor_id = document.getElementById('room-floor').value;
    const room_number = document.getElementById('room-number').value.trim() || null;
    const primary_type = document.getElementById('room-primary-type').value;
    const department_id = document.getElementById('room-department').value || null;
    const aliases = parseCommaList(document.getElementById('room-aliases').value);
    const landmarks = document.getElementById('room-landmarks').value.trim() || null;
    const description = document.getElementById('room-description').value.trim() || null;
    const status = document.getElementById('room-status').value;
    const tags = [...roomTags];

    const data = {
        room_id, canonical_name, campus_id, building_id, floor_id,
        room_number, primary_type, department_id, aliases, landmarks,
        description, status, tags
    };

    let result;
    if (editId) {
        result = await apiCall(`/admin/cqe/room/${editId}`, 'PUT', data);
    } else {
        result = await apiCall('/admin/cqe/room', 'POST', data);
    }

    if (result && result.status === 'success') {
        showToast(result.message, 'success');
        closeModal('room');
        document.getElementById('room-id').disabled = false;
        // Clear filters after creating a new room so it's always visible
        if (!editId) {
            document.getElementById('room-campus-filter').value = '';
            document.getElementById('room-building-filter').value = '';
            document.getElementById('room-type-filter').value = '';
            document.getElementById('room-status-filter').value = '';
            document.getElementById('room-search').value = '';
        }
        await loadRooms();
    } else {
        showToast(result?.detail || result?.error || 'Failed to save room', 'error');
    }
}

async function saveOutdoor(e) {
    e.preventDefault();
    const editId = document.getElementById('outdoor-edit-id').value;
    const location_id = document.getElementById('outdoor-id').value.trim().toUpperCase();
    const canonical_name = document.getElementById('outdoor-canonical-name').value.trim();
    const campus_id = document.getElementById('outdoor-campus').value;
    const aliases = parseCommaList(document.getElementById('outdoor-aliases').value);
    const landmarks = document.getElementById('outdoor-landmarks').value.trim() || null;
    const description = document.getElementById('outdoor-description').value.trim() || null;
    const status = document.getElementById('outdoor-status').value;
    const tags = [...outdoorTags];

    const data = {
        location_id, canonical_name, campus_id, aliases,
        landmarks, description, status, tags
    };

    let result;
    if (editId) {
        result = await apiCall(`/admin/cqe/outdoor/${editId}`, 'PUT', data);
    } else {
        result = await apiCall('/admin/cqe/outdoor', 'POST', data);
    }

    if (result && result.status === 'success') {
        showToast(result.message, 'success');
        closeModal('outdoor');
        document.getElementById('outdoor-id').disabled = false;
        // Clear filters after creating a new outdoor location so it's always visible
        if (!editId) {
            document.getElementById('outdoor-campus-filter').value = '';
            document.getElementById('outdoor-status-filter').value = '';
            document.getElementById('outdoor-search').value = '';
        }
        await loadOutdoorLocations();
    } else {
        showToast(result?.detail || result?.error || 'Failed to save outdoor location', 'error');
    }
}

async function saveDepartment(e) {
    e.preventDefault();
    const editId = document.getElementById('department-edit-id').value;
    const name = document.getElementById('department-name').value.trim();
    const campus_id = document.getElementById('department-campus').value || null;
    const aliases = parseCommaList(document.getElementById('department-aliases').value);
    const description = document.getElementById('department-description').value.trim() || null;

    const data = { name, campus_id, aliases, description };
    let result;

    if (editId) {
        result = await apiCall(`/admin/cqe/department/${editId}`, 'PUT', data);
    } else {
        result = await apiCall('/admin/cqe/department', 'POST', data);
    }

    if (result && result.status === 'success') {
        showToast(result.message, 'success');
        closeModal('department');
        await loadDepartments();
    } else {
        showToast(result?.detail || result?.error || 'Failed to save department', 'error');
    }
}

// =============================================================================
// Delete Operations
// =============================================================================

function confirmDeleteRoom() {
    const roomId = document.getElementById('room-edit-id').value;
    const room = state.rooms.find(r => r.room_id === roomId);
    if (room) {
        state.deleteTarget = { type: 'room', id: roomId, name: room.canonical_name };
        document.getElementById('delete-entity-name').textContent = room.canonical_name;
        document.getElementById('delete-modal').classList.add('active');
    }
}

function confirmDeleteOutdoor() {
    const locationId = document.getElementById('outdoor-edit-id').value;
    const outdoor = state.outdoorLocations.find(o => o.location_id === locationId);
    if (outdoor) {
        state.deleteTarget = { type: 'outdoor', id: locationId, name: outdoor.canonical_name };
        document.getElementById('delete-entity-name').textContent = outdoor.canonical_name;
        document.getElementById('delete-modal').classList.add('active');
    }
}

function closeDeleteModal() {
    document.getElementById('delete-modal').classList.remove('active');
    state.deleteTarget = null;
}

async function executeDelete() {
    if (!state.deleteTarget) return;

    const { type, id } = state.deleteTarget;
    let endpoint = '';

    if (type === 'room') {
        endpoint = `/admin/cqe/room/${id}?hard=true`;
    } else if (type === 'outdoor') {
        endpoint = `/admin/cqe/outdoor/${id}?hard=true`;
    }

    const result = await apiCall(endpoint, 'DELETE');

    if (result && result.status === 'success') {
        showToast(result.message, 'success');
        closeDeleteModal();
        closeModal(type);
        if (type === 'room') {
            document.getElementById('room-id').disabled = false;
            await loadRooms();
        } else {
            document.getElementById('outdoor-id').disabled = false;
            await loadOutdoorLocations();
        }
    } else {
        showToast(result?.detail || 'Failed to delete', 'error');
    }
}

// =============================================================================
// Cascading Dropdowns
// =============================================================================

async function onRoomCampusChange() {
    const campusId = document.getElementById('room-campus').value;
    const buildingSelect = document.getElementById('room-building');
    const floorSelect = document.getElementById('room-floor');

    // Reset dependent dropdowns
    buildingSelect.innerHTML = '<option value="">Select Building</option>';
    floorSelect.innerHTML = '<option value="">Select Floor</option>';

    if (!campusId) return;

    // Filter buildings by campus
    const buildings = state.buildings.filter(b => b.campus_id === campusId);
    buildings.forEach(b => {
        const option = document.createElement('option');
        option.value = b.building_id;
        option.textContent = b.name;
        buildingSelect.appendChild(option);
    });
}

async function onRoomBuildingChange() {
    const buildingId = document.getElementById('room-building').value;
    const floorSelect = document.getElementById('room-floor');

    // Reset floor dropdown
    floorSelect.innerHTML = '<option value="">Select Floor</option>';

    if (!buildingId) return;

    // Filter floors by building
    const floors = state.floors.filter(f => f.building_id === buildingId);
    floors.sort((a, b) => a.level_number - b.level_number);
    floors.forEach(f => {
        const option = document.createElement('option');
        option.value = f.floor_id;
        option.textContent = f.display_name;
        floorSelect.appendChild(option);
    });
}

// =============================================================================
// Tag Input
// =============================================================================

function setupTagInput(inputId, tagsArray, renderFunc) {
    const input = document.getElementById(inputId);
    if (!input) return;

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const tag = input.value.toLowerCase().trim();
            if (tag && !tagsArray.includes(tag)) {
                tagsArray.push(tag);
                renderFunc();
            }
            input.value = '';
        }
    });
}

function renderRoomTags() {
    const container = document.getElementById('room-tags');
    container.innerHTML = roomTags.map(tag => `
        <span class="tag-pill">
            ${escapeHtml(tag)}
            <button type="button" class="remove-tag" onclick="removeRoomTag('${escapeHtml(tag)}')">&times;</button>
        </span>
    `).join('');
}

function renderOutdoorTags() {
    const container = document.getElementById('outdoor-tags');
    container.innerHTML = outdoorTags.map(tag => `
        <span class="tag-pill">
            ${escapeHtml(tag)}
            <button type="button" class="remove-tag" onclick="removeOutdoorTag('${escapeHtml(tag)}')">&times;</button>
        </span>
    `).join('');
}

function removeRoomTag(tag) {
    const index = roomTags.indexOf(tag);
    if (index > -1) {
        roomTags.splice(index, 1);
        renderRoomTags();
    }
}

function removeOutdoorTag(tag) {
    const index = outdoorTags.indexOf(tag);
    if (index > -1) {
        outdoorTags.splice(index, 1);
        renderOutdoorTags();
    }
}

// =============================================================================
// Utility Functions
// =============================================================================

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function parseCommaList(str) {
    if (!str) return [];
    return str.split(',').map(s => s.trim().toLowerCase()).filter(s => s);
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// =============================================================================
// Event Listeners
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            switchSection(item.dataset.section);
        });
    });

    // Search/Filter debounce
    let searchTimeout;
    const debounceSearch = (fn) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(fn, 300);
    };

    // Campus search
    document.getElementById('campus-search').addEventListener('input', () => {
        debounceSearch(renderCampusTable);
    });

    // Building search and filter
    document.getElementById('building-search').addEventListener('input', () => {
        debounceSearch(renderBuildingTable);
    });
    document.getElementById('building-campus-filter').addEventListener('change', renderBuildingTable);

    // Floor search and filter
    document.getElementById('floor-search').addEventListener('input', () => {
        debounceSearch(renderFloorTable);
    });
    document.getElementById('floor-building-filter').addEventListener('change', renderFloorTable);

    // Room search and filters
    document.getElementById('room-search').addEventListener('input', () => {
        debounceSearch(loadRooms);
    });
    document.getElementById('room-campus-filter').addEventListener('change', loadRooms);
    document.getElementById('room-building-filter').addEventListener('change', loadRooms);
    document.getElementById('room-type-filter').addEventListener('change', loadRooms);
    document.getElementById('room-status-filter').addEventListener('change', loadRooms);

    // Outdoor search and filters
    document.getElementById('outdoor-search').addEventListener('input', () => {
        debounceSearch(loadOutdoorLocations);
    });
    document.getElementById('outdoor-campus-filter').addEventListener('change', loadOutdoorLocations);
    document.getElementById('outdoor-status-filter').addEventListener('change', loadOutdoorLocations);

    // Department search
    document.getElementById('department-search').addEventListener('input', () => {
        debounceSearch(renderDepartmentTable);
    });

    // Tag inputs
    setupTagInput('room-tags-input', roomTags, renderRoomTags);
    setupTagInput('outdoor-tags-input', outdoorTags, renderOutdoorTags);

    // Close modals on escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal.active').forEach(modal => {
                modal.classList.remove('active');
            });
        }
    });

    // Close modals on backdrop click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    });

    // Load all data
    loadAllData();

    // Phase 4: Hash-based navigation (supports links like /admin/cqe#building)
    const handleHashNavigation = () => {
        const hash = window.location.hash.slice(1); // Remove '#'
        const validSections = ['campus', 'building', 'floor', 'room', 'outdoor', 'department'];
        if (hash && validSections.includes(hash)) {
            switchSection(hash);
        }
    };

    // Handle initial hash on page load
    handleHashNavigation();

    // Handle hash changes (browser back/forward)
    window.addEventListener('hashchange', handleHashNavigation);
});
