You are working on the existing CoCo Campus RAG Chatbot codebase. Your task is to implement a system that allows administrators to edit the chatbot’s initial welcome message through the Admin interface, and ensure the chatbot UI displays both a logo image and the administrator-defined welcome message when a new conversation begins.

Your implementation must follow industry best practices, maintain architectural consistency, and integrate cleanly into the existing system without introducing technical debt or breaking unrelated functionality.

---

# Core Objective

Currently, every new conversation in the chatbot UI displays a default initial welcome message.

The current initial message is:

Welcome! I can help you with information about:

Library hours and services
Dining options and meal plans
Parking and transportation
IT services and Wi-Fi
Student employment
Campus events and activities

What would you like to know?

(initial message end)

This message is currently static. I want administrators to be able to edit and manage this welcome message through the Admin interface accessible at:

```
http://localhost:8000/admin
```

Additionally, I want the chatbot UI to display an image located at:

```
/images/coco-name.jpg
```

This image must be displayed inside the exact same conversation bubble that contains the welcome message.

Specifically:

* The image must appear at the top of the chatbot’s initial message bubble
* The welcome message text must appear directly below the image
* Both the image and the welcome message must be part of one single chatbot message bubble
* The image and text must not be split into separate messages or separate bubbles

---

# Functional Requirements

## Admin Welcome Message Management

Provide a dedicated section in the Admin interface that allows administrators to:

* View the current welcome message
* Edit the welcome message
* Save changes to the welcome message

The editing interface must support multi-line text and preserve formatting.

Changes must persist and remain effective across page reloads and system restarts.

The system must use the administrator-defined message instead of a hardcoded message when initializing new conversations.

---

## Chatbot UI Initial Message Behavior

When a new conversation begins, the chatbot must display a single initial chatbot message bubble that contains:

1. The image located at `/images/coco-name.jpg`, displayed at the top of the message bubble
2. The welcome message text, displayed directly below the image, within the same bubble

The image and welcome message must be rendered together as one chatbot message.

The welcome message must be dynamically loaded from the system configuration managed by the admin.

Any updates made by administrators must be reflected automatically in future new conversations.

Existing conversations do not need to be modified.

---

# System Integration Requirements

The welcome message must not be hardcoded in frontend logic.

It must be managed as part of the system’s configuration or content management layer and retrieved dynamically by the chatbot UI.

The implementation must ensure:

* Proper persistence of the welcome message
* Clean separation between backend configuration and frontend rendering
* Reliable retrieval and display of the welcome message
* Proper rendering of the image `/images/coco-name.jpg` inside the same chatbot message bubble as the welcome message text
* No disruption to existing chat functionality, session handling, or RAG system behavior

The image `/images/coco-name.jpg` must be served using the system’s static file serving mechanism.

---

# Architectural and Engineering Requirements

Follow professional software engineering practices and industry standards.

This includes:

* Proper modularization of welcome message management
* Avoiding hardcoded content in frontend logic
* Maintaining clear separation between configuration, backend logic, and frontend rendering
* Using persistence and retrieval patterns consistent with the existing system architecture
* Ensuring maintainability, clarity, and extensibility

You may refactor relevant parts of the system if necessary to support clean implementation, but do not redesign unrelated subsystems.

---

# UX and Behavior Expectations

Administrator workflow:

* Administrator opens the Admin interface
* Administrator navigates to the welcome message management section
* Administrator views and edits the welcome message
* Administrator saves changes
* Changes become effective immediately for new conversations

User workflow:

* User opens chatbot UI at `http://localhost:8000`
* User starts a new conversation
* Chatbot displays a single initial chatbot message bubble
* Inside that same message bubble:

  * The image `/images/coco-name.jpg` appears at the top
  * The administrator-defined welcome message appears below the image

---

# Quality Expectations

Your implementation must be:

* Clean
* Modular
* Robust
* Maintainable
* Architecturally consistent
* Production-quality

Avoid hardcoded values, shortcuts, or tightly coupled implementations.

Favor clarity, extensibility, and correctness.

---

# Implementation Approach

Before implementing, analyze how the initial welcome message is currently defined, stored, and rendered.

Refactor the system so the welcome message is dynamically managed by administrators and rendered together with the logo image inside the same chatbot message bubble.

Ensure the implementation integrates cleanly with the existing architecture and frontend behavior without breaking existing functionality.
