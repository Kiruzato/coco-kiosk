Entity Persistence Audit Report
Executive Summary
The entity persistence mechanism relies on 

data/directory_entities.json
 as the single source of truth. The code logic for saving and loading entities is functionally correct in isolation. However, the system is susceptible to race conditions if multiple worker processes are used, which explains why newly added entities disappear after restarts (old in-memory state overwrites new file state).

Findings
1. Source of Truth
Primary File: 

campus_rag_chatbot/data/directory_entities.json
Usage:

EntityRegistry
: Loads from this file on initialization. Saves to this file on add/update/delete.

CampusQueryIndex
: Loads from this file during initialization and rebuilds.

app.py
: Initializes both components pointing to this same file path.
2. Persistence Mechanism
Verification: A standalone script confirmed that 

add_entity
 successfully writes to disk and the data persists across new instances of 

EntityRegistry
.
Implementation: EntityRegistry.save_entities performs a direct file overwrite using json.dump. It does not use atomic writes (write-to-temp-and-rename) or file locking.
Backup: No automatic backup restoration logic was found in 

app.py
 startup.
3. Data Loss Diagnosis
The reported issue "newly added entities disappear after restart" is likely caused by one of the following:

A. Race Condition (High Probability)
If the server is run with multiple workers (e.g., uvicorn app:app --workers 4 or gunicorn), each worker maintains its own isolated in-memory 

EntityRegistry
.

Worker A loads entities (State: v1).
Worker B loads entities (State: v1).
User adds entity via Worker A.
Worker A updates memory (State: v2).
Worker A saves to file (File: v2).
User updates another entity via Worker B.
Worker B (Memory: v1) updates its memory.
CRITICAL FAILURE: Worker B saves its memory (v1 + update) to file, overwriting the changes from Worker A.
Restart happens. System loads the last saved file, which is missing the entity added in step 3.
B. Deployment Environment
If running in a containerized environment (Docker) without mapping the data/ directory to a persistent volume, all changes are lost on container restart. Given the user is on Windows/Local, this is less likely unless using Docker Desktop.

4. Other Observation
JSON Files: Multiple 

directory_entities.json
 files exist (backups, tests), but the application explicitly uses the one in data/.
Logging: Server logs were not found in the expected logs/server.log location, making it difficult to debug silent permission failures (though verification script suggests permissions are fine).
Recommendations
Enforce Single Writer: Ensure the application runs with a single worker process if using the current file-based architecture.
Implement File Locking: Modify EntityRegistry.save_entities to use a file lock (e.g., filelock library) to prevent concurrent writes.
Reload-Before-Save: Modify 

save_entities
 to:
Acquire Lock.
Read current file from disk.
Merge in-memory changes.
Write back to disk.
Release Lock.
Database Migration: For robust multi-user/multi-worker support, migrate entity storage to a proper database (SQLite/PostgreSQL) instead of a JSON file.