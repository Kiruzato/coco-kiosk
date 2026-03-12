You are working on the **CoCo Campus RAG Chatbot** project running on **Raspberry Pi OS in kiosk mode**.

The web application runs at:

```
http://localhost:8000/
```

Holding the **Fullscreen button for 5 seconds** opens the **Kiosk Admin Panel**.

A **WiFi configuration feature** was recently implemented in this panel so administrators can connect the Raspberry Pi to a WiFi network.

---

# Problem

When attempting to connect to a WiFi network through the Kiosk Admin Panel, the following error appears:

```
Error: Failed to add 'WiFi_name' connection: Insufficient privileges
```

This indicates that the backend process attempting to run the WiFi connection command **does not have the required system permissions**.

Because of this, the WiFi connection cannot be created.

---

# Objective

Fix the system so that the WiFi configuration feature can successfully connect the Raspberry Pi to a selected network **without encountering the "Insufficient privileges" error**.

The solution must be implemented **properly and securely**, not by applying unsafe workarounds.

---

# Investigation Requirements

First identify how the WiFi connection is currently being executed.

Investigate:

* what command is being used (`nmcli`, `wpa_cli`, etc.)
* which user account the backend server is running under
* whether the backend process has permission to manage network connections.

Determine why the backend process does not have sufficient privileges.

---

# Required Fix

Implement a correct solution that allows the backend to perform WiFi connection operations safely.

Possible approaches may include:

* properly configuring system permissions for the network command
* allowing the backend service to execute specific networking commands with elevated privileges
* configuring appropriate `sudo` permissions for the required commands
* ensuring the backend user belongs to the correct system groups if necessary.

The implementation must:

* avoid granting unnecessary system privileges
* restrict elevated access only to the required network management commands
* prevent command injection risks.

---

# Security Requirements

Because this feature interacts with system-level networking:

* validate all user input before executing commands
* avoid executing raw shell commands built from unsanitized input
* ensure that elevated privileges are **limited to specific commands only**.

---

# Code Quality Requirements

While implementing the fix:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* keep WiFi management logic isolated from unrelated components
* maintain clean backend command handling.

---

# Validation

After implementing the fix, verify that:

* WiFi networks can be connected successfully through the Kiosk Admin Panel
* the **"Insufficient privileges" error no longer occurs**
* the system can connect to secured WiFi networks
* the web application remains secure and stable.

---

# Goal

Ensure that the **WiFi configuration feature in the Kiosk Admin Panel works reliably**, allowing administrators to connect the Raspberry Pi to WiFi networks while maintaining **proper security and system permissions**.
