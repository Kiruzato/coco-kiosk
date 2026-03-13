You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The web application admin panel is accessible at:

```
http://localhost:8000/admin#voice
```

This panel contains a **Google STT Monthly Usage Tracker** intended to display the usage of **Google Cloud Speech-to-Text (STT)**.

---

# Problem

The **Google STT Monthly Usage tracker is currently not working**.

The tracker should display the **current monthly usage of Google STT**, but the values are either:

* not updating,
* not being tracked,
* or not displayed correctly.

---

# Objective

Investigate and fix the **Google STT Monthly Usage tracker** so that it properly reflects the **actual usage of Google Cloud STT within the system**.

---

# Investigation Requirements

Before implementing a fix, perform a proper investigation.

Determine the following:

### 1. Whether usage tracking logic exists

Check if the system currently has logic that records STT usage when voice transcription occurs.

Specifically inspect:

* the **Google STT integration code**
* the **voice orchestrator / STT service layer**
* any **usage tracking module (e.g., usage_tracker or similar)**.

Determine whether usage data is:

* recorded
* partially recorded
* or never recorded at all.

---

### 2. Where usage data is stored

Identify where STT usage is supposed to be stored.

Possible locations may include:

* JSON logs
* in-memory counters
* a local file
* or another tracking mechanism.

Verify whether the stored data structure is correct and whether it persists correctly.

---

### 3. Monthly reset logic

Determine how the **monthly usage reset** is supposed to work.

Check whether the system:

* tracks usage by **calendar month**
* automatically resets when a new month starts
* properly handles month transitions.

If the reset logic is missing or broken, implement a correct and reliable mechanism.

---

### 4. Admin UI integration

Check the connection between:

* backend usage tracking logic
* the admin API endpoint
* the **UI component in `/admin#voice`**.

Ensure the admin panel is actually retrieving the **real usage data** from the backend.

Fix any broken API or UI binding if necessary.

---

# Required Behavior

After fixing the system:

* Google STT usage must be **tracked whenever transcription occurs**
* the usage counter must reflect the **current calendar month**
* the admin panel must display the **correct monthly usage value**
* the counter must **reset automatically when a new month begins**.

---

# Code Quality Requirements

While implementing the fix:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* avoid duplicating logic
* ensure usage tracking is **lightweight and reliable**
* keep the implementation **maintainable and clear**.

---

# Validation

Verify that:

* STT usage increases when voice queries are processed
* the monthly counter updates correctly
* the admin panel displays the correct value
* the system handles month changes properly
* no regressions occur in the voice input pipeline.

---

# Goal

Ensure that the **Google STT Monthly Usage tracker in `/admin#voice` accurately reflects the real monthly usage of Google Cloud Speech-to-Text**, with correct tracking, storage, reset logic, and admin panel display.
