You are working on the **CoCo Campus RAG Chatbot** project running on **Raspberry Pi OS in kiosk mode**.

The web application runs at:

```
http://localhost:8000/
```

Holding the **Fullscreen button for 5 seconds** opens the **Kiosk Admin panel**.

Several improvements are needed in this panel.

---

# 1. Enable Custom Keyboard in Kiosk Admin Password Field

Currently, the **password input field inside the Kiosk Admin panel is unusable in fullscreen mode**, because the Raspberry Pi OS virtual keyboard does not appear.

A **custom lightweight keyboard** was previously implemented for the main chatbot input field.

I want this **same custom keyboard to be used for the password input field inside the Kiosk Admin panel**.

However, there is one important difference:

* In the **main chatbot UI**, the keyboard is **left-aligned**.
* In the **Kiosk Admin panel**, the keyboard should appear **center-aligned**.

Requirements:

* The custom keyboard must activate when the **password input field receives focus**.
* The keyboard must insert characters correctly into the password field.
* The keyboard must be **center-aligned when used inside the Kiosk Admin panel**.
* The existing keyboard behavior for the chatbot input field must remain unchanged.

If necessary, refactor the keyboard implementation so that its **alignment can be controlled depending on context**.

---

# 2. Replace “Restart Backend” with “Reboot RPI”

In the Kiosk Admin panel there is currently a button:

```
Restart Backend
```

This button only restarts the backend service.

Replace this functionality with a new button:

```
Reboot RPI
```

Behavior:

* When clicked, it should **restart the entire Raspberry Pi system**.
* This should safely trigger a system reboot.

Requirements:

* Ensure the reboot command is executed securely.
* Ensure proper permissions are handled correctly.
* Avoid exposing unsafe command execution paths.

---

# 3. Display Current WiFi Network

In the Kiosk Admin panel, I also want to display the **WiFi network that the Raspberry Pi is currently connected to**.

Add a section that shows something similar to:

```
Connected WiFi: <network_name>
```

Requirements:

* Retrieve the currently connected WiFi SSID from the system.
* Display it clearly in the Kiosk Admin panel.
* If no WiFi is connected, show an appropriate message such as:

```
No WiFi connection detected
```

---

# Code Quality Requirements

While implementing these changes:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* keep the custom keyboard logic reusable and maintainable
* avoid duplicating keyboard logic
* ensure system commands are handled securely
* keep UI code clean and maintainable.

---

# Validation

After implementing the changes, verify that:

* the custom keyboard works in the **Kiosk Admin password input field**
* the keyboard appears **center-aligned in the Kiosk Admin panel**
* the keyboard behavior for the main chatbot input remains unchanged
* the **Reboot RPI** button correctly reboots the system
* the **connected WiFi network name is displayed correctly**
* the system behaves correctly after reboot.

---

# Goal

Improve the **Kiosk Admin panel usability and functionality** by enabling keyboard input for the password field, adding system-level control through reboot functionality, and displaying the Raspberry Pi’s current WiFi connection.
