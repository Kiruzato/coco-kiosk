You are working on the **CoCo Campus RAG Chatbot** project running on **Raspberry Pi OS in fullscreen kiosk mode**.

The web application runs at:

```
http://localhost:8000/
```

Holding the **Fullscreen button for 5 seconds** opens the **Kiosk Admin panel**.

---

# Problem

Inside the **Kiosk Admin panel**, there is a button:

```
Exit Fullscreen
```

However, the button **does not work correctly**.

Current behavior:

* Clicking **Exit Fullscreen** only **closes the Kiosk Admin panel**.
* It **does NOT actually exit fullscreen mode**.

Expected behavior:

* Clicking **Exit Fullscreen** should **exit the browser fullscreen mode**.
* The Kiosk Admin panel should then close normally after exiting fullscreen.

---

# Objective

Fix the **Exit Fullscreen button behavior** so that it correctly exits fullscreen mode.

The button must:

1. Exit fullscreen mode.
2. Close the Kiosk Admin panel.
3. Return the application to normal (non-fullscreen) browser mode.

---

# Investigation Requirements

Investigate how fullscreen mode is currently handled in the system.

Check:

* whether fullscreen is controlled through the **Fullscreen API** (`document.exitFullscreen()` / `requestFullscreen()`)
* whether the fullscreen state is managed through **custom UI logic**
* whether the Kiosk Admin panel is intercepting the click event.

Determine why the current button action **only closes the admin panel instead of exiting fullscreen**.

---

# Required Fix

Refactor the **Exit Fullscreen button logic** so that:

* it explicitly calls the **correct fullscreen exit method**
* the fullscreen exit is handled **before or together with closing the admin panel**
* the behavior works reliably across the kiosk UI.

Ensure the implementation handles cases where:

* the browser is currently in fullscreen
* the browser is not in fullscreen.

---

# Code Quality Requirements

While implementing the fix:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* avoid duplicating fullscreen control logic
* centralize fullscreen handling if necessary
* keep the UI logic clean and maintainable.

---

# Validation

After implementing the fix, verify that:

* clicking **Exit Fullscreen** exits fullscreen mode
* the Kiosk Admin panel closes afterward
* the application returns to normal browser view
* the fullscreen toggle button in the main UI still works correctly
* the fix does not introduce UI regressions.

---

# Goal

Ensure the **Exit Fullscreen button in the Kiosk Admin panel correctly exits fullscreen mode instead of only closing the admin panel**, restoring the expected kiosk control behavior.
