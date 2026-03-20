# CoCo System - Data Flow Diagram

End-to-end data flow for the CoCo Campus RAG Chatbot, covering both text and voice input paths through the processing pipeline to output and logging.

Derived from actual implementation in `WEB_APP`.

---

```mermaid
flowchart TD
    %% ══════════════════════════════════════════════
    %% External Entities
    %% ══════════════════════════════════════════════

    USER[[User]]
    OPENAI[[OpenAI API]]
    GOOGLE_STT[[Google Cloud STT]]

    %% ══════════════════════════════════════════════
    %% Input Layer
    %% ══════════════════════════════════════════════

    subgraph INPUT_LAYER [" Input Layer "]
        TEXT_IN(Text Input)
        VOICE_IN(Voice Input)
    end

    %% ══════════════════════════════════════════════
    %% Processing Layer
    %% ══════════════════════════════════════════════

    subgraph PROCESSING [" Processing Layer "]
        STT(Speech-to-Text Engine)
        PREPROCESS(Input Preprocessing)
        GOVERNANCE(Intent Classification & Governance)
        RETRIEVAL(Hybrid RAG Retrieval)
        EXTRACTION(Deterministic Extraction)
        LLM(LLM Synthesis)
    end

    %% ══════════════════════════════════════════════
    %% Data Stores
    %% ══════════════════════════════════════════════

    subgraph DATA_STORES [" Data Stores "]
        FAISS[(FAISS Vector Store)]
        CONV_LOG[(Conversation Log)]
        FAQ_STORE[(FAQ Database)]
    end

    %% ══════════════════════════════════════════════
    %% Output Layer
    %% ══════════════════════════════════════════════

    subgraph OUTPUT_LAYER [" Output Layer "]
        TEXT_OUT(Text Response Display)
        TTS(Text-to-Speech Engine)
    end

    %% ══════════════════════════════════════════════
    %% Data Flows - Input
    %% ══════════════════════════════════════════════

    USER -->|"text query"| TEXT_IN
    USER -->|"audio stream"| VOICE_IN

    %% ══════════════════════════════════════════════
    %% Data Flows - Voice Path
    %% ══════════════════════════════════════════════

    VOICE_IN -->|"audio bytes"| STT
    STT -->|"audio"| GOOGLE_STT
    GOOGLE_STT -->|"transcript"| STT
    STT -->|"transcribed text"| PREPROCESS

    %% ══════════════════════════════════════════════
    %% Data Flows - Text Path
    %% ══════════════════════════════════════════════

    TEXT_IN -->|"raw query"| PREPROCESS

    %% ══════════════════════════════════════════════
    %% Data Flows - Core Pipeline
    %% ══════════════════════════════════════════════

    PREPROCESS -->|"normalized query"| GOVERNANCE
    GOVERNANCE -->|"classified query"| RETRIEVAL
    RETRIEVAL -->|"query embedding"| OPENAI
    OPENAI -->|"embedding vector"| RETRIEVAL
    RETRIEVAL -->|"context + scores"| EXTRACTION
    EXTRACTION -->|"enriched context"| LLM
    LLM -->|"prompt + context"| OPENAI
    OPENAI -->|"generated completion"| LLM

    %% ══════════════════════════════════════════════
    %% Data Flows - Data Store Access
    %% ══════════════════════════════════════════════

    RETRIEVAL -->|"similarity search"| FAISS
    FAISS -->|"ranked chunks"| RETRIEVAL
    FAQ_STORE -->|"FAQ items"| TEXT_OUT

    %% ══════════════════════════════════════════════
    %% Data Flows - Logging
    %% ══════════════════════════════════════════════

    LLM -->|"query + response"| CONV_LOG

    %% ══════════════════════════════════════════════
    %% Data Flows - Output
    %% ══════════════════════════════════════════════

    LLM -->|"response text"| TEXT_OUT
    LLM -->|"response text"| TTS
    TEXT_OUT -->|"displayed response"| USER
    TTS -->|"synthesized audio"| USER
```

---

## Flow Description

### Input Paths

| Path | Entry | Flow |
|------|-------|------|
| **Text** | User types a query in the UI | Raw query passes directly to Input Preprocessing |
| **Voice** | User speaks into the microphone | Audio is sent to the STT engine, which calls Google Cloud STT for transcription, then the transcript passes to Input Preprocessing |

Both paths converge at **Input Preprocessing**, which normalizes the text (STT artifact cleanup, number normalization, whitespace cleanup).

### Processing Pipeline (4-Layer Architecture)

1. **Intent Classification & Governance** - Classifies the query intent (directory, academic, event, general, greeting, out-of-scope) and applies safety rules.

2. **Hybrid RAG Retrieval** - Embeds the query via OpenAI, runs FAISS vector similarity search (k=8), computes keyword term coverage scores, fuses results via linear weighted combination, then validates grounding and semantic relevance.

3. **Deterministic Extraction** - Attempts pattern-based extraction for structured queries (deans list, awards, event dates, office contacts). If matched, provides authoritative data that bypasses LLM guesswork.

4. **LLM Synthesis** - All response paths terminate here. Sends a prompt with retrieved context and/or extracted data to OpenAI GPT-4o-mini. Generates a natural language response.

### Data Store Interactions

| Store | Read By | Written By |
|-------|---------|------------|
| **FAISS Vector Store** | Hybrid RAG Retrieval (similarity search) | Not written at runtime (pre-built during ingestion) |
| **Conversation Log** | Admin analytics dashboard | LLM Synthesis (logs every query + response as JSONL) |
| **FAQ Database** | Frontend UI (loaded on page start) | Admin panel (CRUD operations) |

### Output Paths

| Path | Source | Destination |
|------|--------|-------------|
| **Text** | LLM response rendered in the chat UI | User reads on screen |
| **Voice** | LLM response passed to TTS engine (Piper or Edge TTS) | User hears audio playback |

### External Services

| Service | Used By | Data Exchanged |
|---------|---------|----------------|
| **OpenAI API** | Retrieval (query embedding) + LLM Synthesis (completion) | Query text, context prompt, generated response |
| **Google Cloud STT** | Speech-to-Text engine (voice input only) | Audio bytes sent, transcript returned. Data logging disabled at project level. |

---

## Notes

- **FAQ Database** feeds the UI independently of the chat pipeline. FAQs are loaded on page start via `/api/faqs` and displayed as clickable suggestions. They do not pass through the RAG pipeline.

- **Conversation Log** is append-only JSONL. Each entry contains `{query_id, timestamp, query, answer, feedback}`. Feedback is updated in-place when the user rates a response.

- **Voice path is a superset of text path.** The voice orchestrator runs STT, then delegates to the same chat pipeline used by text input, then runs TTS on the response. All RAG guarantees are preserved regardless of input modality.

- **Hybrid retrieval** combines FAISS vector similarity (70% weight) with custom keyword term coverage scoring (30% weight) via linear weighted fusion. This is not BM25 — it uses a custom `coverage_score = matched_terms / total_query_terms` formula.
