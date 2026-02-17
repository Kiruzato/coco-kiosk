You are working on the existing CoCo Campus RAG Chatbot codebase. Your task is to design and implement a complete **advertisement panel management and display system** that integrates cleanly into the current architecture.

Your implementation must follow industry best practices, maintain architectural consistency, and avoid introducing technical debt.

---

# Core Objective

Implement a system that allows administrators to upload and manage advertisement images, and allows the chatbot UI to display those advertisements in a slideshow panel with proper navigation and indicators.

The advertisement panel area already exists in the chatbot UI at `http://localhost:8000`. Your task is to implement the functionality that powers this panel. You must use the existing panel and integrate behavior into it, not create a separate or duplicate panel.

This system must integrate seamlessly into the existing backend and frontend without breaking or redesigning unrelated components.

---

# Functional Requirements

## Admin Advertisement Management

Provide a user interface within the existing Admin panel (accessible at `/admin`) that allows administrators to:

* Upload advertisement images (JPG, JPEG, PNG)
* View uploaded advertisements
* Manage advertisements in a structured and reliable way

Uploaded advertisements must be persisted locally and made available to the application.

The system must ensure:

* File validation
* Safe file storage
* Reliable metadata tracking
* Proper separation between storage and business logic

---

## Advertisement Panel Display (Chatbot UI)

The chatbot interface already contains an advertisement panel area. Implement the functionality required so that this panel:

* Displays advertisement images in a slideshow format
* Shows one advertisement at a time
* Displays indicator dots showing how many advertisements exist and which one is currently active
* Automatically rotates advertisements at a fixed interval of **1 minute per advertisement**
* Loops continuously through all advertisements

The existing advertisement panel must dynamically load advertisements from the backend.

---

## Advertisement Panel Navigation Behavior

The advertisement panel itself must act as the navigation surface.

Click interaction behavior:

* Clicking the right half of the panel navigates to the next advertisement
* Clicking the left half of the panel navigates to the previous advertisement
* No visible buttons or arrows should be used
* Navigation must feel natural and responsive

Manual navigation must properly update the display state and slideshow timing.

---

## System Integration Requirements

The advertisement system must integrate cleanly into the existing system architecture.

The implementation must ensure:

* Proper separation of concerns
* Clear boundaries between backend logic, storage, and frontend presentation
* Clean API design for advertisement retrieval and management
* No coupling with the RAG, retrieval, or voice subsystems
* No regression or disruption to existing functionality

Frontend must dynamically load advertisements from the backend, not rely on hardcoded data.

The implementation must extend and power the existing advertisement panel, not replace or duplicate it.

---

# Architectural and Engineering Requirements

Follow professional software engineering practices and industry standards.

This includes:

* Proper modularization of advertisement-related logic
* Clear abstraction boundaries between layers
* Avoiding monolithic or tightly coupled implementations
* Writing maintainable, readable, and extensible code
* Using appropriate data structures and persistence strategies consistent with the existing system
* Reusing existing architectural patterns already present in the codebase where appropriate
* Refactoring related areas if necessary to maintain architectural clarity and consistency

You may reorganize or refactor relevant parts of the system if doing so improves modularity, clarity, or maintainability, but do not redesign unrelated subsystems.

---

# UX and Behavior Expectations

Administrator workflow:

* Administrator opens Admin panel
* Administrator uploads advertisement image
* Advertisement becomes available to the system immediately

User workflow:

* User opens chatbot interface at `http://localhost:8000`
* The existing advertisement panel displays advertisements automatically
* Each advertisement remains visible for exactly 1 minute before rotating
* Advertisements rotate continuously in a loop
* User can navigate advertisements via left/right click zones
* Indicator dots accurately reflect slideshow state

---

# Quality Expectations

Your implementation must be:

* Clean
* Modular
* Robust
* Maintainable
* Architecturally consistent
* Production-quality

Avoid shortcuts, hacks, or tightly coupled solutions.

Favor clarity, extensibility, and correctness.

---

# Implementation Approach

Before implementing, analyze the current codebase structure and identify the most appropriate integration points.

Design the advertisement system so it aligns naturally with the existing architecture and patterns already used in the project.

Then implement the system in a structured, modular, and maintainable way.
