You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The web application runs at:

```
http://localhost:8000/
```

The chatbot supports two input modes:

1. **Voice input**
2. **Typewritten query input**

---

# Current Behavior

When using **voice input**:

* After recording finishes, a panel appears **below the input panel** (the area containing the voice button, text input field, and send button).
* This panel displays the label:

```
... Processing Audio...
```

This acts as a **loading indicator** while the system processes the request.

However, when using **typewritten queries**, there is **no loading feedback shown at all**.

This creates an **inconsistent user experience**.

---

# Objective

Improve the loading feedback system for both **voice input and typewritten queries**.

---

# Required Changes

### 1. Change the Loading Label

Replace the current label:

```
... Processing Audio...
```

with:

```
CoCo is thinking...
```

This message should be used **for both voice queries and typewritten queries**.

---

### 2. Add Animated Thinking Indicator

The label should animate using the following loop:

```
CoCo is thinking.
CoCo is thinking..
CoCo is thinking...
```

Then repeat continuously.

Example sequence:

```
CoCo is thinking.
CoCo is thinking..
CoCo is thinking...
CoCo is thinking.
CoCo is thinking..
...
```

The animation should run **until the response is received**.

---

### 3. Apply the Loading Indicator to Typed Queries

When a user submits a **typewritten query**:

* The same **loading panel** should appear
* The same **"CoCo is thinking..." animated label** should be displayed
* The indicator should remain visible **until the chatbot response is received**.

This ensures **consistent feedback for both input methods**.

---

# Implementation Guidelines

* Avoid duplicating logic between voice and text query flows.
* Use a **shared loading state mechanism** for both input types.
* Ensure the animation stops cleanly once a response is rendered.
* Prevent multiple loading panels from appearing simultaneously.

The loading indicator should be **lightweight and efficient**, since the kiosk runs on **Raspberry Pi hardware**.

---

# Code Quality Requirements

Follow **industry-standard best practices**:

* apply **proper refactorization and modularization**
* keep UI state management clean
* avoid duplicate loading logic
* ensure the solution is maintainable and predictable.

---

# Validation

Verify that:

* the label now displays **"CoCo is thinking..."**
* the animation cycles correctly (`.`, `..`, `...`)
* the loading indicator appears for **voice queries**
* the loading indicator appears for **typewritten queries**
* the indicator disappears once the response arrives
* no UI regressions occur.

---

# Goal

Provide a **consistent and clear loading feedback system** so that users always see **"CoCo is thinking..." with animated dots** whenever the chatbot is processing a request, regardless of whether the query was submitted via **voice or typing**.
