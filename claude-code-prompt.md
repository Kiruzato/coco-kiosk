You are working on the **CoCo Campus RAG Chatbot** project running on **Raspberry Pi OS in kiosk fullscreen mode**.

The web app runs at:

```
http://localhost:8000/
```

A **lightweight built-in keyboard** was recently implemented to allow users to type into the chatbot input field while the application is running in fullscreen mode.

The keyboard implementation is **working correctly**, but it currently **does not include many common symbols found on a standard keyboard**.

---

# Objective

Extend the built-in keyboard so that it includes **commonly used symbols typically available on a standard keyboard**.

The current keyboard is missing symbols such as:

* Parentheses `( )`
* Mathematical symbols such as `+ - × ÷ =`
* Other common punctuation and symbols like:

  * `!`
  * `?`
  * `:`
  * `;`
  * `'`
  * `"`.
  * `/`
  * `\`
  * `@`
  * `#`
  * `%`
  * `&`
  * `*`

These symbols should be available **in a way that keeps the keyboard simple and usable in kiosk mode**.

---

# Implementation Guidelines

The keyboard should remain **lightweight and kiosk-friendly**.

You may implement symbol support by:

* adding additional keys
* adding a **symbol toggle layer** (for example a `?123` or `Symbols` key)
* grouping symbols in a compact layout

However, **do not turn the keyboard into a full complex desktop keyboard**.

The goal is to support **common typing scenarios**, especially:

* general text
* punctuation
* basic mathematical expressions
* typical chatbot queries.

---

# Requirements

Ensure that:

* all added keys correctly insert characters into the input field
* keyboard layout remains usable on a touchscreen
* the keyboard does not overflow the UI
* the keyboard works reliably in **fullscreen kiosk mode**.

---

# Code Quality Requirements

While implementing this enhancement:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* keep keyboard layout logic **clean and maintainable**
* avoid hardcoding layout logic in scattered places
* structure the keyboard configuration in a way that is easy to extend later.

---

# Validation

After implementation, verify that:

* the keyboard contains the new symbols
* symbols insert correctly into the chat input field
* the keyboard remains responsive and usable on the touchscreen
* the keyboard layout remains stable in fullscreen kiosk mode.

---

# Goal

Enhance the **lightweight built-in keyboard** so that it supports **common symbols found on standard keyboards**, while keeping the implementation **simple, maintainable, and suitable for touchscreen kiosk usage**.
