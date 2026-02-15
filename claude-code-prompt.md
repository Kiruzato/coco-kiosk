Modify the Raspberry Pi setup and deployment process so the system uses an already-ingested vector store created on the development machine. Do NOT redesign or refactor the ingestion pipeline, CQE, or retrieval architecture.

The goal is to transfer the pre-ingested data along with the web app so the chatbot works instantly on Raspberry Pi without performing ingestion.

---

## Objective

Ensure Raspberry Pi runs ONLY in runtime mode, loading an existing vector store that was generated on the development machine.

The Raspberry Pi setup must:

* NOT run ingestion
* NOT regenerate embeddings
* NOT rebuild the FAISS index
* ONLY load and use the existing vector store

---

## Tasks

### 1. Raspberry Pi Setup Script Modification

Modify the Raspberry Pi setup script so that it:

* Does NOT run any ingestion scripts
* Does NOT rebuild the vector store
* Only installs dependencies and starts the backend
* Assumes the vector store already exists

Ensure startup fails clearly if the vector store folder is missing.

---

### 2. Deployment Packaging

Define exactly what must be included when transferring the project to Raspberry Pi.

This includes:

* Web app source code
* Vector store folder (FAISS index and metadata)
* Required data files
* Configuration files

Ensure the vector store loads correctly without regeneration.

---

### 3. Repository and File Structure Adjustments

Modify project structure and setup logic if necessary so that:

* Vector store is recognized automatically
* No ingestion is triggered on startup
* Paths work correctly on Raspberry Pi

Do NOT modify CQE logic unless absolutely required for loading.

---

### 4. Raspberry Pi Deployment Workflow

Define the correct deployment process:

Development Machine:

* Use already ingested vector store

Deployment to Raspberry Pi:

* Copy project files
* Copy vector store folder
* Run setup script
* Start backend
* Chatbot works immediately

---

## Constraints

Do NOT redesign the system.

Do NOT modify ingestion logic.

Do NOT modify CQE architecture.

Do NOT introduce new technologies.

Only modify:

* Raspberry Pi setup script
* Deployment process
* File inclusion
* Startup behavior if necessary

---

## Expected Output

Provide:

* Exact setup script modifications
* Exact files and folders that must be transferred
* Exact repository structure requirements
* Exact deployment steps
* Any required safeguards

Provide implementation-ready changes only.
