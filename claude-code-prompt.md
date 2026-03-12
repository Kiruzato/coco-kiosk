You are working on the **CoCo Campus RAG Chatbot** project.

This task concerns the deployment script:

```
WEB_APP/deploy/install_kiosk.sh
```

---

# Context (Reference from Previous Task)

Previously, the script was modified to allow **reconfiguration of the Virtual Keyboard fullscreen solution**.

However, the current implementation **still detects existing configuration and silently skips the setup**, which means the reconfiguration logic **never actually asks the user for input**.

Because of this, **new configuration changes are not applied**.

---

# Problem

The script currently behaves like this:

```
configuration detected → skip setup automatically
```

But what I actually want is:

```
configuration detected → ASK USER if they want to reconfigure
```

The script must **not silently ignore the step just because it detects existing configuration**.

---

# Objective

Modify the **Virtual Keyboard setup section** of the script so that it **always asks the user whether to reconfigure**, even if the system detects that the configuration already exists.

The script must explicitly prompt the user.

Example:

```
Virtual Keyboard configuration already exists.
Do you want to reinstall / reconfigure it? (Y/N):
```

Behavior:

* **Y**

  * Force re-run of the Virtual Keyboard configuration steps
  * Apply the latest configuration changes

* **N**

  * Skip the configuration and continue the script

---

# Important Requirement

The prompt must appear **even when the script detects the system is already configured**.

Do **not bypass the prompt automatically**.

The user must always be able to **manually trigger reconfiguration**.

---

# Implementation Guidance

Refactor the script logic so that:

1. Detection logic determines whether configuration exists.
2. If configuration exists:

   * prompt the user **Y/N**
   * run the configuration only if the user chooses **Y**
3. If configuration does not exist:

   * run the configuration automatically.

Example logic flow:

```
if configuration_exists:
    ask user Y/N
    if Y → reconfigure
    if N → skip
else:
    run configuration
```

Ensure that **the prompt is always reached when configuration exists**.

---

# Code Quality Requirements

While implementing the fix:

* follow **industry-standard shell scripting practices**
* keep the script **modular and readable**
* avoid duplicated configuration logic
* isolate Virtual Keyboard setup into a **clear function or section**
* maintain **idempotent installation behavior**.

---

# Validation

After implementing the fix:

Verify that:

* the script **always prompts the user when configuration exists**
* choosing **Y** re-runs the Virtual Keyboard configuration
* choosing **N** skips the configuration
* first-time installations still run automatically
* no unrelated installation steps are affected.

---

# Goal

Ensure that **new configuration changes (such as the fullscreen Virtual Keyboard solution)** can always be applied on an already-installed system by **allowing the user to manually trigger reconfiguration through a Y/N prompt**.
