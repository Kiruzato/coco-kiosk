You are working on the existing CoCo Campus RAG Chatbot codebase. Your task is to improve the behavior and architecture of the Response Metadata toggle and the Debug Panel system.

Your implementation must follow industry best practices, maintain architectural consistency, and avoid introducing technical debt.

---

# Core Objectives

There are two main issues to address:

---

## 1. Response Metadata Toggle Requires Page Refresh

Currently, when toggling the **Response Metadata visibility** setting in Developer Settings:

* The change does not take effect immediately.
* I must manually refresh the page to see the effect.

However, the **Debug Panel toggle** applies changes immediately without requiring a page refresh.

### Required Behavior

The Response Metadata toggle must:

* Apply changes immediately without requiring page refresh.
* Dynamically update the UI in real time.
* Behave consistently with how the Debug Panel toggle works.
* Not require reloading the entire chatbot interface.

The toggle must control visibility dynamically for:

* Confidence
* Score
* Sources
* Knowledge-origin labels
* Any related response metadata elements

This must affect both existing visible messages (if applicable) and new responses rendered after the toggle.

---

## 2. Debug Panel Not Triggering for Some Queries

I noticed that certain questions, such as:

```
where is engineering dean office?
```

do not trigger the Debug Panel display, even when Debug Panel is enabled.

This indicates inconsistency in how the Debug Panel is activated or rendered.

### Required Improvements

* Ensure the Debug Panel activates consistently whenever it is enabled.
* The Debug Panel must not depend on specific query types or retrieval paths.
* It must work reliably for all question types, including directory-related queries.
* Investigate and fix any logic gaps causing Debug Panel not to render.

---

# Refactor and Modularization Requirement

If necessary, perform proper refactorization and modularization of the Debug Panel and Response Metadata systems to ensure:

* Clean separation of concerns
* Unified and centralized rendering logic
* Consistent state management
* No duplicated toggle handling logic
* Clear abstraction between configuration state and UI rendering
* Proper reactive or event-driven update behavior

Avoid patching individual display conditions.

If needed, restructure how developer settings are propagated to frontend rendering logic so that both:

* Debug Panel
* Response Metadata visibility

are handled through a clean and consistent state management mechanism.

---

# Important Constraints

* Do not redesign the overall chatbot architecture.
* Do not modify unrelated subsystems.
* Do not break RAG, retrieval, or response generation.
* Maintain existing features.
* Preserve separation between Debug Panel toggle and Response Metadata toggle.
* Ensure both toggles operate independently but consistently.

---

# Expected Outcome

After implementation:

* Toggling Response Metadata visibility applies immediately without page refresh.
* Debug Panel reliably appears when enabled, regardless of query type.
* Developer settings behave consistently and predictably.
* Codebase is cleaner, more modular, and easier to maintain.
* No regressions in chatbot functionality.

---

# Implementation Approach

Before implementing, analyze:

* How Debug Panel toggle currently propagates state.
* How Response Metadata visibility is currently applied.
* Where rendering decisions are made in the frontend.

Refactor the system to ensure consistent, reactive behavior and centralized rendering control.

Favor architectural clarity over quick fixes.