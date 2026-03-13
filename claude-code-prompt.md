You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The kiosk UI is available at:

```
http://localhost:8000
```

The system runs on a **touchscreen monitor connected to a Raspberry Pi**.

---

# Background

Previously, swipe scrolling was requested for the **Conversation Panel** so that users can scroll through messages by **swiping up and down on the touchscreen**, similar to mobile chat apps.

Claude attempted to implement this feature.

However, after testing on the **Raspberry Pi touchscreen**, the swipe scrolling **does not work**.

The conversation panel still only scrolls via the **scrollbar**, and swipe gestures do nothing.

---

# Objective

Investigate why the **swipe scrolling implementation is not working**, and fix it so that **touch swipe gestures properly scroll the conversation panel**.

---

# Investigation Requirements

Do not blindly reimplement swipe scrolling.

First determine **why the current implementation fails**.

Check the following areas:

### 1. CSS configuration of the conversation container

Verify whether the container properly supports touch scrolling.

Check properties such as:

* overflow settings
* height constraints
* touch scrolling behavior
* scroll container configuration.

Ensure the container actually allows **touch-driven scrolling**.

---

### 2. Touch event handling

Determine whether the implementation attempted to use:

* native scrolling
* JavaScript touch events.

If JavaScript was used, verify that:

* touchstart / touchmove events are actually firing
* event handlers are not blocked by other UI layers.

---

### 3. Scroll blocking from other UI settings

Check whether other UI configurations are interfering with swipe scrolling, such as:

* `preventDefault()` on touch events
* CSS rules disabling touch behavior
* text selection or pointer settings
* overlays or parent containers blocking the scroll.

---

### 4. Chromium kiosk touchscreen behavior

Since this runs on **Chromium in kiosk mode on Raspberry Pi**, verify whether the current implementation is compatible with:

* Chromium touch input handling
* Raspberry Pi touchscreen drivers.

Prefer **native scrolling behavior** rather than complex JavaScript gesture logic if possible.

---

# Required Fix

After identifying the root cause, implement a **working swipe scrolling solution** for the **Conversation Panel only**.

The fix must ensure that:

* users can scroll the conversation by **swiping up and down**
* scrolling feels **smooth and natural**
* the existing scrollbar continues to work
* the behavior only applies to the **conversation panel**, not the entire page.

---

# Implementation Guidelines

Prefer **native browser scrolling** instead of heavy custom gesture handling.

Ensure the conversation container is correctly configured as a **scrollable touch container**.

Avoid unnecessary JavaScript solutions if proper CSS configuration can achieve the behavior.

---

# Code Quality Requirements

While fixing this:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* avoid introducing fragile gesture code
* ensure the solution remains **maintainable and efficient**.

---

# Validation

Verify that:

* the conversation panel scrolls when users **swipe up or down**
* the behavior works on the **Raspberry Pi touchscreen**
* the scrollbar still functions
* other UI panels are **not affected by swipe scrolling**
* scrolling feels **smooth and responsive**.

---

# Goal

Ensure the **Conversation Panel supports swipe-based scrolling on the Raspberry Pi touchscreen**, allowing users to navigate chat messages naturally without relying on the scrollbar.
