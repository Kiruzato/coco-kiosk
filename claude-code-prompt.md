You are working on the **CoCo Campus RAG Chatbot** project.

This task concerns the **Developer Settings panel** located at:

`http://localhost:8000/admin#developer`

Specifically the **Response Metadata Toggle**.

---

# Problem

The **Response Metadata Toggle** currently works **only for typewritten queries**.

However, when using **voice queries**, the metadata visibility toggle **does not work**.

This means the toggle behavior is **inconsistent between text and voice query flows**.

---

# Objective

Fix the system so that the **Response Metadata Toggle behaves consistently for both query types**:

* typewritten queries
* voice queries

The toggle must correctly control the visibility of response metadata regardless of the input method.

---

# Investigation

First, identify why the metadata toggle is not applied to voice responses.

Investigate the full response flow:

Text Query Flow:

```
UI → chat endpoint → response assembly → UI rendering
```

Voice Query Flow:

```
STT → voice orchestrator → chat processing → TTS → UI rendering
```

Determine where the **metadata visibility setting is lost or ignored** in the voice pipeline.

Possible causes may include:

* different response assembly logic
* missing metadata flag propagation
* separate rendering logic
* bypassed response formatting layer

---

# Required Fix

Ensure that:

* the **same metadata visibility logic** is applied to both text and voice responses
* the toggle setting from `http://localhost:8000/admin#developer` is respected in **both pipelines**
* metadata rendering logic is **centralized rather than duplicated**

Avoid implementing separate or duplicate logic for voice queries.

---

# Code Quality Requirements

While implementing the fix:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* avoid code duplication between voice and text pipelines
* keep response formatting logic **consistent and maintainable**

If necessary, refactor response assembly so that **both query types share the same metadata handling layer**.

---

# Validation

After implementing the fix:

Confirm that:

* the Response Metadata Toggle works correctly for **typewritten queries**
* the Response Metadata Toggle works correctly for **voice queries**
* metadata visibility is **consistently controlled by the toggle**
* no regressions occur in either pipeline.

---

Focus on **correcting the underlying response pipeline behavior**, not just masking the issue at the UI level.
