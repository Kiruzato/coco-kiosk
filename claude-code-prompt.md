You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The kiosk UI is available at:

```id="9xftjq"
http://localhost:8000
```

This system runs on a **touchscreen monitor connected to the Raspberry Pi**.

---

# Current Behavior

The **Conversation Panel** (where chat messages appear) is currently scrollable **only via the scrollbar**.

This works for mouse interaction but is **not convenient for touchscreen users**.

---

# Objective

Enable **touch swipe scrolling** for the **Conversation Panel** so that users can scroll the conversation by **swiping up and down on the screen**.

This behavior must be optimized for the **Raspberry Pi touchscreen monitor**.

---

# Scope

The swipe scrolling behavior must apply **only to the Conversation Panel**.

It must **not affect other UI sections**, including:

* advertisement panel
* headers
* admin panels
* other scrollable containers.

Only the **chat conversation container** should respond to swipe gestures for scrolling.

---

# Expected Behavior

Users should be able to:

* swipe **up** to scroll down through older messages
* swipe **down** to scroll back toward newer messages.

The scrolling must feel **natural and smooth**, similar to typical mobile chat applications.

The existing **scrollbar functionality must remain intact**.

---

# Implementation Guidelines

When implementing this:

* ensure the container properly supports **touch scrolling**
* configure CSS and container properties appropriately (e.g., overflow behavior and touch scrolling settings)
* avoid implementing unnecessary heavy JavaScript scroll handlers unless required.

Prefer **native browser scrolling behavior** whenever possible.

Ensure the implementation works reliably with:

* Chromium kiosk mode
* Raspberry Pi touchscreen input.

---

# Code Quality Requirements

While implementing this feature:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* avoid introducing scroll conflicts with other UI elements
* keep the scrolling logic clean and maintainable.

---

# Validation

Verify that:

* the conversation panel scrolls smoothly using **touch swipe gestures**
* scrolling works both **upward and downward**
* the scrollbar still functions normally
* other UI components are **not affected by swipe scrolling**
* the feature works reliably on the **Raspberry Pi touchscreen environment**.

---

# Goal

Enable **smooth swipe-based scrolling for the conversation panel**, allowing touchscreen users to navigate chat messages naturally without relying on the scrollbar.
