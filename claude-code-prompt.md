You are working on the **CoCo Campus RAG Chatbot** project.

This task concerns the **Kiosk UI** located at:

```
http://localhost:8000/
```

---

# Current Behavior

The **Voice Input button** behaves correctly based on system availability:

* When **Voice Input is available**, the button is **clickable**.
* When **Voice Input is not available**, the button is **disabled / not clickable**.

This availability depends on the **voice service status**.

---

# Required Enhancement

I want the **New Conversation button** to also **refresh the Voice Input button’s usability state**.

Meaning:

When the **New Conversation button is clicked**, the system should **re-check whether Voice Input is available or unavailable**, and update the **Voice Input button state accordingly**.

This ensures that if the **voice system becomes available or unavailable during runtime**, the UI can refresh its state without requiring a page reload.

---

# Expected Behavior

When the **New Conversation button is clicked**:

1. The system resets the conversation (existing behavior).
2. The system **re-checks the voice service availability**.
3. The **Voice Input button state updates accordingly**:

   * enabled if voice input is available
   * disabled if voice input is unavailable.

---

# Implementation Requirements

Do **not implement this using page reloads**.

Instead:

* trigger a **proper voice availability check**
* update the Voice Input button state programmatically
* reuse existing logic used during initial page load (if applicable).

Avoid duplicating logic.

If the voice availability logic exists in a function, **reuse or refactor it into a reusable method**.

---

# Code Quality Requirements

While implementing this change:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* avoid duplicating voice availability logic
* ensure the UI state update is clean and maintainable.

---

# Validation

After implementing the change:

Verify that:

* clicking **New Conversation** refreshes the **Voice Input button availability state**
* the button correctly switches between **enabled and disabled**
* no page reload occurs
* existing New Conversation functionality remains intact
* no UI regressions occur.

---

# Goal

Ensure that the **Voice Input button state remains accurate during runtime** and can be refreshed using the **New Conversation button without requiring a page reload**.
