You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The Voice configuration panel is accessible at:

```
http://localhost:8000/admin#voice
```

This panel includes the **Google STT Monthly Usage tracker**, which displays the current monthly usage of **Google Cloud Speech-to-Text (STT)**.

---

# Current Situation

The **Google STT Monthly Usage tracker is functioning**, but there is a usability issue.

Currently:

* The usage value shown in the UI **only updates after a system reboot**.
* During runtime, the displayed value **does not refresh automatically**, even though STT usage may increase.

---

# Objective

Update the system so the **Google STT Monthly Usage tracker refreshes dynamically in the UI** without requiring a system reboot.

---

# Required Behavior

### 1. Refresh Usage When Navigating to Voice Config

When the admin navigates to **Voice Config** through the **Admin Sidebar**, the system must:

* retrieve the **current Google STT monthly usage from the backend**
* update the UI to display the **latest usage value**.

This ensures the tracker always shows **current usage when the page is opened**.

---

### 2. Include Usage Refresh in the Refresh Button

The **Refresh button** in the Voice configuration panel must also:

* request the **latest Google STT usage value**
* update the **Google STT Monthly Usage tracker in the UI**.

The refresh button should update:

* voice configuration status
* **Google STT usage value**

so the entire panel reflects the **latest runtime state**.

---

# Implementation Guidelines

When implementing this change:

* reuse the **existing backend usage-retrieval logic**
* avoid duplicating STT usage tracking code
* use **clean asynchronous API calls** from the frontend
* ensure the UI updates only the necessary components.

---

# Code Quality Requirements

Follow **industry-standard best practices**:

* apply **proper refactorization and modularization**
* avoid duplicated logic
* keep backend usage retrieval centralized
* maintain clear separation between **UI logic and backend logic**.

---

# Validation

Verify that:

* navigating to **Voice Config via the sidebar** updates the usage value
* clicking the **Refresh button** updates the usage value
* the UI reflects the **latest STT usage without rebooting**
* no regressions occur in the Voice configuration panel.

---

# Goal

Ensure that the **Google STT Monthly Usage tracker in `/admin#voice` always displays the current usage value**, updating automatically when the Voice Config page is opened and when the Refresh button is used, without requiring a system reboot.
