You are working on the **CoCo Campus RAG Chatbot** project.

This task concerns the **user feedback / liking system** in the **Kiosk UI** located at:

`http://localhost:8000/`

---

# Problem 1 — Voice Query Feedback Not Saved

Currently, the **feedback / liking system works only for responses generated from typewritten queries**.

However, when the response comes from a **voice query**, user feedback (Like / Dislike) **is not saved**.

This indicates that the **voice query response pipeline is not properly integrated with the feedback system**.

---

# Objective 1

Fix the system so that **responses generated from voice queries can also receive and correctly save user feedback**.

Investigate the entire feedback flow:

User clicks Like / Dislike
→ frontend event handler
→ API request
→ backend logging system
→ feedback stored in the conversation log

Verify that voice responses have the **necessary identifiers and metadata** required by the feedback system.

If voice responses are missing required identifiers (such as message IDs or query IDs), correct the response generation logic so that feedback can be properly associated with the correct message.

Ensure that feedback for voice responses is **saved correctly in the conversation logging system**.

---

# Problem 2 — Feedback on Past Messages Is Incorrect

Currently, users can click Like / Dislike on **past chatbot responses**.

However, this produces incorrect behavior:

Feedback given to **past messages** is sometimes **applied to the most recent response instead**.

This creates **incorrect feedback logging**.

---

# Objective 2

To prevent this incorrect behavior:

Disable the **Liking / Dislike functionality for past messages**.

The feedback system should only be active for the **most recent chatbot response**.

Requirements:

* Only the **latest chatbot message** should have active Like / Dislike controls.
* Past messages should **not allow feedback interaction**.
* Past messages may still visually show their existing feedback status if already recorded.

Ensure this behavior is implemented **cleanly in both the frontend and backend logic**.

---

# Investigation

Identify the root causes of both issues.

Possible causes may include:

* missing response identifiers for voice responses
* feedback API not triggered for voice responses
* incorrect message ID mapping
* frontend event handler binding problems
* feedback API always referencing the latest message ID

Do not implement superficial UI fixes — correct the **actual system behavior**.

---

# Implementation Requirements

While implementing the fix:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* ensure feedback handling logic is **consistent for both text and voice responses**
* avoid duplicating logic between voice and text pipelines
* keep the feedback system **clean and maintainable**

---

# Validation

After implementing the fixes, confirm that:

1. Feedback works correctly for **responses generated from voice queries**.
2. Feedback is correctly **saved in the conversation logging system**.
3. Feedback controls are **disabled for past chatbot responses**.
4. Feedback actions always apply to the **correct response**.
5. No regressions occur in the text query feedback system.

---

The goal is to ensure that the **feedback system is reliable, consistent across query types, and free from incorrect feedback associations**.
