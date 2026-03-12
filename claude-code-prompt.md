You are working on the **CoCo Campus RAG Chatbot** project.

This task concerns the **deployment script**:

```
WEB_APP/deploy/install_kiosk.sh
```

---

# Current Situation

After fetching the latest commits, I ran the deployment script again:

```
WEB_APP/deploy/install_kiosk.sh
```

However, the script **detected that everything was already installed and configured**, so it skipped most steps.

Because of this behavior, **the new Virtual Keyboard solution for fullscreen mode was not applied**.

The script currently assumes the system is already fully configured and **does not reapply configuration changes introduced in newer commits**.

---

# Objective

Modify the installation script so that **changes related to the Virtual Keyboard fullscreen solution can still be applied even when the system is already installed**.

Specifically:

When the script reaches the **Virtual Keyboard configuration section**, it should ask the user:

```
Virtual Keyboard configuration already exists.
Do you want to reinstall / reconfigure it? (Y/N)
```

Behavior:

* If the user selects **Y**:

  * Reapply the Virtual Keyboard setup and configuration.
  * Update any related system settings required for fullscreen keyboard functionality.

* If the user selects **N**:

  * Skip that section and continue the installation script normally.

---

# Requirements

The script should:

* remain **safe to run multiple times** (idempotent installation).
* only reconfigure the **Virtual Keyboard-related setup when explicitly requested**.
* not reinstall unrelated dependencies unnecessarily.

Avoid forcing full reinstallations.

---

# Implementation Guidelines

Update the script so that:

* the Virtual Keyboard configuration section is **isolated into its own function or section**.
* the script **detects existing configuration**.
* the user is prompted whether to **reapply the setup**.

The logic should follow this structure:

```
if keyboard_config_exists:
    ask user Y/N
    if yes → reconfigure
    if no → skip
else:
    install and configure normally
```

---

# Code Quality Requirements

While modifying the script:

* follow **industry-standard shell scripting practices**
* keep the script **clean and modular**
* avoid duplicated logic
* maintain **readability and maintainability**
* ensure the script remains **safe for repeated execution**

If necessary, refactor the relevant portion of the script into **clearly separated functions**.

---

# Validation

After implementing the changes, verify that:

* running `install_kiosk.sh` again **offers the reconfiguration option**.
* selecting **Y** correctly reapplies the Virtual Keyboard setup.
* selecting **N** skips the step.
* the script still behaves correctly for **first-time installations**.
* no unrelated components are reinstalled unnecessarily.

---

# Goal

Ensure that **new deployment changes (such as the Virtual Keyboard fullscreen solution)** can be **applied on already-installed systems without requiring a full reinstall**, while keeping the installation script **safe, modular, and maintainable**.
