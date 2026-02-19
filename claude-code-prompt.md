You are working on the CoCo Campus RAG Chatbot project.

I want to transition the system to a fully document-based RAG approach for directory information.

The goal is:

* Create a directory document (e.g., PDF) containing all directory information.
* Ensure the content of that PDF is written and formatted in a retrieval-optimized way (clear sections per office/person, natural language descriptions, strong semantic clarity).
* Ingest this directory PDF through the normal RAG ingestion pipeline.
* Remove the existing directory entity system entirely.
* Remove directory entities in both the backend and the Admin UI.

Important clarification:

The directory document will be a standard RAG-ingested document (such as a PDF). It will not be a structured database or JSON entity system. However, its content must be formatted intentionally to maximize semantic retrieval performance.

Your task is to create a comprehensive architectural and implementation plan for safely accomplishing this migration and removal.

This is a planning task only. Do not write code.

---

# Core Objective

Produce a detailed, structured plan for:

1. Migrating directory data into a RAG-ingested PDF document.
2. Validating retrieval accuracy and system stability.
3. Decommissioning and removing all directory entity-related systems.
4. Ensuring the system remains stable, consistent, and fully functional after removal.

The end state must be a unified RAG-based knowledge system with no structured directory entity subsystem remaining.

---

# Planning Requirements

Your plan must include the following:

---

## 1. Architectural Impact Analysis

Identify and analyze:

* Backend components that depend on directory entities
* Retrieval or orchestration logic that references directory entities
* Ingestion logic that handles entity-specific processing
* Admin UI components that manage directory entities
* API routes related to directory entities
* Any validation, grounding, or ranking logic that assumes entity structures

Explain architectural dependencies and coupling points that must be addressed.

---

## 2. Directory PDF Design Plan

Define:

* How the directory PDF content should be formatted for optimal retrieval
* Section structure strategy (per office/person)
* Chunking considerations
* Semantic clarity considerations
* How to ensure list-based queries (e.g., “List all deans”) remain accurate
* How to avoid formatting patterns that reduce embedding quality

This must be optimized specifically for FAISS-based semantic retrieval and hybrid ranking.

---

## 3. Migration Strategy (Phased)

Provide a safe, staged migration plan:

* How to introduce the new directory PDF into ingestion
* How to validate directory-related question performance
* How to compare results before removing entity logic
* How to avoid a big-bang deletion

The plan must reduce regression risk.

---

## 4. Directory Entity System Decommissioning Plan

Define a structured removal roadmap:

* What to deprecate first
* What to remove from backend
* What to remove from ingestion pipeline
* What to remove from retrieval/orchestration logic
* What to remove from Admin UI
* How to eliminate orphaned logic and dead routes
* How to verify clean removal

---

## 5. Admin UI Cleanup Plan

Specify:

* How to safely remove directory entity management UI
* How to adjust navigation and sidebar items
* How to prevent broken routes or links
* How to preserve admin panel stability

---

## 6. Retrieval Accuracy Validation Plan

Define:

* Test categories for directory-related queries
* Precision expectations
* How to validate grounding reliability
* How to detect hallucination increases
* How to measure ranking consistency
* How to validate enumeration queries (e.g., “List all chairpersons”)

---

## 7. Risk Assessment and Mitigation

Identify:

* Retrieval degradation risks
* Formatting pitfalls in PDF ingestion
* Chunking problems
* Performance impacts on Raspberry Pi
* Edge cases in directory queries

Provide mitigation strategies.

---

## 8. Post-Migration Architecture Description

Describe what the simplified architecture will look like after removal.

The target architecture must have:

* A single unified ingestion pipeline
* A single FAISS-based retrieval pathway
* No structured directory entity subsystem
* Reduced architectural complexity
* Clear separation of concerns
* Improved maintainability

---

# Constraints

* Do not redesign the entire RAG system.
* Do not introduce new databases or technologies.
* Keep the solution aligned with the current FAISS-based architecture.
* Focus on simplification and architectural cleanliness.
* Preserve system stability.

---

# Deliverable

Produce a structured, phased architectural plan with clear sequencing, risk analysis, and rationale.

This is a high-level systems plan, not code.