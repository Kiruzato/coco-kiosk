Proceed with generating the ERD, but **only include core persistent entities** and exclude non-essential or runtime/config-only components.

### ✅ Include:

* DOCUMENT
* CHUNK
* METADATA_INDEX_ENTRY
* CONVERSATION_ENTRY
* FAQ
* ADVERTISEMENT
* TRIVIA_CONTENT
* STT_USAGE
* STT_USAGE_HISTORY
* CREDENTIAL
* OPENAI_API
* GOOGLE_CLOUD_STT

### ❌ Exclude:

* CONSOLIDATION_RULE
* EVENT_ENTRY
* CHAT_SESSION (in-memory)
* ADMIN_SESSION (in-memory)
* WELCOME_CONFIG
* VOICE_SETTINGS
* DEBUG_SETTINGS

### Rules:

* Only include **persistent, meaningful system data**
* Do NOT include **runtime state, debug data, or configuration-only entities**
* Focus on **clean, maintainable, and meaningful relationships**

Proceed with a **clean, production-quality Mermaid ERD in `.md` format**.
