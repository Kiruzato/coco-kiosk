Act as a senior engineer. Execute the following refactor in strict order.

Do not redesign architecture.
Do not propose alternatives.
Do not expand scope.
Keep responses concise and implementation-focused.
Ask only blocking questions if absolutely necessary.

---

# PHASE 1 — Fix JSON Persistence (Highest Priority)

Stabilize entity persistence:

* Ensure a single source-of-truth JSON file.
* Implement atomic write (write to temp file → replace original).
* Implement file lock during writes.
* Rebuild CQE index only after successful write.
* Ensure create/edit/delete survive restart.

Do not introduce database.
Do not implement reload-merge logic.
Keep solution minimal for single-process FastAPI + Uvicorn.

Verify persistence stability before continuing.

---

# PHASE 2 — Absorb Legacy Directory

* Fully absorb Directory Engine into CQE.
* Remove `/admin#entities` UI and backend routes.
* Backup removed legacy code to a folder in project root.
* Ensure only one admin data path and one index builder remain.

---

# PHASE 3 — Enforce Deletion Rules (Server-Side Only)

Floor:

* Block delete if rooms exist.
* If no rooms, allow delete.

Building:

* Block delete if any room exists in the building.
* If no rooms:

  * Show confirmation: building and its floors will be deleted.
  * Delete building and its floors.

Campus:

* No delete function.

Room & OutdoorLocation:

* Hard delete allowed.
* Require confirmation.
* Rebuild index after delete.

Tags:

* Standalone tag registry allowed.
* Block delete if tag is in use.

IDs:

* All entity IDs immutable (visible but not editable).

---

# PHASE 4 — Refactor and Integrate Existing CQE Admin

Refactor the existing `/admin/cqe` implementation and integrate it into `/admin`.

* Move CQE Admin functionality into `/admin` navigation.
* Remove `/admin/cqe` route after integration.
* Ensure `/admin#entities` no longer exists.
* Ensure there is only one entity management interface under `/admin`.

Do not build a new admin from scratch.
Enhance and restructure the existing CQE Admin.

---

## UI Structure Requirements

Under `/admin`, implement sidebar sections:

* Campus
* Buildings
* Rooms
* Outdoor Locations
* Departments
* Tags

Remove standalone Floor tab.

---

## Building–Floor Hierarchy

In Buildings section:

* Clicking a building expands its floors.
* Floor rows have edit/delete.
* “Add Floor” appears only inside expanded building.
* Floor auto-associates with parent building.
* Block floor delete if rooms exist.

---

## Structured Fields

Use dropdowns for:

* Campus
* Building
* Floor
* Department
* Primary type

No free-text for structured relationships.

Implement:

* Search by name
* Status filter
* Name sorting

Rooms additionally support:

* Filter by campus
* Filter by building
* Filter by primary type

---

## Tags Section

Add dedicated Tags section:

* List tags with usage count.
* Clicking tag shows entities using it.
* Create tag (unused tags allowed).
* Delete tag (blocked if in use).

Tags apply to:

* Room
* OutdoorLocation

---

# PHASE 5 — Field Additions

Add and support in Admin + CQE:

Campus:

* description
* landmarks

Building:

* description
* landmarks

Department:

* landmarks

Ensure fields persist and appear in CQE responses.

---

# Execution Order (Mandatory)

1. Persistence Fix
2. Directory Absorption
3. Deletion Rules
4. CQE Admin Refactor + Integration
5. Field Additions

Keep output concise.
Avoid theory and re-explanations.
Provide only necessary implementation details.