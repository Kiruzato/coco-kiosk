You are working on the existing CoCo Campus RAG Chatbot codebase. Your task is to implement a configurable system that allows administrators to control the visibility of developer/debug information in chatbot response bubbles.

Your implementation must follow industry best practices, maintain architectural consistency, and integrate cleanly into the existing system without breaking or redesigning unrelated functionality.

---

# Core Objective

Currently, chatbot response bubbles include additional diagnostic and retrieval-related information, such as:

* Confidence level (example: `CONFIDENCE: HIGH`, `MEDIUM`, `LOW`)
* Score value (example: `92.69999694824219 / 100`)
* Sources section, including document names and metadata references

Example:

```
CONFIDENCE: HIGH
Score: 92.69999694824219 / 100

Sources:
Columban_College_Barretto_Campus_Directory_RAG_Knowledge_Base.pdf - Description: Engineering Dean office.
Columban_College_Barretto_Campus_Directory_RAG_Knowledge_Base.pdf - General Information
Columban_College_Barretto_Campus_Directory_RAG_Knowledge_Base.pdf - Entity ID: SP106_DEAN
...
```

This information is useful for debugging and development, but it should not always be visible to end users.

I want administrators to be able to control whether this developer/debug information is visible or hidden.

This control must be accessible from the existing Admin interface, specifically under the Developer Settings section:

```
http://localhost:8000/admin#developer
```

---

# Functional Requirements

## Separate Developer Visibility Toggle

Provide a dedicated toggle in the Developer Settings section that controls the visibility of the following response metadata:

* Confidence level
* Score value
* Sources section

This toggle must be separate and independent from the existing Debug Panel toggle.

It must NOT reuse, override, or be combined with the Debug Panel toggle. These are two distinct controls with different purposes.

The Debug Panel toggle must continue to function independently as it currently does.

The new toggle must specifically and only control the visibility of confidence, score, and sources in chatbot response bubbles.

---

## Developer Settings Persistence

The visibility setting must:

* Persist across page reloads
* Persist across system restarts
* Be stored using the system’s existing settings persistence mechanism
* Be reliably retrievable by both backend and frontend components as needed

---

## Chatbot Response Behavior

When the developer visibility toggle is enabled:

* Confidence, score, and sources must be displayed as they currently are.

When the developer visibility toggle is disabled:

* Confidence, score, and sources must not be shown in chatbot response bubbles.
* Only the main assistant response content must be visible.

The retrieval pipeline, scoring logic, and response generation must continue functioning normally regardless of visibility settings.

This feature only controls display visibility, not internal computation.

---

# System Integration Requirements

The implementation must integrate cleanly into the existing Admin Developer Settings system.

It must ensure:

* Proper separation between Debug Panel functionality and response metadata visibility control
* Clear separation between backend logic and frontend rendering logic
* Dynamic control of response metadata visibility based on administrator settings
* No disruption to retrieval, scoring, grounding, or response generation systems
* No regression in existing chatbot functionality

Frontend rendering must respect the administrator-configured visibility setting dynamically.

---

# Architectural and Engineering Requirements

Follow professional software engineering practices and industry standards.

This includes:

* Proper modularization of developer settings logic
* Maintaining clear separation between system configuration and UI presentation
* Avoiding hardcoded display logic
* Ensuring maintainability, extensibility, and clarity
* Reusing and extending existing developer settings architecture patterns appropriately

You may refactor related parts of the system if necessary to maintain architectural clarity and consistency, but do not redesign unrelated subsystems.

---

# UX and Behavior Expectations

Administrator workflow:

* Administrator opens the Admin interface
* Administrator navigates to Developer Settings
* Administrator sees a dedicated toggle specifically for response metadata visibility
* Administrator enables or disables this toggle
* Changes persist and apply immediately

User workflow:

* User interacts with chatbot
* Response bubbles display either full developer metadata or only user-facing response content, depending on the administrator’s configured visibility setting

---

# Quality Expectations

Your implementation must be:

* Clean
* Modular
* Robust
* Maintainable
* Architecturally consistent
* Production-quality

Avoid shortcuts, tightly coupled logic, or hardcoded visibility behavior.

Favor clarity, configurability, and correctness.

---

# Implementation Approach

Before implementing, analyze how confidence, score, and sources are currently generated, stored, and rendered.

Extend the developer settings system to include a new, separate visibility control specifically for response metadata.

Ensure that chatbot response rendering dynamically respects this setting while preserving all existing retrieval and scoring functionality.

Do not remove or disable the underlying metadata generation—only control its visibility in the UI.
