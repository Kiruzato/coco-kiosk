You are working on the CoCo Campus RAG Chatbot project.

I want to optimize the Raspberry Pi deployment by creating a runtime-only dependency configuration.

The Raspberry Pi does NOT perform document ingestion.
It only runs the chatbot using a pre-built FAISS index.

Therefore, ingestion-related dependencies should not be installed on the RPi.

Execution is authorized, but strictly limited to dependency restructuring and deployment troubleshooting.

---

# Core Objective

Create a runtime-only dependency configuration for RPi deployment that:

* Excludes ingestion-only packages
* Preserves full chatbot runtime functionality
* Does NOT break the RAG pipeline
* Does NOT modify core application logic

---

# Additional Requirement — Log Inspection

Before making changes:

1. Inspect the file:

```id="rpi-log"
rpi-runtime-logs.txt
```

located in the root directory.

2. Analyze any errors, warnings, or missing module traces.

3. Determine whether current runtime failures (if any) are caused by:

   * Missing dependencies
   * Ingestion-only imports
   * Improper guards
   * Incorrect setup script behavior

4. Troubleshoot and resolve issues in a way that aligns with runtime-only mode.

Do not guess. Base dependency removal decisions on both:

* Import analysis
* Actual runtime log evidence

---

# Implementation Tasks

## 1. Create a New File

Create:

```id="rpi-runtime-req"
requirements_rpi_runtime.txt
```

This file must:

* Include only runtime-required dependencies
* Exclude ingestion-related packages such as:

  * `unstructured[pdf]`
  * `pypdf`
  * `python-docx`
  * `tabulate`
  * Other ingestion-only tooling
* Preserve:

  * FastAPI stack
  * FAISS
  * LangChain
  * OpenAI
  * Streaming dependencies
  * Confidence scoring logic
  * Voice features (if currently supported)

Do NOT remove anything required for runtime query handling.

---

## 2. Update `pi-setup.sh`

Modify the setup script so that:

* It installs from `requirements_rpi_runtime.txt`
* It clearly indicates runtime-only mode
* It remains idempotent
* It contains explanatory comments

Do not modify Windows setup behavior.

---

## 3. Safeguards

Ensure:

* The application does not import ingestion-only modules at runtime.
* If ingestion modules are imported at module load time, refactor to lazy imports or guard them properly.
* The RPi runtime can start cleanly without ingestion packages installed.
* Any issues discovered in `rpi-runtime-logs.txt` are resolved.

Do NOT redesign ingestion architecture.
Only isolate it from runtime environment.

---

# Strict Constraints

You must NOT:

* Modify RAG retrieval logic
* Modify response orchestrator logic
* Modify chatbot behavior
* Change vector store logic
* Remove ingestion support from development environment
* Introduce new frameworks
* Redesign project structure

This is dependency optimization and troubleshooting only.

---

# Post-Execution Report

Provide:

1. Summary of log findings from `rpi-runtime-logs.txt`
2. Root cause analysis of any runtime errors
3. List of packages removed from RPi runtime
4. Confirmation that:

   * RPi runtime installs successfully
   * Application starts without ingestion packages
   * Directory queries function
   * Voice features function (if enabled)
5. Any lazy-import refactors performed

---

# Goal

Reduce RPi install time and footprint, fix any runtime issues found in logs, and preserve full runtime behavior.

Proceed carefully and methodically.