# Phase 4 Quick Start Guide

## What Phase 4 Adds

Phase 4 makes the RAG system **measurable and inspectable** by adding:

1. **Confidence Scoring** - Every answer gets High/Medium/Low confidence
2. **Grounding Validation** - Rejects low-confidence answers
3. **Structured Logging** - JSON logs for all queries, retrievals, responses
4. **Offline Evaluation** - Tools to replay queries and compare parameters

## Quick Start (5 Minutes)

### Step 1: Install (if needed)

```bash
pip install -r requirements.txt
```

### Step 2: Ingest Documents

```bash
# Ingest sample documents
python admin.py ingest data/
```

### Step 3: Run Chatbot with Confidence Scoring

```bash
python main.py
```

**What you'll see:**
- Answers with confidence scores (High/Medium/Low)
- Similarity scores and metrics
- Source citations
- Grounding validation (rejects low-confidence queries)
- Logs saved to `logs/` directory

**Example output:**
```
Turn 1
================================================================================
User: What are the library hours?
--------------------------------------------------------------------------------
Assistant: According to the Library Hours and Services section in
campus_info.txt, the Springfield University Library is open Monday through
Friday from 8:00 AM to 10:00 PM...

Confidence: High (92/100)
  - Average Similarity: 0.856
  - Chunks Retrieved: 3
  - Reason: Strong relevance with consistent scores

Sources Used:
  From campus_info.txt:
    - Section: Library Hours and Services (Chunk 0)
--------------------------------------------------------------------------------
```

### Step 4: Inspect Logs

```bash
# View log summary
python -c "from query_logger import print_log_summary; print_log_summary()"
```

**Output:**
```
================================================================================
LOG SUMMARY
================================================================================
Total Queries:    5
Total Retrievals: 5
Total Responses:  5

Confidence Distribution:
  High: 3
  Medium: 1
  Low: 1

Retrieval Statistics:
  Avg Chunks per Query: 3.0
  Avg Similarity Score: 0.712
================================================================================
```

### Step 5: Run Evaluation Tools

```bash
python evaluate_demo.py
```

**What it does:**
- Replays logged queries
- Compares different retrieval parameters
- Analyzes parameter impact
- Runs batch evaluation
- Shows you how to optimize the system

## Core Concepts

### 1. Confidence Levels

| Level | Meaning | Criteria |
|-------|---------|----------|
| **High** | Very reliable answer | avg_similarity ≥ 0.75, multiple chunks, consistent scores |
| **Medium** | Reasonably reliable | avg_similarity ≥ 0.55, at least one good chunk |
| **Low** | Not reliable | Low similarity or no chunks found |

### 2. Grounding Validation

**Before Phase 4:**
- System would generate an answer even with weak retrieval
- No way to know if answer was well-grounded

**With Phase 4:**
- System checks confidence before answering
- If confidence < Medium: Refuses with explicit message
- User knows when system doesn't have good information

**Example:**
```
User: What is the weather like today?

Confidence: Low (15/100)
  - Average Similarity: 0.12
  - Chunks Retrieved: 0
  - Reason: Insufficient chunks (0 < 1)

⚠ Answer rejected due to low confidence (grounding validation failed)
```

### 3. Structured Logs

Three log files track everything:

**queries.jsonl** - What users asked
**retrievals.jsonl** - What chunks were retrieved
**responses.jsonl** - What answers were given

**Format:** JSON Lines (.jsonl) - one JSON object per line

### 4. Offline Evaluation

**Replay a query:**
```python
from evaluation import quick_test
quick_test("What are the library hours?", show_chunks=True)
```

**Compare parameters:**
```python
from evaluation import compare_retrieval_parameters
compare_retrieval_parameters(
    query="What IT services are available?",
    top_k_values=[2, 4, 6],
    threshold_values=[0.4, 0.5, 0.6]
)
```

## Common Use Cases

### Use Case 1: Find Low-Confidence Queries

```python
from query_logger import LogReader

reader = LogReader()
low_conf_queries = reader.get_low_confidence_queries()

for query in low_conf_queries:
    print(f"Query: {query['query']}")
    print(f"Confidence: {query['confidence_level']}")
    print(f"Metrics: {query['confidence_metrics']}")
    print()
```

