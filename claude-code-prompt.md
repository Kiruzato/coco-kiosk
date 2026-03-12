You are working on the **CoCo Campus RAG Chatbot** deployed on **Raspberry Pi OS** running in **kiosk mode**.

The web application is accessed at:

```
http://localhost:8000/
```

and typically runs in **fullscreen mode**.

---

# Problem

Raspberry Pi OS has a **built-in virtual keyboard**.

Observed behavior:

* When the web app is **not in fullscreen**, clicking the **text input field** correctly triggers the **virtual keyboard**.
* When the web app is in **fullscreen**, clicking the **text input field does NOT trigger the virtual keyboard**.

This results in the **typing input field becoming unusable in fullscreen mode**, because there is **no keyboard available for input**.

---

# Objective

Investigate and implement a solution so that **a keyboard can still be used when the web app is in fullscreen kiosk mode**.

The solution must allow users to **type into the input field while the web app is running fullscreen**.

---

# Investigation

Determine the root cause of why the virtual keyboard does not appear in fullscreen.

Investigate:

* Raspberry Pi OS **on-screen keyboard behavior**
* how the system detects **focus events**
* whether fullscreen mode blocks **input focus detection**
* how Chromium kiosk mode interacts with the **RPI virtual keyboard**
* whether the keyboard requires a specific **input method framework**
* whether fullscreen suppresses the **on-screen keyboard trigger**

Also determine if the system uses:

* `matchbox-keyboard`
* `onboard`
* Raspberry Pi OS built-in virtual keyboard service
* other input frameworks.

---

# Possible Solutions to Evaluate

Evaluate practical solutions such as:

* triggering the system virtual keyboard when the input field receives focus
* explicitly launching the OS virtual keyboard when the input field is clicked
* configuring Chromium kiosk flags for touchscreen keyboards
* integrating a lightweight web-based keyboard as a fallback
* adjusting kiosk launch parameters in the deployment setup.

Select the **most stable and maintainable approach** suitable for Raspberry Pi kiosk environments.

Avoid solutions that rely on fragile hacks or heavy third-party libraries unless absolutely necessary.

---

# Implementation Requirements

The implemented solution should:

* allow typing into the input field while the app is **fullscreen**
* work reliably in **Raspberry Pi kiosk runtime**
* not require exiting fullscreen
* not introduce UI regressions.

Prefer **system keyboard integration** over building a custom keyboard if possible.

---

# Code Quality Requirements

While implementing the solution:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* avoid tightly coupling keyboard logic with unrelated UI code
* keep the implementation **clean and maintainable**.

---

# Validation

After implementing the solution, confirm that:

* the keyboard appears when the input field is focused in **fullscreen mode**
* typing works normally
* kiosk fullscreen mode remains intact
* the solution works after **system reboot**
* the solution works in **Raspberry Pi runtime environment**.

---

# Goal

Ensure that the **chat input field remains usable in fullscreen kiosk mode by enabling a working keyboard solution in Raspberry Pi OS runtime**.
