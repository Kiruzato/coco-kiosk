You are working on the **CoCo Campus RAG Chatbot kiosk system**.

The RAG package management page is located at:

```
http://localhost:8000/admin#rag-package
```

---

# Objective

Update the **RAG Package ingestion instructions and upload label text** to reflect the current workflow using the **Ingestion Module**, instead of the previous command-line ingestion process.

If the wording of the new instructions sounds grammatically incorrect or unclear, improve the wording while **preserving the intended meaning**.

---

# Task 1 — Update the RAG Package Instructions

Currently, the page shows instructions similar to:

```
How to Create a RAG Package
On your development machine, run: python -m coco_ingestion.ingest <documents_folder>
Find the generated package at: Desktop/CoCo_RAG_Packages/
Upload the .zip file here

Package Requirements
Must be a .zip file
Must contain: index.faiss, index.pkl
```

Replace these instructions with updated instructions that reflect the **current ingestion workflow using the Ingestion Module GUI/tool**.

Target wording (improve grammar if needed):

```
How to Create a RAG Package
On your computer or laptop, run the Ingestion Module.
Select the folder containing the files you want to ingest and proceed.
Find the generated package in the same folder.
Upload the .zip file here.

Package Requirements
Must be a .zip file.
```

You may refine this wording if necessary so it sounds **clear, professional, and natural**.

Do **not reintroduce references to the old command-line ingestion system**.

---

# Task 2 — Update the Upload Label

On the same page, the upload field currently shows a label similar to:

```
Choose a .zip file or drag and drop
```

Modify this label to display only:

```
Choose a .zip file
```

The **"drag and drop" text must be removed**.

Ensure the change does not break the upload component behavior.

---

# Implementation Requirements

* Update only the **UI text content**, not the backend logic.
* Ensure the layout and styling remain consistent.
* Avoid introducing UI regressions.

---

# Code Quality Requirements

While implementing these changes:

* follow **industry-standard best practices**
* apply **proper refactorization and modularization**
* avoid hardcoding duplicated text across multiple components
* ensure the UI text remains **maintainable and centralized where possible**.

---

# Validation

Verify that:

* the new instructions appear correctly in `/admin#rag-package`
* the instructions reflect the **Ingestion Module workflow**
* the upload label now displays **"Choose a .zip file"**
* the upload functionality continues to work normally.

---

# Goal

Update the **RAG package instructions and upload label** so they correctly reflect the **current ingestion workflow using the Ingestion Module**, while improving clarity and maintaining a clean, maintainable UI implementation.
