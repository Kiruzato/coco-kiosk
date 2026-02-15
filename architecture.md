# Architecture Overview
This document serves as a critical, living template designed to equip agents with a rapid and comprehensive understanding of the codebase's architecture, enabling efficient navigation and effective contribution from day one. Update this document as the codebase evolves.

## 1. Project Structure
This section provides a high-level overview of the project's directory and file structure, categorised by architectural layer or major functional area. It is essential for quickly navigating the codebase, locating relevant files, and understanding the overall organization and separation of concerns.

```
[Project Root]/
├── campus_rag_chatbot/       # Core Application Package
│   ├── app.py                # Main FastAPI Application entry point
│   ├── main.py               # Alternative entry point / runner
│   ├── voice/                # Voice Module (STT/TTS Services)
│   │   ├── config.py         # Voice configuration (Models, threads)
│   │   ├── stt_service.py    # Speech-to-Text abstraction (Whisper, Google)
│   │   ├── tts_service.py    # Text-to-Speech abstraction (Piper, Edge, OpenAI)
│   │   ├── usage_tracker.py  # Usage quota tracking for paid APIs
│   │   └── models/           # Local model storage (Whisper.cpp, Piper onnx)
│   ├── static/               # Frontend Assets (HTML/JS/CSS)
│   │   ├── index.html        # Main Chat Interface
│   │   ├── admin.html        # Admin Dashboard
│   │   ├── dev.html          # Developer Debug Panel
│   │   ├── app.js            # Frontend Chat Logic
│   │   └── admin.js          # Admin Interaction Logic
│   ├── data/                 # Runtime Data Storage
│   │   ├── debug_settings.json # Persisted debug toggle state
│   │   └── directory_entities.json # Entity registry data
│   ├── logs/                 # Application Logs
│   ├── reports/              # Generation Reports and Analysis
│   ├── document_manager.py   # Document Ingestion & Registry Logic
│   ├── retrieval_validator.py # Hybrid RAG & Grounding Logic
│   ├── response_orchestrator.py # LLM Synthesis & Response Management
│   ├── vector_store/         # FAISS Vector Database (Persisted)
│   └── voice_routes.py       # Voice API Endpoints
├── documents_to_ingest/      # Staging Area for Raw Documents
├── scripts/                  # Utility Scripts
├── tests/                    # Unit and Integration Tests
├── requirements.txt          # Python Dependencies
├── architecture_template.md  # Architecture Template
└── RPI5_DEPLOYMENT_INSTRUCTIONS.txt # Deployment Guide
```


## 2. High-Level System Diagram
The CoCo Chatbot uses a Retrieval-Augmented Generation (RRF Hybrid) architecture with a voice-first interface capability.

```mermaid
graph TD
    User[User (Web/Kiosk)] <-->|HTTPS/WebSocket| Frontend[Frontend (HTML/JS)]
    Frontend <-->|REST API| Backend[FastAPI Backend]
    
    subgraph "Core Application Layer"
        Backend -->|Orchestrates| Orchestrator[Response Orchestrator]
        Backend -->|Audio I/O| VoiceService[Voice Service (STT/TTS)]
    end

    subgraph "Domain / RAG Layer"
        Orchestrator -->|Query| Retrieval[Retrieval Validator]
        Retrieval -->|Hybrid Search| VectorStore[(FAISS Vector Store)]
        Retrieval -->|Keyword Search| BM25[Keyword Scorer]
        Retrieval -->|Synthesize| LLM[LLM (OpenAI GPT-4o-mini)]
        
        Ingestion[Document Ingestion] -->|Process| VectorStore
        Ingestion -->|Metadata| DocRegistry[Document Registry]
    end

    subgraph "Infrastructure"
        VoiceService -->|Local| Whisper[Whisper.cpp (STT)]
        VoiceService -->|Local| Piper[Piper (TTS)]
        VoiceService -->|Cloud Fallback| CloudAPIs[Google/OpenAI APIs]
    end
```

## 3. Core Components

### 3.1. Frontend
Name: **Kiosk Web Interface**

Description: A lightweight, responsive web interface designed for touch-screen kiosks. It provides a chat-like experience with voice input triggers. It includes an Admin Panel for document management and a Dev Panel for real-time debugging.

Technologies: HTML5, CSS3, Vanilla JavaScript (No framework), WebSocket (for streaming).

Deployment: Served statically via FastAPI (`/static`).

### 3.2. Backend Services

#### 3.2.1. Main Application API
Name: **Campus RAG Chatbot API**

Description: The central brain of the system. It exposes REST endpoints for chat, voice interaction, and administration. It handles session management, query intent classification, and RAG orchestration.

Technologies: Python 3.11, FastAPI, Uvicorn.

Deployment: Runs as a systemd service on Linux (RPi5) or local process on Windows.

### 3.3. Domain Components

#### 3.3.1. RAG Engine
Name: **Hybrid Retrieval Validator**

Description: Implements "Sub-Question Query Engine" logic. It uses **Reciprocal Rank Fusion (RRF)** to combine Vector Similarity (Semantic) and Keyword Matching (Lexical).
- **Semantics**: FAISS Vector Store with OpenAI Embeddings.
- **Lexical**: Custom Keyword Scorer (BM25-like).
- **Grounding**: Strict verification to ensure answers are supported by retrieved chunks, with a "Semantic Override" for long-form content (e.g., hymns/prayers).

