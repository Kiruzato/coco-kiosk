You are working on the **CoCo Campus RAG Chatbot** project running on **Raspberry Pi OS in kiosk fullscreen mode**.

The web app runs at:

```
http://localhost:8000/
```

---

# Problem

A **lightweight built-in keyboard** was implemented to solve the issue where the **Raspberry Pi OS virtual keyboard does not appear in fullscreen mode**.

However, the **built-in keyboard is currently not working**.

Claude previously attempted to fix it, but the keyboard **still does not function**.

---

# Observed Behavior

Here are some observations that might help identify the problem:

1. When focusing on the **chat input field**, the **panel where the input field belongs moves slightly downward**.

2. The keyboard **does not appear usable in the UI**, even though the feature was implemented.

3. I suspect that the keyboard **might actually be spawning outside the fullscreen viewport**, similar to how the **Admin panel appears outside fullscreen when holding the fullscreen button for 5 seconds**.

This suggests the keyboard **may exist in the DOM but is rendered outside the visible fullscreen container**.

These observations may or may not be the exact cause, but they may help guide debugging.

---

# Objective

Fix the **built-in keyboard implementation so it works correctly in fullscreen kiosk mode**.

The keyboard must:

* appear correctly in the UI
* remain inside the visible fullscreen viewport
* send characters to the chat input field
* work reliably for typing messages.

---

# Investigation Requirements

Before modifying code, investigate the implementation carefully.

Check:

### 1. Keyboard Rendering

Verify whether the keyboard is:

* correctly inserted into the DOM
* visible but positioned outside the viewport
* hidden due to CSS positioning issues
* rendered inside the correct container.

Investigate CSS rules such as:

* `position`
* `z-index`
* `overflow`
* `transform`
* `viewport height`
* fullscreen container boundaries.

---

### 2. Fullscreen Container Behavior

Investigate how the kiosk UI handles fullscreen layout.

Check whether:

* the keyboard is attached to the wrong DOM container
* the keyboard is appended outside the fullscreen root element
* CSS clipping or overflow hides the keyboard.

---

### 3. Focus Behavior

Investigate the **input focus behavior**:

* why the input panel shifts downward when focused
* whether layout resizing pushes the keyboard out of view
* whether mobile-style keyboard adjustments are interfering.

---

### 4. Event Handling

Verify that:

* keyboard keys correctly send characters
* the input field receives inserted text
* keyboard events are bound properly.

---

# Implementation Requirements

After identifying the root cause, fix the keyboard so that:

* it renders **inside the fullscreen viewport**
* it remains visible above the UI
* it types correctly into the input field
* it works reliably in fullscreen kiosk mode.

Avoid temporary or superficial fixes.

The solution should **correct the root layout/rendering problem**.

---

# Code Quality Requirements

While implementing the fix:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* keep keyboard logic isolated from unrelated UI components
* maintain clean and maintainable code.

Avoid introducing unnecessary complexity.

---

# Validation

After implementing the fix, verify that:

* the keyboard appears when the input field is focused
* the keyboard is visible within the fullscreen viewport
* keys correctly insert characters into the input field
* the keyboard works consistently in fullscreen kiosk mode
* the solution works after **Raspberry Pi reboot**.

---

# Goal

Ensure that the **built-in web keyboard functions reliably in fullscreen kiosk mode**, allowing users to type into the chatbot input field even when the Raspberry Pi OS virtual keyboard cannot be used.
