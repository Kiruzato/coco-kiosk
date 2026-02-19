# Unify Directory Queries into Standard RAG Flow

Remove the `handle_directory_query()` special path so directory queries follow the same orchestrator pipeline as all other queries.

---

## 1. Current Flow Analysis

### Current Directory Flow (app.py:2123–2132)

```
Query → is_directory_query() regex match
      → handle_directory_query()
        → canonicalize_directory_query()
        → similarity_search(k=8, threshold=0.5)
        → compute_confidence_score()
        → [confidence < HIGH?] → hardcoded fallback (NO LLM)
        → [confidence = HIGH]  → standalone LLM call with directory prompt
```

**Problems**: Pre-LLM confidence gate blocks queries, hardcoded fallback bypasses LLM, separate retrieval path from orchestrator.

### Standard Orchestrator Flow (app.py:2134+)

```
Query → response_orchestrator.process_query()
      → Layer 1: _apply_governance() — intent + safety
      → Layer 2: _perform_retrieval() — hybrid retrieval + grounding + semantic relevance
      → Layer 3: _try_extractors() — deterministic extraction
      → Mode determination — RAG_AUTHORITATIVE / RAG_SUPPLEMENTED / GENERAL_KNOWLEDGE
      → Layer 4: _synthesize_response() — LLM ALWAYS CALLED
```

**Key difference**: The orchestrator **always** reaches the LLM. Grounding validation determines the *prompt mode*, not whether the LLM is called at all.

### Divergence Point

