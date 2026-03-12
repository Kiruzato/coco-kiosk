You are working on the **CoCo Campus RAG Chatbot** project running on **Raspberry Pi OS in kiosk runtime**.

The web application runs at:

```
http://localhost:8000/
```

---

# Problem

In the **Advertisement Panel**, specifically for **Text Advertisements**, emojis are **not rendering correctly**.

Observed behavior:

* Emojis appear as **empty boxes / square placeholders** instead of the correct emoji characters.

This issue occurs in **Raspberry Pi OS runtime**.

The emojis appear correctly in some development environments, but **not on the Raspberry Pi system**.

---

# Objective

Fix the issue so that **emojis render correctly in Text Advertisements on Raspberry Pi OS**.

The Advertisement Panel should correctly display emojis embedded in the advertisement text.

---

# Investigation Requirements

Investigate the real cause of the emoji rendering issue.

Possible causes may include:

### Font Support

The system may not have a font installed that supports emoji characters.

Check whether the Raspberry Pi system has fonts such as:

* `Noto Color Emoji`
* `Noto Emoji`
* other emoji-capable fonts.

---

### CSS Font Stack

Check the CSS font-family used by the Text Advertisement component.

Verify whether the font stack includes emoji-capable fonts.

If necessary, extend the font stack to support emoji rendering.

---

### Encoding Issues

Ensure that:

* the page uses **UTF-8 encoding**
* advertisement text is not losing emoji characters during storage or rendering.

---

### Deployment Script

If the issue requires installing fonts on Raspberry Pi, update the deployment script:

```
WEB_APP/deploy/install_kiosk.sh
```

so that the required emoji fonts are installed automatically.

Ensure this installation is **safe for repeated execution**.

---

# Required Fix

Implement a solution that ensures:

* emojis render correctly in Text Advertisements
* the fix works reliably on Raspberry Pi OS
* the UI displays emojis consistently.

Avoid quick hacks that only work in some environments.

---

# Code Quality Requirements

While implementing the fix:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* keep the CSS font configuration clean
* avoid hardcoding system-specific assumptions where possible.

---

# Validation

After implementing the fix, verify that:

* emojis display correctly in the Advertisement Panel
* emojis render properly in Raspberry Pi runtime
* the solution persists after **system reboot**
* the change does not break existing UI text rendering.

---

# Goal

Ensure that **Text Advertisements in the Advertisement Panel can correctly display emojis on Raspberry Pi OS**, providing proper emoji rendering instead of placeholder boxes.
