You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The main kiosk interface is available at:

```id="j9p21v"
http://localhost:8000
```

---

# Background

Swipe / drag scrolling was implemented for the **Conversation Panel** so users can scroll through chat messages by swiping or dragging the screen.

This feature **now works correctly for scrolling**.

However, a new problem appeared.

---

# Problem

The swipe scrolling implementation **prevents the FAQ questions from opening**.

The FAQ section is located near the **top of the conversation panel**, and each FAQ question is supposed to expand when clicked/tapped.

Currently:

* tapping a FAQ question **does nothing**
* the swipe/drag scrolling behavior **intercepts the interaction**
* the FAQ toggle action is **blocked by the scrolling logic**.

---

# Objective

Fix the interaction conflict so that **both features work correctly**:

1. Swipe / drag scrolling must continue working in the **Conversation Panel**.
2. FAQ questions must still be **clickable/tappable and expandable**.

---

# Investigation Requirements

Investigate how the swipe scrolling behavior was implemented.

Check whether the implementation:

* intercepts pointer / touch events globally
* prevents default click behavior
* blocks event propagation
* captures events on the container before they reach the FAQ elements.

Determine exactly **why FAQ click/tap events are not firing**.

---

# Required Fix

Adjust the implementation so that:

* swipe scrolling continues to work for scrolling
* FAQ elements can still receive **click or tap events**.

Possible strategies may include:

* allowing events to propagate when the gesture is a **tap rather than a drag**
* excluding FAQ elements from the drag handler
* detecting gesture movement thresholds before activating drag scrolling.

The solution should **not remove swipe scrolling**.

---

# Implementation Guidelines

The solution must:

* preserve smooth swipe/drag scrolling
* preserve FAQ click/tap functionality
* avoid fragile event hacks
* maintain clean event handling logic.

Prefer a **gesture detection approach** that distinguishes between:

* **tap (FAQ interaction)**
* **drag (scrolling)**.

---

# Code Quality Requirements

While implementing the fix:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* keep event-handling logic clean and maintainable
* avoid complex or brittle gesture logic.

---

# Validation

Verify that:

* swipe scrolling still works in the conversation panel
* FAQ questions can be opened normally
* tapping a question expands its answer
* dragging still scrolls the conversation
* both features work smoothly on the **Raspberry Pi touchscreen environment**.

---

# Goal

Ensure that **swipe scrolling and FAQ interaction coexist properly**, allowing users to scroll the conversation panel while still being able to **tap FAQ questions to expand their answers**.
