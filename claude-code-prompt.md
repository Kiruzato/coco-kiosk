You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The kiosk UI is available at:

```
http://localhost:8000
```

The **Conversation Panel** (where chat messages appear) is currently scrollable **only via the scrollbar**.

Previously, swipe scrolling was attempted specifically for **touchscreen devices**, but the implementation did **not work during testing**.

---

# New Direction

Instead of implementing swipe scrolling specifically for **touchscreen input**, implement a **general swipe/drag scrolling behavior** for the **Conversation Panel**.

The idea is that the user should be able to:

* click/touch the conversation panel
* **drag up or down**
* and the panel scrolls accordingly.

This behavior should work with:

* mouse dragging
* touch swiping
* trackpad gestures

without depending on device-specific touchscreen logic.

---

# Objective

Implement **drag/swipe scrolling behavior for the Conversation Panel** that works **generally across input types**, including:

* mouse
* touchscreen
* trackpad.

The goal is to make the conversation panel behave similarly to a **mobile chat interface**, where the user can scroll through messages by dragging the content.

---

# Scope

The drag/swipe scrolling behavior must apply **only to the Conversation Panel**.

It must **not affect**:

* advertisement panel
* headers
* admin panels
* other UI components.

Only the **chat conversation container** should support this behavior.

---

# Implementation Guidelines

Implement the scrolling in a **general input-friendly way**.

Possible approaches include:

* enabling proper native scroll behavior on the container
* implementing controlled drag-to-scroll behavior using pointer events or similar mechanisms.

Avoid solutions that are **specific only to touchscreen APIs**.

Prefer solutions that work across **multiple input types**.

Ensure the implementation does not conflict with:

* message interaction
* input field focus
* other UI components.

---

# Behavior Requirements

Users should be able to:

* drag/swipe **upward** to scroll down through older messages
* drag/swipe **downward** to scroll toward newer messages.

Scrolling should feel:

* smooth
* responsive
* natural.

The **existing scrollbar must remain functional**.

---

# Code Quality Requirements

While implementing this change:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* keep the scrolling logic isolated to the conversation panel
* avoid overly complex gesture handling.

Prefer **clean and maintainable implementation**.

---

# Validation

Verify that:

* dragging or swiping on the conversation panel scrolls messages
* the behavior works with **mouse, touchscreen, and trackpad**
* the scrollbar still works normally
* no other UI components are affected.

---

# Goal

Enable **general drag/swipe scrolling for the Conversation Panel**, allowing users to navigate chat messages naturally without relying solely on the scrollbar, while maintaining compatibility across different input devices.
