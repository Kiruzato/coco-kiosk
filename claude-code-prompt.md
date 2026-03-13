# Prompt for Claude Code Agent — Opus 4.6

You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The admin panel is available at:

```
http://localhost:8000/admin#voice
```

In the **Cloud Credentials** panel there are two credential verification features:

1. **OpenAI API Key verification**
2. **Google Cloud Service Account JSON verification**

Each credential has a **Verify button** that should check whether the credential is valid.

---

# Problem

Currently, both **Verify buttons are not functioning correctly**.

### OpenAI API Key

I tested by entering a **nonexistent / invalid OpenAI API key**, saving it, and pressing **Verify**.

The UI still shows the key as **Valid**, which is incorrect.

---

### Google Cloud Service Account

I tested by uploading a **Google Cloud Service Account JSON file with incorrect credentials**.

After saving and pressing **Verify**, the UI still shows the credential as **Valid**, which is also incorrect.

---

# Objective

Fix the credential verification logic so that the **Verify buttons perform real credential validation**, not just UI confirmation.

The system must accurately determine whether the credentials are **valid or invalid**.

---

# Required Investigation

First determine how the current verification works.

Check whether the system currently:

* only verifies **file existence**
* only checks **JSON format**
* only checks whether the credential is **saved in configuration**
* or incorrectly assumes validity.

Determine why invalid credentials are still marked as **valid**.

---

# Required Behavior

### 1. OpenAI API Key Verification

The **Verify button** must perform a **real API validation**.

Possible approach:

* perform a lightweight request to the OpenAI API using the provided key
* confirm that the API returns a **successful authentication response**.

If authentication fails, the UI must display **Invalid**.

---

### 2. Google Cloud Service Account Verification

The **Verify button** must confirm that the uploaded service account JSON is **usable for Google STT**.

Verification should include:

* confirming the JSON structure is valid
* confirming authentication with Google Cloud services works
* ideally performing a **lightweight STT client initialization test**.

If authentication fails, the UI must display **Invalid**.

---

# Error Handling

If a verification attempt fails:

* return a clear error message
* update the UI to indicate **Invalid credentials**.

Avoid silent failures.

---

# If Real Verification Is Not Possible

If real verification is technically impossible due to API limitations or security constraints, clearly explain:

* why verification cannot be implemented
* what the **best alternative validation approach** would be.

Do not fake validation.

---

# Code Quality Requirements

While implementing the fix:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* keep credential verification logic clean and isolated
* avoid exposing sensitive credential data in logs
* ensure secure handling of API keys and service account files.

---

# Validation

Verify that:

* invalid OpenAI API keys are detected correctly
* valid OpenAI API keys pass verification
* invalid Google Service Account credentials fail verification
* valid service account credentials pass verification
* the UI displays correct **Valid / Invalid status**.

---

# Goal

Ensure that the **Verify buttons in the Cloud Credentials panel perform real credential validation**, accurately indicating whether the **OpenAI API Key and Google Cloud Service Account credentials are actually usable by the system**.
