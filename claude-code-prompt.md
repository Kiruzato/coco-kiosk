You are working on the **CoCo Campus RAG Chatbot** project running on **Raspberry Pi OS in fullscreen kiosk mode**.

The web application runs at:

```
http://localhost:8000/
```

Holding the **Fullscreen button for 5 seconds** opens the **Kiosk Admin panel**.

---

# Problem

Inside the **Kiosk Admin panel**, there is a **password input field**.

A **custom lightweight keyboard** was implemented so users can type even in fullscreen mode.

The keyboard **does appear when the password field is focused**, but it **cannot be used**.

Observed behavior:

* The keyboard **visually appears on the screen**.
* However, **clicking the keys does nothing**.
* It appears that **a UI layer or overlay is blocking interaction with the keyboard**.

This suggests that a **screen layer, overlay, or container element is intercepting pointer events**, preventing interaction with the keyboard.

---

# Objective

Fix the UI layering so the **custom keyboard is fully usable inside the Kiosk Admin panel**.

The keyboard must:

* remain visible
* accept click/touch input
* correctly insert characters into the password field.

---

# Investigation Requirements

Investigate the layout and layering behavior when the **Kiosk Admin panel is active**.

Specifically check:

### 1. Overlay Layers

Determine whether the Kiosk Admin panel uses an overlay element such as:

* modal background
* screen blocker
* fullscreen container layer.

Check whether that overlay:

* covers the keyboard
* blocks pointer events
* intercepts clicks.

---

### 2. CSS Layering (z-index)

Check the CSS rules of the keyboard and surrounding elements:

* `z-index`
* `position`
* `pointer-events`
* container stacking context
* modal overlay behavior.

Verify whether the keyboard is being rendered **under another layer in the stacking order**.

---

### 3. DOM Placement

Verify where the keyboard is inserted in the DOM.

Check whether it is being appended:

* inside the admin modal
* inside a container that has `overflow:hidden`
* outside the interactive container.

The keyboard should be placed in a **layer where it can receive pointer events**.

---

# Required Fix

Adjust the UI structure so that:

* the keyboard is **above blocking layers**
* the keyboard **receives pointer events**
* the admin overlay does not intercept keyboard input.

Possible fixes may include:

* correcting `z-index` stacking
* modifying modal overlay structure
* disabling pointer blocking for the keyboard area
* placing the keyboard in a higher-level container.

However, avoid fragile hacks. Implement a **clean and maintainable solution**.

---

# Code Quality Requirements

While implementing the fix:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* keep keyboard logic reusable
* avoid hardcoded z-index values scattered throughout the code
* maintain clear layering rules for modal UI elements.

---

# Validation

After implementing the fix, verify that:

* the keyboard appears when the password field is focused
* keyboard keys are clickable
* characters correctly appear in the password input field
* the fix does not break the keyboard for the main chatbot input field
* the Kiosk Admin panel UI still behaves correctly.

---

# Goal

Ensure that the **custom keyboard inside the Kiosk Admin panel is fully interactive and usable in fullscreen kiosk mode**, without any UI layers blocking user interaction.
