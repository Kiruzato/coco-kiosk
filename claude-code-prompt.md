You are working on the **CoCo Campus RAG Chatbot** project running on **Raspberry Pi OS in kiosk mode**.

The web app runs at:

```
http://localhost:8000/
```

and normally operates in **fullscreen mode**.

---

# Current Situation

Previously, the system had a problem where the **Raspberry Pi virtual keyboard did not appear when the web app was in fullscreen mode**.

To solve this, you implemented a **lightweight built-in web keyboard** inside the web app.

However, **the built-in keyboard currently does not work**.

The keyboard either:

* does not appear
* appears but does not type into the input field
* or does not trigger correctly when the input field is focused.

---

# Important Context

After the keyboard implementation:

* I **only pulled the latest code changes**
* I **restarted the Raspberry Pi**
* I **did NOT run** the deployment script again:

```
WEB_APP/deploy/install_kiosk.sh
```

Because of this, the issue might be caused by either:

1. **Broken frontend code / keyboard implementation**
2. **Missing configuration that the install script should apply**
3. **A runtime issue related to kiosk mode or fullscreen behavior**

Your task is to **determine which of these is the real cause**.

---

# Objective

Investigate and **fix the built-in keyboard so it works correctly in fullscreen kiosk mode**.

The keyboard must allow users to **type into the chat input field while the web app is fullscreen**.

---

# Step 1 — Investigation

First determine the root cause.

Check:

### Frontend Implementation

Verify:

* keyboard UI rendering
* keyboard event handling
* key press handling
* input field binding
* focus handling
* keyboard visibility logic
* compatibility with fullscreen mode

Check whether:

* keyboard keys actually insert characters
* keyboard events target the correct input element
* keyboard container visibility logic is broken.

---

### Runtime / Deployment Requirements

Determine whether the keyboard implementation depends on:

* files created during `install_kiosk.sh`
* environment configuration
* system-level services.

If the keyboard requires changes from the deployment script, clearly identify them.

---

# Step 2 — Determine Deployment Requirement

If the keyboard requires **deployment configuration**, explain clearly:

* whether `install_kiosk.sh` must be run again
* what configuration step is required
* why the keyboard does not work without it.

If the deployment script is **not required**, fix the keyboard **directly in the codebase**.

---

# Step 3 — Fix the Implementation

Fix the keyboard so that it:

* appears correctly
* sends characters to the chat input field
* works reliably in fullscreen mode
* does not interfere with existing UI behavior.

Ensure keyboard input works with:

* normal typing
* backspace
* space
* enter / send message.

---

# Code Quality Requirements

While implementing the fix:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* keep the keyboard implementation **clean and maintainable**
* avoid tightly coupling keyboard logic with unrelated UI code
* avoid unnecessary complexity.

---

# Validation

After implementing the fix, verify that:

* the keyboard appears when needed
* keys correctly type into the chat input field
* the keyboard works in **fullscreen kiosk mode**
* the solution works after **Raspberry Pi reboot**
* the keyboard does not break existing UI behavior.

---

# Goal

Ensure that the **built-in web keyboard works reliably in fullscreen kiosk mode**, allowing users to type into the chatbot even when the Raspberry Pi OS virtual keyboard cannot be used.
