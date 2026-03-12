You are working on the **CoCo Campus RAG Chatbot** project running on **Raspberry Pi OS in kiosk fullscreen mode**.

The web application runs at:

```
http://localhost:8000/
```

A **lightweight built-in virtual keyboard** has already been implemented and is functioning.
However, several improvements and fixes are required.

---

# Objective

Improve the built-in keyboard by:

1. Ensuring common symbols exist
2. Fixing layout spacing issues
3. Improving Caps Lock behavior
4. Adjusting keyboard alignment
5. Improving input field scrolling behavior

---

# 1. Symbol Coverage Check

First, check whether the following symbols **already exist in the keyboard**.

If any of them are **missing**, add them properly.

Symbols to verify:

```
~
`
!
@
#
$
%
^
&
*
(
)
_
-
+
=
{
[
}
]
|
\
:
;
"
'
<
,
>
.
?
/
```

Only add symbols that are **not already present**.

Ensure the added symbols:

* insert correctly into the input field
* follow the keyboard's existing design and layout style
* do not break the current keyboard structure.

---

# 2. Key Spacing Fix

Currently:

* The **last row of keys**
* and the **row above the last row**

are **cramped and touching each other**.

Fix the keyboard layout so that:

* spacing between these rows is **consistent**
* the spacing matches the **upper rows of keys**
* the layout remains clean and usable on a touchscreen.

---

# 3. Caps Lock Behavior

Currently, pressing **Caps Lock** only capitalizes **one character at a time**.

Improve the behavior to match typical keyboard functionality:

* **Single click** → capitalize **next character only**
* **Double click** → enable **continuous Caps Lock mode**

In continuous mode, all characters remain capitalized until Caps Lock is disabled.

Ensure this behavior is implemented cleanly and reliably.

---

# 4. Keyboard Alignment

Currently the keyboard appears **centered on the screen**.

Change the keyboard positioning so that it becomes:

**Left-aligned instead of centered**.

Ensure this alignment:

* looks clean in fullscreen kiosk mode
* does not break the layout
* does not push the keyboard outside the viewport.

---

# 5. Input Field Scrolling Behavior

When typing long text:

* once the characters exceed the visible width of the input field,
* the visible area **does not follow the cursor**.

Fix this behavior so that:

* the input field **automatically scrolls to the right**
* the **latest typed characters remain visible**
* the cursor position is always visible.

This should behave similarly to **normal text input fields on standard systems**.

---

# Code Quality Requirements

While implementing these improvements:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* keep keyboard logic clean and maintainable
* avoid duplicating layout logic
* avoid hardcoding values unnecessarily
* keep the keyboard lightweight and kiosk-friendly.

---

# Validation

After implementing the changes, verify that:

* all listed symbols are available in the keyboard
* keyboard rows have consistent spacing
* Caps Lock supports both single-press and double-press behavior
* the keyboard is left-aligned
* the input field scrolls correctly when text exceeds the visible width
* the keyboard remains fully functional in **fullscreen kiosk mode**.

---

# Goal

Enhance the **built-in virtual keyboard** so that it behaves more like a **standard keyboard**, while remaining **lightweight, clean, and reliable for touchscreen kiosk usage**.
