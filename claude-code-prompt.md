You are working on the **CoCo Campus RAG Chatbot kiosk system**.

The advertisement management page is located at:

```
http://192.168.18.178:8000/admin#advertisements
```

---

# Problem

In the **Advertisement Management UI**, specifically in the **list of advertisements displayed below the upload/publish section**, there is a layout issue.

The following UI elements are **overlapping each other**:

* the **advertisement number label**
* the **delete button (X icon)**

This overlap makes the UI look broken and may affect usability.

---

# Objective

Fix the layout so that the **advertisement number label and the delete button no longer overlap**.

Both elements must remain **clearly visible and clickable**.

---

# Requirements

Ensure that:

* the **advertisement number label** and **delete (X) button** are properly spaced
* the UI remains **clean and readable**
* the delete button remains **easy to click**
* the layout works consistently across **different screen sizes** used by the admin panel.

Avoid quick fixes that only shift the elements slightly without solving the layout structure.

Instead, **adjust the container layout properly**.

---

# Implementation Guidelines

When fixing the layout:

* inspect the CSS and HTML structure responsible for the advertisement list
* adjust the layout using a proper approach such as **flexbox or grid alignment**
* ensure the delete button is placed in a **stable corner or dedicated container**
* avoid absolute positioning hacks unless necessary.

---

# Code Quality Requirements

While implementing the fix:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* keep layout logic clean and maintainable
* avoid hard-coded offsets that may break on different screen sizes.

---

# Validation

Verify that:

* the **advertisement number label and delete button no longer overlap**
* both elements remain **clearly visible**
* the delete button is **fully clickable**
* the layout works properly across typical admin panel resolutions.

---

# Goal

Ensure the **advertisement list layout in `/admin#advertisements` is visually correct and usable**, with the advertisement number label and delete button properly separated and aligned.
