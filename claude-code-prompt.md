You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The web application runs at:

```
http://localhost:8000/
```

Holding the **Fullscreen button for 5 seconds** opens the **Kiosk Admin Panel**.

Claude previously implemented:

* a **lightweight built-in keyboard**
* a **WiFi configuration interface** inside the Kiosk Admin Panel.

Inside the WiFi configuration screen there is a **Scan Networks** function used to display available WiFi networks.

---

# Problem

When I enable my **phone hotspot** and immediately click **Scan Networks**, the hotspot **does not appear in the list**.

However:

* the hotspot **is confirmed to be available**
* other devices **can detect it immediately**
* the hotspot **only appears after several minutes when scanning again**.

Therefore the issue is **not that the hotspot is unavailable**, but that the system **is not detecting it immediately**.

---

# Objective

Investigate why the **Scan Networks function fails to detect newly available WiFi networks immediately**, and fix the issue so that **new networks appear right away when scanning**.

---

# Investigation Requirements

Perform a proper investigation before modifying anything.

Determine:

### 1. How WiFi scanning is implemented

Check:

* what backend command is used (`nmcli`, `iw`, etc.)
* whether the command **forces a fresh scan** or just retrieves cached results.

For example, verify whether the system is using something like:

```
nmcli device wifi list
```

instead of

```
nmcli device wifi rescan
```

or an equivalent forced scan.

---

### 2. NetworkManager scan caching behavior

NetworkManager often **caches scan results** for a period of time.

Determine whether the current implementation is simply reading **cached scan results**, which would explain why the hotspot only appears later.

---

### 3. Scan timing and hardware behavior

Check if:

* the WiFi adapter requires a **manual rescan command**
* the system needs a **short delay after triggering a scan**
* the scan command is executed **before results are ready**.

---

# Required Fix

Modify the implementation so that **Scan Networks triggers a proper real-time WiFi scan**.

The solution should:

1. Force a **fresh WiFi scan**.
2. Wait until scan results are available.
3. Then retrieve the updated list of networks.

The goal is that **newly created networks (such as phone hotspots) appear immediately after scanning**.

---

# Code Quality Requirements

While implementing the fix:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* avoid duplicating WiFi scanning logic
* keep system command execution secure
* ensure backend logic is clean and maintainable.

---

# Validation

After implementing the fix, verify that:

* enabling a **new WiFi network (such as a phone hotspot)** and clicking **Scan Networks** immediately detects it
* network lists refresh correctly
* the feature works reliably on **Raspberry Pi OS**
* no regressions occur in the WiFi configuration UI.

---

# Goal

Ensure that the **Scan Networks feature performs a proper real-time WiFi scan**, allowing newly available networks (such as phone hotspots) to appear **immediately after scanning**, without requiring several minutes of waiting.
