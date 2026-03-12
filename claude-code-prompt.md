You are working on the **CoCo Campus RAG Chatbot** project.

This issue occurs **after deployment on Raspberry Pi** using the setup script:

```
WEB_APP/deploy/install_kiosk.sh
```

---

# Problem

After deploying the web app on **Raspberry Pi OS**, the Text-to-Speech system is **not using Piper**, even though Piper is supposed to be the **primary TTS engine**.

Observed behavior:

* In the Kiosk UI (`http://localhost:8000/`), the voice being used sounds like a **male robotic voice**, which indicates that **the fallback engine is being used instead of Piper**.
* The intended voice should be **Piper**, which sounds more **natural and female-like**.
* In the Admin Voice Settings panel:

```
http://192.168.18.178:8000/admin#voice
```

Piper is currently shown as **Offline**.

This indicates that the **Piper TTS engine is not being detected or initialized correctly in the Raspberry Pi runtime environment**.

---

# Objective

Diagnose and fix the problem so that **Piper becomes the active TTS engine during Raspberry Pi runtime**.

The system should:

* correctly detect Piper
* initialize the Piper engine
* generate speech using Piper instead of the fallback engine.

---

# Investigation

Investigate the entire Piper runtime pipeline:

### 1. Installation

Verify that Piper is correctly installed by the deployment script:

```
WEB_APP/deploy/install_kiosk.sh
```

Check:

* whether Piper binaries are installed
* whether required Piper dependencies are installed
* whether the Piper voice model is downloaded

---

### 2. Voice Model Availability

Verify that the expected Piper voice model exists.

Check:

* the model file path
* the ONNX model file
* the configuration JSON
* file permissions

Ensure the correct model is present (for example something similar to):

```
en_US-amy-medium.onnx
```

---

### 3. Runtime Detection

Investigate why Piper is reported as **Offline** in the admin voice panel.

Check:

* the TTS engine detection logic
* environment paths
* runtime configuration loading
* subprocess execution of Piper
* whether the system fails silently and falls back to another engine.

---

### 4. Fallback Behavior

Identify which engine is currently producing the **robotic male voice**.

Likely candidates include:

* espeak-ng
* other fallback TTS engines

Determine why the system is **falling back instead of using Piper**.

---

# Required Fix

Ensure that:

* Piper is correctly installed during deployment
* Piper voice model is available
* Piper engine detection works
* Piper is successfully initialized during runtime
* the system uses Piper as the **primary TTS engine**

If fallback engines are used, they should only activate **when Piper truly fails**.

---

# Additional Checks

Also verify that:

* the admin voice status panel correctly reflects Piper's state
* Piper detection logic matches the actual runtime status
* the voice system behaves consistently after reboot.

---

# Code Quality Requirements

While implementing the fix:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* avoid hardcoded paths when possible
* ensure the deployment script remains reliable for Raspberry Pi environments.

---

# Validation

After fixing the issue, confirm that:

* Piper is shown as **Online** in `admin#voice`
* Piper is the **active TTS engine**
* the voice produced in the kiosk UI matches the Piper voice model
* fallback engines are not used unless Piper actually fails
* the system works correctly after **Raspberry Pi reboot**.

---

The goal is to ensure that **Piper is correctly installed, detected, and used as the primary TTS engine in the Raspberry Pi deployment environment**.
