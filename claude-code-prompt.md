You will now execute the RPI5 deployment preparation plan defined in `implementation_plan.md`.

Execution is authorized.

---

## Scope of Work (Deployment Only)

Implement the deployment refactors described in the plan.

Specifically:

* **Audit the existing `.gitignore`**

  * Ensure it properly excludes:

    * `venv/`
    * `__pycache__/`
    * `.env`
    * `*.pyc`
    * voice model directories
  * Update it only if incomplete.

* **Audit the existing `.env.example`**

  * Ensure it contains all required environment variables.
  * Ensure it aligns with what `pi-setup.sh` expects.
  * Fix inconsistencies if necessary.
  * Do not overwrite valid content without reason.

* Consolidate requirements files (reduce to two).

* Remove dead dependencies (e.g., `edge-tts`).

* Add missing dependencies (`sse-starlette`, `httpx`).

* Add proper Python version guards where required.

* Sync `requirements_rpi.txt` with base requirements.

* Fix stale references in `pi-setup.sh`.

* Fix branch mismatch in deployment instructions.

* Clean inconsistencies identified in the plan.

---

## Strict Constraints

You must NOT:

* Modify RAG logic
* Modify orchestrator logic
* Modify chatbot runtime behavior
* Modify vector store handling
* Introduce new technologies

This is deployment-layer refactoring only.

---

## Post-Execution Report

Provide:

* Files modified
* Files deleted
* Dependencies added/removed
* Confirmation that:

  * Requirements install cleanly
  * Setup script is consistent
  * No application logic was modified

---

Proceed.
