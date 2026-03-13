You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The admin panel is available at:

```
http://localhost:8000/admin#voice
```

In the **Cloud Credentials panel**, there are two credential verification features:

1. **OpenAI API Key verification**
2. **Google Cloud Service Account verification**

Each credential has a **Verify button**, and the UI displays a **VALID label** when the credential is considered valid.

---

# Background

Previously, I reported that both **Verify buttons were not working properly**.

Testing revealed that:

* entering a **nonexistent OpenAI API key** still results in the UI showing **VALID**
* uploading an **invalid Google Cloud Service Account JSON** still results in **VALID**.

You attempted to fix this previously, but the problem **still persists**.

The **VALID label does not change at all**, even after re-testing with invalid credentials.

---

# Objective

Perform a **proper investigation of the verification system** and determine exactly what the **Verify buttons are actually verifying**, because it appears they are **not validating credentials correctly**.

After identifying the root cause, **fix the system so that credential verification works correctly**.

---

# Investigation Requirements

Do not immediately rewrite the feature.

First investigate the full verification flow.

Trace the entire path from:

1. **Verify button click in the UI**
2. **Frontend request sent to the backend**
3. **Backend verification logic**
4. **Response returned to the UI**
5. **UI label update logic**

Determine which part is broken.

Possible failure points include:

* the Verify button not calling the correct API
* the backend endpoint not performing real verification
* the backend returning incorrect status
* the frontend not updating the VALID label properly
* verification logic checking only file existence or format instead of real authentication.

---

# Specific Questions to Answer

During the investigation, determine:

1. What exactly does the **Verify button currently check**?
2. Does the backend actually attempt authentication with:

   * OpenAI API
   * Google Cloud STT service?
3. Does the backend always return **success regardless of credential validity**?
4. Does the frontend **ignore verification results** and always show VALID?

---

# Required Fix

After identifying the root cause, implement a proper fix so that:

### OpenAI API Key Verification

The Verify button must perform **real API authentication** using the provided key.

For example:

* perform a lightweight request to the OpenAI API
* if authentication fails, return **Invalid**
* if successful, return **Valid**.

---

### Google Cloud Service Account Verification

The Verify button must verify that the **uploaded service account JSON is actually usable**.

Possible checks:

* validate JSON structure
* initialize Google STT client with the credential
* confirm authentication succeeds.

If authentication fails, return **Invalid**.

---

# UI Behavior

Ensure the **VALID label in the UI updates dynamically** based on the verification result.

The label must:

* change to **Valid** only when credentials pass verification
* change to **Invalid** when verification fails.

The UI must not show **Valid by default** without verification.

---

# Code Quality Requirements

While fixing this:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* isolate credential verification logic
* avoid exposing sensitive credentials in logs
* ensure secure handling of API keys and service account files.

---

# Validation

After implementing the fix, verify that:

* invalid OpenAI API keys are correctly detected
* valid OpenAI API keys pass verification
* invalid Google Service Account credentials fail verification
* valid service account credentials pass verification
* the **VALID label updates correctly in the UI**.

---

# Goal

Ensure that the **Verify buttons in the Cloud Credentials panel perform real credential validation**, and that the **UI correctly reflects the verification result instead of always displaying VALID**.