**Why:** Identify gaps in your knowledge base

### Use Case 2: Optimize Retrieval Parameters

```python
from evaluation import analyze_parameter_impact

queries = [
    "What are the library hours?",
    "How much does parking cost?",
    "What IT services are available?"
]

results = analyze_parameter_impact(
    queries=queries,
    parameter_name="top_k",
    parameter_values=[2, 4, 6, 8]
)
```

**Why:** Find the best top_k setting for your use case

### Use Case 3: Test Before Deployment

```python
from evaluation import batch_evaluate

test_queries = [
    "What are the library hours?",
    "How much does parking cost?",
    # ... your test queries
]

results = batch_evaluate(test_queries)

if results['high_confidence'] / results['total_queries'] < 0.5:
    print("⚠ Warning: Less than 50% high confidence")
```

**Why:** Ensure quality before launching to users

## Key Files

| File | Purpose |
|------|---------|
| `confidence_scorer.py` | Computes confidence scores |
| `query_logger.py` | Structured logging |
| `evaluation.py` | Offline evaluation tools |
| `main.py` | Updated chatbot with confidence |
| `evaluate_demo.py` | Evaluation examples |
| `logs/queries.jsonl` | All user queries (auto-generated) |
| `logs/retrievals.jsonl` | All retrievals (auto-generated) |
| `logs/responses.jsonl` | All responses (auto-generated) |

## Configuration

### Adjust Confidence Thresholds

Edit `confidence_scorer.py`:
```python
# Make confidence stricter
HIGH_SIMILARITY_THRESHOLD = 0.80  # default: 0.75
MEDIUM_SIMILARITY_THRESHOLD = 0.65  # default: 0.55
```

### Change Minimum Confidence to Answer

Edit `main.py`:
```python
# Only answer HIGH confidence queries
MIN_CONFIDENCE_TO_ANSWER = ConfidenceLevel.HIGH  # default: MEDIUM

# Answer all queries (no rejection)
MIN_CONFIDENCE_TO_ANSWER = ConfidenceLevel.LOW
```

### Adjust Retrieval Parameters

Edit `main.py`:
```python
RETRIEVAL_TOP_K = 6  # default: 4 (get more chunks)
RELEVANCE_SCORE_THRESHOLD = 0.4  # default: 0.5 (lower threshold)
```

## Troubleshooting

**Problem:** All queries have low confidence

**Solution:**
1. Lower `RELEVANCE_SCORE_THRESHOLD` to 0.4
2. Increase `RETRIEVAL_TOP_K` to 6 or 8
3. Check if documents are properly ingested

**Problem:** System rejects good queries

**Solution:**
1. Set `MIN_CONFIDENCE_TO_ANSWER = ConfidenceLevel.LOW`
2. Lower `MEDIUM_SIMILARITY_THRESHOLD` to 0.50
3. Increase `RETRIEVAL_TOP_K`

**Problem:** No logs generated

**Solution:**
- Run `python main.py` first
- Check that `logs/` directory exists
- Verify write permissions

## Next Steps

1. **Analyze Your Logs**
   ```bash
   python -c "from query_logger import print_log_summary; print_log_summary()"
   ```

2. **Find Problem Queries**
   ```python
   from query_logger import LogReader
   reader = LogReader()
   low_conf = reader.get_low_confidence_queries()
   ```

3. **Optimize Parameters**
   ```bash
   python evaluate_demo.py
   ```

4. **Add More Documents**
   ```bash
   python admin.py ingest path/to/new/docs
   ```

5. **Test Again**
   ```bash
   python main.py
   ```

## Cost

Phase 4 adds **zero additional cost**:
- Confidence computation: Local (free)
- Logging: Local file writes (free)
- Evaluation: Only when you run it manually

## Summary

Phase 4 transforms the chatbot from a "black box" into an **inspectable, measurable system**:

- ✅ Know when answers are reliable (confidence scoring)
- ✅ Prevent bad answers (grounding validation)
- ✅ Track everything (structured logging)
- ✅ Optimize performance (offline evaluation)
- ✅ Continuous improvement (data-driven)

**Result:** A production-ready RAG system you can trust and improve over time.

---

For detailed documentation, see `PHASE4_SUMMARY.md`
