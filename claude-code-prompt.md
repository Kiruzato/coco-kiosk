You are working on the **CoCo Campus RAG Chatbot project**, specifically the **INGESTION_MODULE**.

I am preparing for a **Thesis Defense**, and I need a **clear technical explanation of how the ingestion pipeline actually works** in the system.

Your task is to **analyze the ingestion module and generate a report explaining the full ingestion process**.

---

# Objective

Produce a **detailed report explaining exactly how document ingestion works in INGESTION_MODULE**.

This report must help me clearly understand:

* how documents are processed
* how chunks are created
* how chunks are divided
* what rules determine chunk boundaries
* how embeddings are generated
* how the vector store is built.

The report should focus strictly on **the ingestion behavior and internal processes**, **not the UI**.

---

# Important Topic I Need Clarified

One key thing I want to understand is something like what I call:

**"early chunk cut-off" behavior**

My terminology may not be correct, so you must determine what I am referring to.

Specifically investigate whether the ingestion system has behaviors such as:

* chunk truncation
* sentence boundary trimming
* paragraph boundary handling
* token limits
* chunk overlap rules
* chunk splitting heuristics
* text normalization before chunking.

Explain clearly:

* what **rules determine when a chunk stops**
* whether chunking happens **by token count, characters, paragraphs, or sentences**
* whether **overlap between chunks exists**
* whether chunks can be **cut mid-sentence**
* whether chunks are **adjusted to sentence boundaries**.

---

# Required Sections in the Report

Generate a report that includes the following sections:

### 1. Ingestion Pipeline Overview

Explain the complete ingestion flow from:

```
input documents
→ preprocessing
→ chunking
→ embedding generation
→ vector index creation
→ packaging into RAG zip
```

---

### 2. Document Processing

Explain:

* supported file types
* how documents are read and parsed
* whether any text cleaning or normalization occurs.

---

### 3. Chunking Strategy

Provide a **very detailed explanation of chunking**, including:

* chunk size rules
* overlap rules
* splitting logic
* sentence handling
* paragraph handling
* token limits.

Explain **exactly how a chunk is created from raw text**.

---

### 4. Chunk Boundary Rules

Explain:

* what determines when a chunk stops
* whether early truncation occurs
* whether chunk boundaries try to align with sentences or paragraphs.

---

### 5. Embedding Generation

Explain:

* which embedding model is used
* how embeddings are generated for chunks.

---

### 6. Vector Store Creation

Explain:

* how FAISS index is created
* how metadata is stored.

---

### 7. RAG Package Generation

Explain:

* what files are placed in the RAG package
* how the zip file is built
* how the system expects the package to be structured.

---

### 8. Dead Code Check

While analyzing the ingestion module:

* detect any **dead code**
* detect unused chunking logic
* detect unused preprocessing logic.

Do **not rely on the presence of code alone** — determine whether the code is **actually used in the ingestion pipeline**.

---

# Output Format

Save the report as a **.txt file** in the project root.

Example filename:

```
ingestion_process_report.txt
```

---

# Code Quality Requirements

While analyzing the system:

* follow **industry standard engineering practices**
* ensure the analysis is **accurate and based on actual code execution paths**
* avoid describing **dead or unused code** as part of the ingestion pipeline.

---

# Goal

Produce a **clear, technically accurate report explaining exactly how the INGESTION_MODULE performs document ingestion and chunking**, so that I can:

* confidently explain the system during **Thesis Defense**
* understand how to **prepare documents optimally for ingestion**.