Technologies: LangChain, FAISS, OpenAI Embeddings (`text-embedding-3-small` implied).

#### 3.3.2. Voice Orchestrator
Name: **Offline-First Voice Service**

Description: Manages speech-to-text and text-to-speech pipelines. Prioritizes local execution for low latency and privacy, falling back to cloud providers only when necessary.
- **STT**: Local `whisper.cpp` (ggml-tiny) -> Fallback: OpenAI Whisper.
- **TTS**: Local `piper` (onnx-amy-medium) -> Fallback: EdgeTTS / OpenAI TTS.

Technologies: Whisper.cpp-python, Piper-tts, PyAudio (implied).

#### 3.3.3. Ingestion Pipeline
Name: **Document Manager**

Description: Handles parsing and indexing of PDF, DOCX, and TXT files.
- **Layout-Aware**: Uses `unstructured` to parse PDFs, preserving section hierarchies.
- **Enumeration Handling**: "Hard Merge" logic for administrative roles (Deans, Directors) to ensure complete lists are retrieved.
- **Registry**: file-based JSON registry for duplicate detection and metadata management.

## 4. Data Stores

### 4.1. Vector Database
Name: **FAISS Index**
Type: **Local File-Based (FAISS)**
Purpose: Stores high-dimensional vector embeddings of document chunks for semantic similarity search.
Key Schemas: Chunks with metadata (`document_id`, `section`, `page_number`, `is_appendix`).

### 4.2. Document Registry
Name: **Document Registry**
Type: **JSON File (`document_registry.json`)**
Purpose: Tracks ingested files to prevent duplicates and manage updates.
Key Schemas: File Hash (SHA256), Timestamp, Document ID, File Path.

### 4.3. Session Storage
Name: **In-Memory Session Store**
Type: **Python Dictionary (RAM)**
Purpose: Stores active chat sessions, conversation history, and context (intent, last entity).
Retention: 30-minute timeout for user sessions.

## 5. External Integrations / APIs

### 5.1. OpenAI Platforms
Service Name: **OpenAI API**
Purpose: 
1. **LLM**: `gpt-4o-mini` for response synthesis and intent classification.
2. **Embeddings**: `text-embedding-3-small` (implied standard) for vectorization.
Integration Method: LangChain SDK / OpenAI Python SDK.

### 5.2. Google Cloud Platform (Optional)
Service Name: **Google Cloud STT**
Purpose: Cloud-based Speech-to-Text fallback or primary provider (configurable).
Integration Method: Google Cloud Speech Client Library.

## 6. Deployment & Infrastructure
Cloud Provider: **Hybrid / Edge (primary)**. Application is designed to run on **Edge Devices**.

Key Services Used:
- **Raspberry Pi 5 (8GB RAM)**: Primary production target.
- **Windows**: Development and Kiosk alternative.

CI/CD Pipeline: Manual / Script-based (`scripts/` folder).
- `rpi-setup.sh`: Deployment automation for RPi.
- `win-setup.ps1`: Setup for Windows.

Monitoring & Logging: 
- **Application Logs**: File-based (`logs/server.log`).
- **Telemetry**: `EventTracker` writes to CSV/JSONL.
- **Dev Panel**: Real-time debug view (`/static/dev.html`).

## 7. Security Considerations

Authentication:
- **User**: Anonymous / Session-based (cookie-less session ID).
- **Admin**: Token-based authentication (`ADMIN_API_KEY`, `ADMIN_PASSWORD` in `.env`).

Data Encryption:
- **In-Transit**: HTTPS (Reverse Proxy required for production).
- **At-Rest**: Vector store and JSON registry are unencrypted text/binary files (Internal network only).

Key Security Tools/Practices:
- **Input Sanitization**: `text_normalizer.py` cleans inputs.
- **Rate Limiting**: Implemented for Voice endpoints (30 req/min).

## 8. Development & Testing Environment

Local Setup Instructions: 
1. Install Python 3.11+.
2. Create Venv & Install `requirements.txt`.
3. Configure `.env` (OpenAI Keys).
4. Run `python app.py` or use `win-setup.ps1`.

Testing Frameworks: `pytest` (Backend).

Code Quality Tools: Standard Python linting (implied).

## 9. Future Considerations / Roadmap
1. **Response Latency**: Moving to `whisper.cpp` streaming and VAD (Voice Activity Detection) improvements.
2. **LLM Independence**: Investigating local LLMs (Llama 3 8B) for fully offline RAG on RPi5.
3. **Database Migration**: Moving from JSON/FAISS to SQLite/ChromaDB for better scalability if dataset grows >10k docs.
4. **frontend Framework**: Migrating from Vanilla JS to React/Vue for complex UI states.

## 10. Project Identification
Project Name: **CoCo (Campus RAG Chatbot)**
Repository URL: *Internal / Local*
Primary Contact: Retrieval & Voice Architecture Team
Date of Last Update: 2026-02-15

## 11. Glossary / Acronyms
- **RAG**: Retrieval-Augmented Generation
- **RRF**: Reciprocal Rank Fusion (Algorithm for combining search results)
- **STT**: Speech-to-Text (ASR)
- **TTS**: Text-to-Speech
- **LLM**: Large Language Model
- **Grounding**: Verification process to ensure AI answers are supported by facts.
- **RPi**: Raspberry Pi (Single Board Computer)
