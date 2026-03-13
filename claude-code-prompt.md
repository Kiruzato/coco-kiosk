You are working on the **CoCo Campus RAG Chatbot kiosk system** running on **Raspberry Pi OS**.

The main kiosk UI is available at:

```id="a3rm9f"
http://localhost:8000
```

The system supports **voice input** through a voice input button.

---

# Background

When the **Voice Input button** is clicked, the system begins listening for the user's speech.

The UI already includes a feature that **detects when the user actually starts speaking**, and there is visual feedback on the screen indicating this detection.

However, in real usage, users sometimes **do not start speaking immediately** after clicking the voice input button. There can be a **short silent period at the beginning** before the user begins speaking.

---

# Concern

I want to determine whether the **silent portion at the beginning of the recording** is included in the audio sent to **Google Speech-to-Text (STT)**.

I noticed that the **Google STT usage tracker increases even when the beginning of the recording contains silence**, which suggests that the silent portion might be included in the transcription request.

---

# Objective

Investigate the voice input pipeline to determine exactly how the audio sent to **Google STT** is handled.

Specifically determine:

1. Whether the **initial silent portion of the recording** is included in the audio sent to Google STT.
2. Whether the system already **trims or discards the silent portion before speech begins**.
3. Whether the **voice activity detection (VAD) or speech start detection** affects what portion of the audio is actually transmitted to Google STT.

---

# Investigation Scope

Inspect the entire voice input pipeline, including:

* voice recording logic
* speech start detection logic
* voice activity detection (if present)
* preprocessing of audio before STT submission
* the STT request being sent to Google Cloud.

Determine the **exact audio segment that is being transmitted** to the STT service.

---

# If Silent Audio Is Being Sent

If the investigation confirms that **the silent portion at the beginning is included in the STT request**, propose and implement an improvement so that:

* audio before **actual speech detection** is removed or trimmed
* only the **relevant speech portion** is sent to Google STT.

The goal is to **reduce unnecessary STT usage and improve efficiency**.

---

# Implementation Requirements

If a fix is implemented:

* ensure trimming is reliable and does not cut off the beginning of speech
* ensure the change does not introduce noticeable delays
* keep the solution **lightweight for Raspberry Pi hardware**.

---

# Code Quality Requirements

While performing the investigation and possible fix:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* avoid duplicating logic
* keep the voice pipeline clean and maintainable.

---

# Deliverable

Provide:

1. A clear explanation of **whether silent audio is currently being sent to Google STT**.
2. If applicable, implement an improvement so that **only the speech portion of the audio is sent to STT**.
3. Ensure the voice input system continues to function reliably.

---

# Goal

Determine whether the **initial silent portion of voice recordings is being transmitted to Google STT**, and if so, improve the system so that **only actual speech is sent**, reducing unnecessary STT usage and improving efficiency.
