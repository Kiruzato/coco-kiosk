# 🏗 CQE Architecture & Admin System – Full Compliance Checklist

*(JSON-Based, Deterministic, Industry-Structured)*

---

# I. ARCHITECTURAL FOUNDATION

## 1. Single Source of Truth

* [ ] Exactly one JSON file stores all entities.
* [ ] No secondary entity storage exists.
* [ ] No in-memory registry acts as permanent state.
* [ ] No CQE logic mutates index directly.
* [ ] All mutations go through registry → save → rebuild.

---

## 2. Deterministic Data Flow

For every entity mutation:

1. Modify registry data
2. Call save_entities() (atomic write)
3. Rebuild CQE index

* [ ] No endpoint skips save.
* [ ] No endpoint rebuilds before save.
* [ ] No direct JSON modification bypassing registry.

---

# II. FULL JSON SCHEMA STRUCTURE

JSON must follow this structure:

```json
{
  "version": "1.x",
  "last_updated": "ISO_TIMESTAMP",
  "entities": [ ... ]
}
```

---

## Entity: Campus

Required fields:

* entity_id
* entity_type = "CAMPUS"
* name

Optional fields:

* description
* landmarks

Validation:

* [ ] entity_id unique
* [ ] status controlled (active/inactive)

---

## Entity: Building

Required fields:

* entity_id
* entity_type = "BUILDING"
* campus_id
* name

Optional fields:

* description
* landmarks

Validation:

* [ ] campus_id references existing campus

---

## Entity: Floor

Required fields:

* entity_id
* entity_type = "FLOOR"
* building_id
* level (integer)
* display_name

Validation:

* [ ] building_id exists

---

## Entity: Room

Required fields:

* entity_id
* entity_type = "ROOM"
* campus_id
* building_id
* floor_id
* canonical_name
* primary_type
* status

Optional fields:

* department_id
* room_number
* description
* landmarks
* tags (list)

Validation:

* [ ] campus_id exists
* [ ] building_id exists
* [ ] floor_id exists
* [ ] department_id valid if present
* [ ] tags is list if present

---

## Entity: OutdoorLocation

Required fields:

* entity_id
* entity_type = "OUTDOOR"
* campus_id
* canonical_name
* status

Optional fields:

* description
* landmarks
* tags (list)

Validation:

* [ ] campus_id exists

---

## Entity: Department

Required fields:

* entity_id
* entity_type = "DEPARTMENT"
* campus_id
* name

Optional fields:

* landmarks

Validation:

* [ ] campus_id exists

---

# III. SCHEMA INTEGRITY VALIDATION

Claude must verify:

* [ ] No duplicate entity_id.
* [ ] No orphaned building.
* [ ] No orphaned floor.
* [ ] No orphaned room.
* [ ] No orphaned department.
* [ ] No unexpected fields.
* [ ] All required fields exist.

If mismatch:

* Identify entity_id
* Explain violation
* Fix structure

---

# IV. ADMIN MANAGEMENT VALIDATION

## 1. Utilities Per Entity

| Entity     | Add | Edit | Delete | Search | Filter | Sort |
| ---------- | --- | ---- | ------ | ------ | ------ | ---- |
| Campus     | ✓   | ✓    | ✗      | ✓      | ✓      | ✓    |
| Building   | ✓   | ✓    | ✓      | ✓      | ✓      | ✓    |
| Floor      | ✓   | ✓    | ✓      | ✓      | ✓      | ✓    |
| Room       | ✓   | ✓    | ✓      | ✓      | ✓      | ✓    |
| Outdoor    | ✓   | ✓    | ✓      | ✓      | ✓      | ✓    |
| Department | ✓   | ✓    | ✓      | ✓      | ✓      | ✓    |
| Tag        | ✓   | ✗    | ✓      | ✓      | ✓      | ✓    |

* [ ] All utilities implemented.
* [ ] Delete buttons follow rules.
* [ ] ID fields visible but not editable.

---

## 2. Floor Embedded Under Building

* [ ] No standalone Floor tab.
* [ ] Floors displayed under building.
* [ ] Expand/collapse behavior exists.
* [ ] Add Floor inside building context.
* [ ] Floor auto-associates building_id.

---

## 3. Structured Fields

* [ ] Campus dropdown.
* [ ] Building dropdown.
* [ ] Floor dropdown.
* [ ] Department dropdown.
* [ ] Primary type dropdown.
* [ ] No relational free-text inputs.

---

# V. DELETION RULE ENFORCEMENT

### Campus

* [ ] Delete endpoint forbidden (403).
* [ ] No UI delete option.

### Building

* [ ] Block if rooms exist.
* [ ] Delete floors automatically if allowed.

### Floor

* [ ] Block if rooms exist.

### Room / Outdoor

* [ ] Hard delete allowed.

### Tag

* [ ] Standalone allowed.
* [ ] Delete blocked if in use.

---

# VI. DATA LOAD & RESTART INTEGRITY

Test:

* [ ] Add entity → restart → persists.
* [ ] Edit entity → restart → persists.
* [ ] Delete entity → restart → persists.
* [ ] Tag assignment persists.
* [ ] No ghost entities after restart.

---

# VII. CQE–SCHEMA INTEGRATION VALIDATION

## 1. Field Propagation

For every schema field:

* [ ] Loaded into registry.
* [ ] Mapped into CQE index.
* [ ] Accessible during query resolution.
* [ ] Included in responses if required.

No schema field unintentionally ignored.

---

## 2. Hierarchical Query Integrity

Test:

* Where is SP303?
* Where is Engineering Department?
* Show all classrooms on Ground Floor.
* List all offices in A Building.
* Show all College Department rooms.

Verify:

* [ ] Structured resolution.
* [ ] Not brittle string matching.
* [ ] Correct hierarchy traversal.

---

## 3. Tag Integration

* [ ] Tags loaded into index.
* [ ] Tag filtering functional.
* [ ] Tag removal updates behavior.
* [ ] No tag state cached separately.

---

## 4. Drift Detection

Check for:

* [ ] Schema fields unused by CQE.
* [ ] CQE referencing removed fields.
* [ ] Dead attributes.
* [ ] Hardcoded assumptions conflicting with schema.
* [ ] Partial mapping.

Fix any drift.

---

# VIII. ARCHITECTURAL CONSISTENCY QUESTIONS

Claude must answer:

1. Is JSON the only source of truth?
2. Is registry the only mutation layer?
3. Is CQE strictly derived?
4. Are deletion rules deterministic?
5. Is Admin fully wired?
6. Is there architectural redundancy?
7. Is system restart-safe?
8. Is CQE structurally a “structured campus intelligence engine”?

---

This checklist now fully reflects your original intent:

* JSON persistence
* Strong schema
* Strict admin wiring
* Deterministic CQE
* Structural integrity
* No drift
* No partial integration

