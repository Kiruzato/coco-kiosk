You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The web application runs at:

```
http://localhost:8000/
```

The chatbot supports:

* **Voice input**
* **Typewritten query input**

---

# Background

Previously I asked for a loading feedback system that would replace the voice-processing label:

```
... Processing Audio...
```

with:

```
CoCo is thinking...
```

and apply it to both **voice input** and **typed queries**.

However, the implementation was **incorrect**.

---

# Problem With The Previous Implementation

The system implemented a **fullscreen overlay** with the "CoCo is thinking..." message that **blocks the entire screen**.

This is **not what I want**.

The correct behavior should instead **reuse the existing loading panel that appears below the input panel**.

Additionally, the implementation **failed to locate the actual "Processing Audio..." label**, even though it clearly appears when using voice input.

---

# Objective

Fix the loading feedback implementation correctly.

---

# Step 1 — Locate the Existing "Processing Audio..." Panel

Search the codebase for where this label originates:

```
... Processing Audio...
```

It appears **below the input panel**, specifically under the area containing:

* Voice input button
* Text input field
* Send button

You must **find the actual code responsible for displaying this panel**.

Do **not assume the location** — search the codebase.

---

# Step 2 — Modify the Existing Panel (Do NOT Create Overlays)

Once found, modify the **existing loading panel**.

Requirements:

1. Replace the label:

```
... Processing Audio...
```

with:

```
CoCo is thinking...
```

2. Add a lightweight animation:

```
CoCo is thinking.
CoCo is thinking..
CoCo is thinking...
```

Then repeat continuously.

3. The animation must **stop automatically when the response arrives**.

4. The panel must remain **in its original position below the input panel**.

---

# Step 3 — Apply the Same Feedback to Typed Queries

Currently, typed queries **do not display any loading feedback**.

Modify the system so that when a **typewritten query is submitted**, the same loading panel appears.

Requirements:

* Use the **same panel used by voice input**
* Use the same **"CoCo is thinking..." animated text**
* Hide the panel once the chatbot response appears.

---

# Important Restrictions

Do NOT:

* create fullscreen overlays
* block the entire UI
* create duplicate loading panels
* implement a separate system for voice and typed queries.

Both input methods must **reuse the same loading feedback component**.

---

# Implementation Guidelines

Follow **industry-standard best practices**:

* apply proper **refactorization and modularization**
* reuse existing UI components instead of duplicating logic
* keep the animation lightweight (important for Raspberry Pi performance)
* ensure loading state is properly cleaned up when responses arrive.

---

# Validation

Verify that:

* the existing **Processing Audio panel is correctly located**
* it now displays **"CoCo is thinking..."**
* the animated dots cycle correctly
* the panel appears for **voice queries**
* the panel appears for **typed queries**
* the panel disappears once the response is received
* the UI is **not blocked by overlays**.

---

# Goal

Use the **existing loading panel below the input controls** and convert it into a **shared thinking indicator** displaying:

```
CoCo is thinking...
```

with animated dots, working consistently for both **voice input and typed queries**, without blocking the screen.
