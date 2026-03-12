You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The web application runs at:

```
http://localhost:8000/
```

Holding the **Fullscreen button for 5 seconds** opens the **Kiosk Admin Panel**.

Claude previously implemented:

* a **lightweight built-in keyboard**
* a **WiFi configuration function** inside the Kiosk Admin Panel.

Inside the WiFi configuration screen, there is a **Back button** that returns the admin to the **main Kiosk Admin Panel**.

---

# Problem

When the admin changes the WiFi connection and then presses the **Back button** to return to the Kiosk Admin Panel, the **Connected WiFi label** in the Admin panel **does not refresh**.

This means the displayed WiFi network may be outdated even though the connection has already changed.

---

# Objective

Modify the system so that **when the Back button is clicked in the WiFi configuration screen**, the **Connected WiFi label in the Kiosk Admin Panel refreshes automatically** to reflect the **current active WiFi connection**.

---

# Expected Behavior

After returning from the WiFi configuration screen:

* the Admin Kiosk Panel should **re-query the current WiFi connection**
* the **Connected WiFi label should update immediately**
* the displayed network must reflect the **actual current connection state**.

The refresh should occur **every time the admin navigates back from WiFi configuration**, not only after a successful connection.

---

# Implementation Guidelines

When implementing the solution:

* ensure the WiFi status is retrieved from the **actual system network state** (e.g., via backend endpoint or existing WiFi status logic)
* avoid duplicating logic that already exists for checking WiFi status
* reuse existing API endpoints if possible.

The refresh should be triggered by the **Back button navigation event**.

---

# Code Quality Requirements

Follow **industry-standard best practices**:

* apply **proper refactorization and modularization**
* avoid duplicating WiFi status logic
* keep UI state updates clean and predictable
* ensure the refresh mechanism does not introduce unnecessary API calls or performance issues.

---

# Validation

After implementing the change, verify that:

* changing WiFi networks updates the **Connected WiFi label correctly**
* returning to the Admin panel via the **Back button always refreshes the label**
* no UI regressions occur in the Kiosk Admin Panel
* the lightweight keyboard and other kiosk features continue to function normally.

---

# Goal

Ensure that the **Connected WiFi label in the Kiosk Admin Panel always reflects the real network state**, especially after navigating back from the WiFi configuration screen.
