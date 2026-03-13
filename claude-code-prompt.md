Here is a **clear, intent-focused prompt** for **Claude Code agent Opus 4.6**.

---

# Prompt for Claude Code Agent — Opus 4.6

You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The main kiosk interface is available at:

```
http://localhost:8000
```

This interface is used in **kiosk mode with a touchscreen**.

---

# Problem

When users interact with the kiosk (tapping, dragging, or touching the screen), **text highlighting sometimes appears**.

This creates a **messy and distracting UI experience**, which is undesirable for a kiosk environment.

For example:

* touching or dragging on the screen highlights text
* this leaves visible blue selection highlights across the interface.

---

# Objective

Disable **text highlighting/selection behavior** across the kiosk interface to provide a **clean kiosk experience**.

Users should **not be able to highlight text accidentally while interacting with the screen**.

---

# Requirements

Text selection must be disabled for the kiosk UI.

This should apply to:

* general page text
* UI labels
* buttons
* advertisement text
* chatbot messages
* FAQ content
* header and panels.

However, **input fields must remain selectable**, including:

* the chatbot **text input field**
* any other form inputs where text entry is required.

Users must still be able to:

* place the cursor
* type text
* edit typed queries.

---

# Implementation Guidelines

Implement this using proper **CSS-based text selection control**.

For example:

* disable selection globally for non-input UI components
* allow selection only for **input fields and text areas**.

Ensure the solution works properly for:

* **touch interactions**
* **mouse interactions**
* **Chromium kiosk mode**.

Avoid JavaScript hacks for this unless necessary.

---

# Code Quality Requirements

While implementing the change:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* avoid scattering style overrides across multiple components
* centralize the behavior in the **global UI stylesheet** where appropriate.

---

# Validation

Verify that:

* text can **no longer be highlighted accidentally**
* the kiosk UI remains visually clean during touch interaction
* **input fields still allow normal typing and cursor placement**
* no UI functionality is broken.

---

# Goal

Ensure the **kiosk interface prevents accidental text highlighting**, while still allowing normal interaction with **text input fields**, resulting in a cleaner and more professional kiosk experience.
