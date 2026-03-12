You are working on the **CoCo Campus RAG Chatbot** project running on **Raspberry Pi OS in kiosk mode**.

The web application runs at:

```
http://localhost:8000/
```

Holding the **Fullscreen button for 5 seconds** opens the **Kiosk Admin Panel**.

---

# Objective

Add a **WiFi configuration feature** inside the **Kiosk Admin Panel** so that an administrator can **change the WiFi network that the Raspberry Pi connects to**.

This feature should allow the admin to:

1. View available WiFi networks
2. Select a WiFi network
3. Enter the WiFi password
4. Connect the Raspberry Pi to the selected network

---

# Required Functionality

The WiFi configuration panel should include:

### 1. Current Connection Status

Display the current WiFi network the Raspberry Pi is connected to.

Example:

```
Connected WiFi: <SSID>
```

If not connected:

```
No WiFi connection
```

---

### 2. Scan Available Networks

Provide a button such as:

```
Scan WiFi Networks
```

This should retrieve nearby WiFi networks and display them in a list.

Each entry should show:

* SSID
* signal strength (if available)

---

### 3. Connect to Network

When the admin selects a WiFi network:

* allow entering the WiFi password
* allow connecting to the network.

Example UI flow:

```
Available Networks:
[ Network_A ]
[ Network_B ]
[ Network_C ]

Password: [________]

[Connect]
```

---

### 4. Connection Feedback

Provide feedback messages such as:

* Connecting...
* Connected successfully
* Failed to connect

---

# Backend Requirements

The backend must securely interact with the Raspberry Pi networking system.

Possible approaches include:

* `nmcli`
* `wpa_cli`
* other Raspberry Pi network management tools.

The implementation must:

* avoid unsafe command execution
* validate inputs
* handle errors safely.

---

# Security Considerations

Since this feature interacts with system networking:

* restrict access only through the **Kiosk Admin Panel**
* ensure commands cannot be injected through user input
* handle password input securely.

---

# Code Quality Requirements

While implementing the feature:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* keep UI logic separated from system command execution
* structure the WiFi management logic in a **clean backend module**
* avoid tightly coupling WiFi logic with unrelated UI components.

---

# Validation

After implementing the feature, verify that:

* the current WiFi network is displayed correctly
* available networks can be scanned
* the admin can connect to a new WiFi network
* the system reconnects successfully
* the web app remains accessible after network changes.

---

# Goal

Provide a **simple and reliable WiFi configuration interface inside the Kiosk Admin Panel**, allowing administrators to manage Raspberry Pi WiFi connections directly from the kiosk system without needing terminal access.
