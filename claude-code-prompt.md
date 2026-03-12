You are working on the **CoCo Campus RAG Chatbot** project running on **Raspberry Pi OS in kiosk mode**.

The web application runs at:

```
http://localhost:8000/
```

Holding the **Fullscreen button for 5 seconds** opens the **Kiosk Admin Panel**.

A **WiFi configuration feature** was recently added there.

However, there are two issues that need to be fixed.

---

# Issue 1 — WiFi Connection Error

When attempting to connect to a WiFi network through the Kiosk Admin Panel, the system returns the following error:

```
Error: 802-11-wireless-security.key-mgmt: property is missing
```

This indicates that the WiFi connection command is missing the required **security configuration parameters**.

---

## Objective

Fix the WiFi connection logic so that networks can be connected successfully.

The system must correctly handle WiFi security configuration when connecting.

Investigate the backend command being used (likely via `nmcli` or another network tool) and ensure that:

* the correct **key management method** is provided
* WPA/WPA2 networks are handled correctly
* open networks are handled correctly
* password-protected networks pass the required parameters.

Ensure the connection command is **constructed properly and securely**.

The WiFi connection flow should work reliably for typical secured networks.

---

# Issue 2 — Password Visibility Toggle

Currently, the password fields do not allow administrators to verify what they typed.

Add a **password visibility toggle button** (show/hide password) for the following fields:

### 1. Kiosk Admin Panel login password

### 2. WiFi configuration password field

---

## Required Behavior

Each password field should include a **visibility toggle icon/button**, such as:

```
[ password input ] 👁
```

Behavior:

* Clicking the toggle switches the field between:

  * hidden (`type="password"`)
  * visible (`type="text"`)

This allows the admin to verify the entered password.

The toggle should not break existing functionality.

---

# Implementation Requirements

While implementing these fixes:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* avoid duplicating password toggle logic
* keep WiFi connection logic clean and maintainable
* ensure system command execution is **secure and validated**.

---

# Validation

After implementing the fixes, verify that:

### WiFi Connection

* WiFi networks can be connected successfully
* no `key-mgmt property is missing` error appears
* both secured and open networks work correctly.

### Password Visibility

* password visibility toggle works for:

  * Kiosk Admin login password
  * WiFi password input
* toggling visibility does not affect functionality.

---

# Goal

Ensure that the **WiFi configuration system works correctly** and that administrators can **verify passwords using a visibility toggle**, improving both reliability and usability of the Kiosk Admin Panel.
