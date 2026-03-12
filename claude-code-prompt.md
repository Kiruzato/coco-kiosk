You are working on the **CoCo Campus RAG Chatbot** project running on **Raspberry Pi OS in kiosk mode**.

The web application runs at:

```
http://localhost:8000/
```

Holding the **Fullscreen button for 5 seconds** opens the **Kiosk Admin Panel**.

A **WiFi configuration feature** was recently implemented in this panel.

---

# Problem

When attempting to connect to a WiFi network using the Kiosk Admin WiFi configuration feature, the system returns the following error:

```
Error: 802-11-wireless-security.key-mgmt: property is missing
```

You previously attempted to fix this issue, but **the exact same error still occurs**, meaning the problem was **not actually resolved**.

---

# Objective

Investigate the WiFi connection logic again and **correctly fix the root cause** so that WiFi connections can be established successfully.

Do **not repeat the previous fix without verifying the actual behavior**.

---

# Investigation Requirements

Perform a proper investigation before applying changes.

Specifically check:

### 1. Actual System Command Being Executed

Determine exactly what command the backend is using to connect to WiFi.

Most likely this involves:

* `nmcli`
* `wpa_cli`
* or other network management commands.

Capture and inspect the **actual command being executed**.

Verify whether the command includes the required security parameters.

---

### 2. Network Security Handling

Ensure the system correctly handles different network types:

* WPA/WPA2 secured networks
* open networks
* hidden networks (if applicable)

The connection command must correctly specify the **key management type** when required.

---

### 3. NetworkManager Behavior on Raspberry Pi

Check how **NetworkManager / nmcli expects WiFi connections to be created**.

Verify that the parameters used by the system match what NetworkManager expects.

Test commands manually if necessary to confirm the correct syntax.

---

### 4. Backend Implementation

Review the backend WiFi connection logic and determine whether:

* parameters are missing
* arguments are incorrectly formatted
* the command is being executed incorrectly.

Correct the implementation so that the command structure is valid.

---

# Required Fix

Implement a **proper and reliable WiFi connection command** that works on Raspberry Pi OS using the installed network management system.

Ensure the backend correctly passes:

* SSID
* password
* security configuration

to the connection command.

The solution must work reliably for **typical WPA/WPA2 WiFi networks**.

---

# Code Quality Requirements

While fixing the issue:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* keep WiFi management logic **clean and isolated**
* avoid insecure command execution
* validate all user inputs before executing system commands.

---

# Validation

After implementing the fix, verify that:

* WiFi networks can be connected successfully
* the `key-mgmt property is missing` error no longer occurs
* the system works for password-protected networks
* connection feedback is displayed properly in the Kiosk Admin panel.

---

# Goal

Ensure that the **WiFi configuration feature in the Kiosk Admin Panel works reliably**, allowing administrators to successfully connect the Raspberry Pi to WiFi networks without encountering the `key-mgmt property is missing` error.
