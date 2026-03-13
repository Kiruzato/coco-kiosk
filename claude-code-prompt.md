You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The main interface is available at:

```
http://localhost:8000
```

When the **Fullscreen button is held for 5 seconds**, a **Kiosk Admin Panel** appears.

---

# Objective

I want to display the **current IP address of the Raspberry Pi** in the **Kiosk Admin Panel**.

The IP address must appear **below the "Connected WiFi" information** in the panel.

---

# Requirements

The Kiosk Admin Panel should display something like:

```
Connected WiFi: <WiFi Name>
IP Address: <Raspberry Pi IP Address>
```

The IP address must reflect the **actual active network interface used by the system**.

---

# Implementation Guidelines

* Retrieve the **current IP address from the backend**, not from hardcoded values.
* Ensure the system retrieves the IP address from the **active network interface (usually wlan0 for WiFi)**.
* The value should reflect the **current runtime network state**.
* The frontend should fetch the value from a **backend endpoint or existing network status logic**.

If there is already an endpoint that provides WiFi status, extend or reuse it to include the IP address instead of creating redundant endpoints.

---

# Behavior Requirements

* The IP address must **update when the Kiosk Admin Panel opens**.
* If the WiFi connection changes, the IP address displayed should reflect the **current connection state**.
* If no network is connected, display a fallback message such as:

```
IP Address: Not available
```

---

# Code Quality Requirements

While implementing this feature:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* avoid duplicating network status logic
* keep backend and frontend responsibilities clean
* ensure the implementation remains maintainable.

---

# Validation

Verify that:

* the **IP address appears below the Connected WiFi label**
* the displayed IP matches the **actual Raspberry Pi network address**
* the value updates when the Kiosk Admin Panel opens
* the UI layout remains clean and readable.

---

# Goal

Enhance the **Kiosk Admin Panel** by displaying the **Raspberry Pi’s current IP address below the Connected WiFi information**, allowing administrators to quickly see the device’s network address.
