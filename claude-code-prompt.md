You are working on the **CoCo Campus RAG Chatbot** project running on **Raspberry Pi**.

This issue concerns the **Voice System Status panel** in the Admin UI:

```
http://192.168.18.178:8000/admin#voice
```

---

# Current Situation

In the Raspberry Pi runtime environment:

* The **Piper TTS voice model is now successfully working**.
* The system is **actually generating speech using Piper**.

However, the **Admin Voice panel still shows Piper as "Offline"**, which is incorrect.

This means the **status detection logic is wrong or incomplete**, because Piper is functioning but the UI reports it as unavailable.

---

# Objective

Fix the system so that the **Piper status indicator accurately reflects the real runtime state**.

The Admin Voice panel should show:

* **Online** when Piper is correctly installed, available, and usable by the system.
* **Offline** only when Piper is truly unavailable or failing.

---

# Investigation

Identify how the system currently determines Piper’s status.

Investigate the full pipeline:

Admin UI
→ API endpoint for voice status
→ backend status detection logic
→ Piper engine initialization / availability check

Determine why the system reports **Offline even when Piper is functioning**.

Possible causes may include:

* incorrect runtime detection logic
* checking only installation instead of runtime availability
* incorrect path detection
* outdated status caching
* mismatched engine initialization state
* checking wrong model paths
* relying on a failed subprocess check even though the engine is usable.

---

# Required Fix

Refactor the status detection logic so that Piper status is determined based on **real engine usability**.

A proper check should verify things such as:

* Piper binary availability
* voice model availability
* ability to initialize the Piper engine
* ability to synthesize audio (or at least initialize the model successfully)

The system should **not rely on superficial checks** like static configuration flags.

---

# Additional Requirements

Ensure that:

* the admin status panel reflects the **true runtime state**
* the voice status endpoint returns accurate information
* Piper detection logic is **consistent with how the system actually uses Piper during TTS generation**

Avoid duplicating logic between the **status checker and the actual TTS engine initialization**.

---

# Code Quality Requirements

While implementing the fix:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* centralize TTS engine detection logic where possible
* remove redundant or outdated status checks
* ensure maintainability and clarity.

---

# Validation

After the fix:

Verify that:

* Piper shows **Online** in `admin#voice` when it is functioning.
* Piper shows **Offline** only when it is truly unavailable.
* The status remains correct after **server restart**.
* The status check does not introduce performance overhead.

---

# Goal

Ensure the **Admin Voice status panel accurately reflects the real operational state of the Piper TTS engine** in the Raspberry Pi runtime environment.
