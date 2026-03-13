You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The developer tools panel is available at:

```
http://localhost:8000/dev
```

The admin voice configuration panel is available at:

```
http://192.168.18.178:8000/admin#voice
```

---

# Objective

I want to add a **Developer Toggle** in:

```
/dev
```

This toggle will **hide specific advanced UI elements** in the Voice Configuration page:

```
/admin#voice
```

The goal is to simplify the UI for normal usage while still allowing developers to enable advanced controls when needed.

---

# Toggle Behavior

Create a **toggle switch in `/dev`** that controls the visibility of several UI elements inside `/admin#voice`.

### Default State

The toggle must default to:

```
HIDDEN
```

This means the UI elements listed below are hidden unless the toggle is enabled.

---

# UI Elements to Hide

When the toggle is **enabled (hide mode ON)**, hide the following elements in `/admin#voice`.

---

## Speech-to-Text (STT) Panel

Hide:

1. The label:

```
Select the engine for converting speech to text
```

2. The entire panel:

```
Whisper.cpp (Local)
```

3. The entire section:

```
Fallback Engine
```

---

## Text-to-Speech (TTS) Panel

Hide:

1. The label:

```
Select the engine for converting text to speech
```

2. The entire section:

```
Fallback Engine
```

---

## Bottom Configuration Section

Hide the button:

```
Save Configuration
```

at the bottom of:

```
/admin#voice
```

---

# Persistence Requirement

The toggle state must **persist across system restarts and reboots**.

This means the selected state must be **stored in a persistent configuration**, not only in frontend memory.

When the system starts again, the UI must respect the **last saved toggle state**.

---

# Implementation Guidelines

* The toggle should control **UI visibility only**, not disable backend functionality.
* Hidden components should **not break layout structure**.
* Avoid duplicating UI logic.
* Prefer using **centralized configuration or feature flags** for the toggle state.

---

# Code Quality Requirements

While implementing this feature:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* avoid duplicated visibility logic
* keep developer-specific configuration isolated
* ensure maintainability and clarity of the code.

---

# Validation

Verify that:

* the toggle appears in `/dev`
* the toggle **hides and reveals the specified UI elements**
* the **default state is hidden**
* the toggle state **persists across system restarts**
* the admin voice page continues functioning normally.

---

# Goal

Provide a **developer toggle in `/dev` that hides advanced configuration elements in `/admin#voice`**, simplifying the UI for normal operation while allowing developers to re-enable those controls when needed.
