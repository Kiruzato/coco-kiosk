You are working on the **CoCo Campus RAG Chatbot** project running on **Raspberry Pi OS in kiosk mode**.

The web application runs at:

```
http://localhost:8000/
```

and normally operates in **fullscreen mode**.

---

# Problem

The system requires a **virtual keyboard** so users can type into the chatbot input field.

However, in the Raspberry Pi runtime environment:

* When the web app **is NOT in fullscreen**, the **Raspberry Pi virtual keyboard appears correctly** when the input field is focused.
* When the web app **is in fullscreen**, the **virtual keyboard does not appear at all**.

This makes the **chat input field unusable in fullscreen mode**, because users cannot type.

Attempts have already been made to fix this by **reconfiguring the virtual keyboard through the deployment script**, but **the problem still persists**.

---

# Objective

I need a **reliable solution that allows a virtual keyboard to work while the web app is running in fullscreen kiosk mode**.

You must **investigate and implement the best solution**, rather than repeatedly applying the same configuration.

---

# Investigation Requirements

Investigate the full system stack involved:

### Raspberry Pi OS

Check:

* the **built-in virtual keyboard**
* whether the system uses `matchbox-keyboard`, `onboard`, or another keyboard service
* how the keyboard is triggered by **input focus events**

---

### Chromium / Kiosk Mode

Investigate how Chromium behaves in kiosk mode:

* whether fullscreen suppresses the OS virtual keyboard
* whether kiosk flags affect virtual keyboard activation
* whether touchscreen keyboard support is disabled in fullscreen

Check if additional Chromium flags are needed.

---

### Web Application

Check whether the web application:

* prevents focus events from triggering the OS keyboard
* uses input fields compatible with the Raspberry Pi keyboard trigger.

---

# Solution Requirements

Implement the **most reliable solution for Raspberry Pi kiosk deployments**.

Possible approaches may include:

* properly enabling the OS virtual keyboard in kiosk mode
* triggering the OS keyboard when the chat input field receives focus
* adjusting Chromium kiosk flags
* launching the virtual keyboard through system commands when needed
* integrating a lightweight web-based keyboard if OS integration is impossible.

Choose the **best approach that is stable and maintainable for kiosk environments**.

Avoid fragile hacks.

---

# Constraints

The solution must:

* work while the web app is **in fullscreen**
* allow users to type into the chat input field
* work reliably after **system reboot**
* integrate cleanly with the current kiosk deployment setup.

---

# Code Quality Requirements

While implementing the solution:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* keep the deployment logic clean
* avoid unnecessary dependencies
* ensure the solution is **maintainable and stable**.

---

# Validation

After implementing the solution, verify that:

* the virtual keyboard appears when the chat input field is focused
* the keyboard works **in fullscreen mode**
* typing works correctly
* the solution persists after reboot
* kiosk functionality remains intact.

---

# Goal

Ensure that the **chat input field remains usable in fullscreen kiosk mode by providing a reliable virtual keyboard solution for Raspberry Pi OS runtime**.