[app.py:2123-2132](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/campus_rag_chatbot/app.py#L2123-L2132) — The `if is_directory_query(query):` check intercepts the query **before** it reaches the orchestrator (line 2134).

### What the Orchestrator Already Does for Directory Queries

The orchestrator already has built-in directory awareness:

| Capability | Location | Status |
|-----------|----------|--------|
| `is_directory_query()` check | [_apply_governance:580](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/campus_rag_chatbot/response_orchestrator.py#L580) | ✅ Already implemented |
| `GovernanceResult.is_directory_query` flag | [line 96](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/campus_rag_chatbot/response_orchestrator.py#L96) | ✅ Already implemented |
| Intent set to `"directory"` | [_apply_governance:589-590](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/campus_rag_chatbot/response_orchestrator.py#L589-L590) | ✅ Already implemented |
| Strict RAG prompt: "say you don't have verified information" | [SYNTHESIS_PROMPTS\[RAG_AUTHORITATIVE\]:164](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/campus_rag_chatbot/response_orchestrator.py#L164) | ✅ Already implemented |

---

## 2. Target Unified Architecture

### Post-Change Control Flow

```
Query → [doc clarification check — unchanged]
      → response_orchestrator.process_query()
        → Governance: is_directory_query flag set (no control flow change)
        → Hybrid retrieval: normalized query, vector search, grounding, semantic relevance
        → Deterministic extractors: attempted (will not match directory queries)
        → Mode determination: RAG_AUTHORITATIVE if grounded, GENERAL_KNOWLEDGE if not
        → LLM synthesis: ALWAYS called with appropriate prompt
        → LLM decides if context is sufficient, responds naturally
```

### What Changes

| Aspect | Before | After |
|--------|--------|-------|
| Entry point | `is_directory_query()` early exit | Falls through to orchestrator |
| Confidence gate | HIGH required pre-LLM | No pre-LLM gate |
| LLM invocation | Conditional (HIGH only) | Always |
| Fallback message | Hardcoded string | LLM decides |
| Retrieval | Direct `similarity_search` | Hybrid retrieval + grounding |
| Prompt | Custom directory prompt | Shared `RAG_AUTHORITATIVE` prompt |
| Query normalization | `canonicalize_directory_query()` | Orchestrator's `normalize_text()` |

### What Stays The Same

- `QueryIntent.DIRECTORY` classification — retained in `_apply_governance()`
- `GovernanceResult.is_directory_query` flag — retained for future prompt specialization
- `is_directory_query()` function — retained in `intent_classifier.py`
- All event tracking and logging
- Session context and memory management

---

## 3. Refactor Strategy

### Stage 1: Remove the Early Exit (app.py)

**Remove** the directory query interception block at [app.py:2123-2132](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/campus_rag_chatbot/app.py#L2123-L2132):

```diff
-    # === CHECK FOR DIRECTORY QUERY ===
-    # Directory queries get stricter handling (HIGH confidence required)
-    if is_directory_query(query):
-        intent_metadata = {
-            "intent": "directory",
-            "reasoning": "Location/directory question detected via pattern matching",
-            "raw_classification": "DIRECTORY",
-            "query_length": len(query)
-        }
-        return await handle_directory_query(query, session_id, memory, intent_metadata, session)
```

Directory queries now fall through to `response_orchestrator.process_query()` at line 2134.

### Stage 2: Delete `handle_directory_query()` (app.py)

**Delete** the entire function at [app.py:1862-2021](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/campus_rag_chatbot/app.py#L1862-L2021) (~160 lines).

### Stage 3: Clean Up Imports (app.py)

- Remove `canonicalize_directory_query` from the import at [line 57](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/campus_rag_chatbot/app.py#L57) (if no other callers exist)
- Remove `is_directory_query` from the import at [line 55](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/campus_rag_chatbot/app.py#L55) (if no other callers exist in `app.py`)

> [!NOTE]
> `is_directory_query` is still imported by `response_orchestrator.py` at [line 577](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/campus_rag_chatbot/response_orchestrator.py#L577). The function itself stays in `intent_classifier.py`. Only the `app.py` import becomes unused.

### Stage 4: Verify Streaming Endpoint

The streaming endpoint at [app.py:2244](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/campus_rag_chatbot/app.py#L2244) uses `process_query_streaming()` which already goes through the same orchestrator layers. **No changes needed.**

---

## 4. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| **LLM hallucination on unfound locations** | Medium | The `RAG_AUTHORITATIVE` prompt already instructs: *"If the documents don't contain the answer, say 'I don't have verified information about that.'"* The LLM is explicitly told not to invent locations. |
| **Grounding may reject valid directory chunks** | Low | The orchestrator uses `validate_grounding()` with `allow_semantic_override=True`, which is actually more forgiving than the old HIGH confidence gate. |
| **Loss of query canonicalization** | Low | The orchestrator uses `normalize_text()` which handles basic normalization. The `canonicalize_directory_query()` conversion (e.g., "where is the library" → "library location") is removed, but the LLM can handle natural-language queries equally well. |
| **Mode string in ChatResponse changes** | Very Low | Old: `mode="directory"`. New: `mode="campus"` or `mode="general"`. This is cosmetic — the UI treats both identically. No functional impact. |
| **Event tracking differences** | Very Low | Old: explicit `QUERY_RECEIVED`/`ANSWER_REFUSED`/`ANSWER_RETURNED` tracking. New: existing orchestrator event tracking at [app.py:2147-2165](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/campus_rag_chatbot/app.py#L2147-L2165) covers all modes. |

---

## 5. Validation Plan

### Automated Checks

Run the following test queries via `/chat` and verify:

| Test Query | Expected Behavior |
|------------|-------------------|
| "Where is the library?" | LLM called, RAG context passed, natural answer |
| "Where is the CESO office?" | LLM called, answer based on retrieved context |
| "Where is room SP303?" | LLM called, answer or "I don't have verified information" |
| "Where is simulation room" | LLM called, no hardcoded fallback |
| "What are the library hours?" | Normal campus flow — unaffected |
| "What is 5 + 5?" | Math engine fast path — unaffected |
| "Hello" | General greeting — unaffected |

### Verification Checklist

- [ ] No `handle_directory_query` function exists in `app.py`
- [ ] No `if is_directory_query(query)` early exit in chat endpoint
- [ ] Directory queries produce LLM-generated answers
- [ ] No hardcoded fallback string appears in responses
- [ ] `GovernanceResult.is_directory_query` still set correctly in orchestrator
- [ ] Non-directory queries behave identically to before
- [ ] Streaming endpoint (`/chat/stream`) unaffected
- [ ] Debug info shows `routing_path: orchestrator:*` for directory queries
- [ ] No unused imports remain

---

## 6. Architectural Integrity Check

| Criterion | ✅ Confirmed |
|-----------|-------------|
| Preserves unified RAG-only architecture | Single retrieval path for all queries |
| Does not reintroduce entity logic | No entity code touched or added |
| Maintains clean separation of concerns | Orchestrator handles retrieval+synthesis; app.py handles routing |
| Improves architectural consistency | Removes last special-case branching in chat endpoint |
| Reduces special-case branching | Eliminates 170+ lines of directory-specific code |
| `DIRECTORY` intent classification retained | `_apply_governance()` still sets the flag for future use |

### Files Changed

| File | Change | Lines |
|------|--------|-------|
| [app.py](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/campus_rag_chatbot/app.py) | Delete `handle_directory_query()` function + early exit block + unused imports | ~170 lines removed |

### Files Unchanged

| File | Reason |
|------|--------|
| `response_orchestrator.py` | Already has full directory awareness |
| `intent_classifier.py` | `is_directory_query()` and `QueryIntent.DIRECTORY` retained |
| `text_normalizer.py` | `canonicalize_directory_query()` can remain for potential future use |
| `confidence_scorer.py` | No changes needed |
| Admin UI | No changes needed |
