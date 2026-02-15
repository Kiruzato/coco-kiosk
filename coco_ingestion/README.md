# CoCo Standalone Ingestion Module

This module processes documents and creates vector store packages for deployment to Raspberry Pi or other runtime environments.

## Why Standalone?

The Raspberry Pi runs in **runtime mode only** - it loads and uses pre-built vector stores but does NOT perform document ingestion. This design:

- Reduces RPi resource usage (no heavy embedding computation)
- Ensures consistent vector stores across deployments
- Speeds up RPi setup (no ingestion step)
- Allows document updates without RPi access

## Usage

### Basic Usage

```bash
# From project root
cd vibecoding_coco

# Ingest from default folder (campus_rag_chatbot/documents_to_ingest/)
python -m coco_ingestion.ingest

# Ingest from custom folder
python -m coco_ingestion.ingest ./my_documents

# Custom settings
python -m coco_ingestion.ingest --chunk-size 1000 --chunk-overlap 100
```

### Output

The module creates a timestamped package folder **inside the documents folder**:

```
my_documents/
├── file1.pdf
├── file2.docx
└── rag_package_2026-02-15_14-30/      <-- Output here
    ├── vector_store/
    │   ├── index.faiss
    │   └── index.pkl
    ├── document_registry.json
    └── rag_package_2026-02-15_14-30.zip  (ready for upload)
```

## Deploying to Raspberry Pi

### Option 1: Admin UI Upload (Recommended)

1. Open Admin UI: `http://<rpi-ip>:8000/admin`
2. Click **RAG Package** in sidebar
3. Upload the `.zip` file
4. Vector store reloads automatically

### Option 2: Manual Copy

```bash
# On your dev machine
scp -r campus_rag_2026-02-15_14-30/vector_store/ pi@<rpi-ip>:/home/pi/coco/campus_rag_chatbot/

# On RPi - restart server
sudo systemctl restart coco
```

### Option 3: Git (for version control)

```bash
# Copy to project
cp -r campus_rag_2026-02-15_14-30/vector_store/ campus_rag_chatbot/

# Commit
git add campus_rag_chatbot/vector_store/
git commit -m "Update vector store"
git push

# On RPi
git pull
sudo systemctl restart coco
```

## Requirements

- Python 3.8+
- OpenAI API key (for embeddings)
- Dependencies from `campus_rag_chatbot/requirements.txt`

## Environment Variables

Create `.env` in `campus_rag_chatbot/`:

```
OPENAI_API_KEY=sk-your-key-here
```

## Supported Document Formats

- `.txt` - Plain text
- `.pdf` - PDF documents (layout-aware parsing if tesseract installed)
- `.docx` - Microsoft Word documents
