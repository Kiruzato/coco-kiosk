You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The web application runs at:

```
http://localhost:8000/
```

Holding the **Fullscreen button for 5 seconds** opens the **Kiosk Admin Panel**.

Claude previously implemented:

* a **lightweight built-in keyboard**
* a **WiFi configuration interface** in the Kiosk Admin Panel.

Inside the WiFi configuration screen there is a **Scan Networks** function that displays the list of available WiFi networks.

---

# Task 1 — Investigate the Scan Networks Behavior

I want you to determine how the **Scan Networks** feature currently works.

Specifically, investigate whether the system:

1. **Performs a real WiFi scan each time the button is clicked**, or
2. **Only retrieves cached results from the previous scan performed by the system**.

Check:

* the backend logic handling the scan request
* the system command used (`nmcli`, `iw`, etc.)
* whether a **fresh scan is explicitly triggered**.

After investigating, confirm which behavior is currently implemented.

If the system is **only retrieving cached results**, modify the implementation so that the **Scan Networks button performs a proper active WiFi scan** before retrieving the network list.

The goal is for the list to reflect the **current available networks** rather than stale results.

---

# Task 2 — Add Button Cooldown

Implement a **5-second cooldown** for the **Scan Networks** button.

Requirements:

* After the button is clicked, it should be **disabled for 5 seconds**.
* During the cooldown, the button should **visually indicate it is disabled**.
* After 5 seconds, the button should become **clickable again**.
* The cooldown should prevent **rapid repeated scans** that could overload the system.

The cooldown must be handled **cleanly in the UI layer**, while still allowing backend validation if needed.

---

# Code Quality Requirements

While implementing the changes:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* avoid duplicating network scanning logic
* ensure backend commands are executed **safely and securely**
* keep the UI behavior **predictable and maintainable**.

---

# Validation

Verify that:

* clicking **Scan Networks** performs an **actual WiFi scan**
* the network list reflects **currently available networks**
* the **5-second cooldown works correctly**
* the cooldown prevents repeated scanning
* no regressions occur in the WiFi configuration UI or the Kiosk Admin Panel.

---

# Goal

Ensure the **Scan Networks feature performs a proper real-time WiFi scan** and prevent excessive scanning by implementing a **5-second cooldown on the Scan Networks button**.
