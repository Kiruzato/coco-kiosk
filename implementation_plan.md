# RPI5 Deployment Preparation Plan

## 1. Current State Assessment

### Deployment Files Inventory

| File | Purpose | Status |
|------|---------|--------|
| [pi-setup.sh](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/pi-setup.sh) | 7-step automated setup (285 lines) | ⚠️ Has issues |
| [download-voice-models.sh](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/download-voice-models.sh) | Whisper + Piper model downloads (138 lines) | ✅ Good |
| [RPI5_DEPLOYMENT_INSTRUCTIONS.txt](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/RPI5_DEPLOYMENT_INSTRUCTIONS.txt) | 10-phase manual guide (293 lines) | ⚠️ Stale refs |
| [requirements.txt](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/campus_rag_chatbot/requirements.txt) | Python 3.13 deps (62 lines) | ⚠️ Incomplete |
| [requirements_py311.txt](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/campus_rag_chatbot/requirements_py311.txt) | Python 3.11 deps (66 lines) | ⚠️ Dead deps |
| [requirements_rpi.txt](file:///c:/Users/chann/OneDrive/Desktop/restartcoco/vibecoding_coco/campus_rag_chatbot/requirements_rpi.txt) | ARM64 deps (66 lines) | ⚠️ Drift from py311 |
| `.env.example` | API key template | ❌ Does not exist |
| `.gitignore` | Git exclusions | ❌ Does not exist |

### Vector Store Status

Vector store IS committed to git (`index.faiss` + `index.pkl`). The Feb 8 deployment error ("`No vector store found`") was a pre-commit issue that has since been resolved.

---

## 2. Issues Found

### Critical

| # | Issue | Impact |
|---|-------|--------|
| **C1** | `.env.example` does not exist | `pi-setup.sh` line 152/158 runs `cp .env.example .env` — **will fail with error** |
| **C2** | No `.gitignore` at project root | `venv/`, `__pycache__/`, `.env` (with API keys), `*.pyc` are at risk of being pushed to GitHub |

### Moderate

| # | Issue | Detail |
|---|-------|--------|
| **M1** | `requirements.txt` missing `sse-starlette` and `httpx` | Both are imported at `app.py:23-24` — app will crash on Python 3.13 env without them |
| **M2** | `requirements.txt` has `audioop-lts>=0.2.0` without version guard | All 3.11 installs will try to install it (harmless but wasteful); `requirements_rpi.txt` correctly has the `python_version >= "3.13"` guard |
| **M3** | `edge-tts` in `requirements_py311.txt` is dead | Zero imports across entire codebase. TTS uses Piper natively, not Edge TTS |
| **M4** | `pi-setup.sh` line 68 mentions "edge-tts (cloud) as fallback" | Edge TTS is not installed or used. Misleading to the user |
| **M5** | Deployment instructions reference conflicting branches | Clone: `model-1.1` (line 25), Pull: `antigravity-dev-2` (line 288) |
| **M6** | Three requirements files with inconsistent content | `requirements.txt` lacks `sse-starlette`/`httpx`, `requirements_py311.txt` has dead `edge-tts`, `requirements_rpi.txt` missing `python-magic-bin` guard (fine for ARM, but drifting from py311) |

### Minor

| # | Issue | Detail |
|---|-------|--------|
| **m1** | Deployment instructions skip Phase 3 | Phases go 1, 2, 4, 5... |
| **m2** | `pi-setup.sh` Step 5 prompts `Re-ingest documents?` but `deploy_instructions.txt` says to answer N — script has no re-ingest prompt (the message is stale in the instructions) |
| **m3** | `WINDOWS_SETUP_INSTRUCTIONS.txt` and `win-setup.ps1` exist at root level — not relevant for RPI but add clutter |

---

## 3. Recommended Refactors

### 3A. Consolidate Requirements to 2 Files

Currently 3 files with inconsistent overlap. Reduce to:

| File | Target Environment | Differences from base |
|------|-------------------|----------------------|
| `requirements.txt` | Dev/Windows (Python 3.11+) | Includes `python-magic-bin` Windows guard, all deps |
| `requirements_rpi.txt` | RPi/Linux ARM64 | Omits `python-magic-bin`, has ARM64 notes |

**What to unify**:
- Both files should have identical core deps (`sse-starlette`, `httpx`, etc.)
- `audioop-lts` should have `python_version >= "3.13"` guard in both
- Remove `edge-tts` entirely
- Mark `google-cloud-speech` as optional with a comment (gracefully degrades)
- Delete `requirements_py311.txt` (merged into `requirements.txt`)

---

### 3B. Create `.gitignore`

```
# Python
__pycache__/
*.py[cod]
*.pyo
*.egg-info/

# Virtual environments
venv/
venv311/

# Environment variables (contains API keys)
.env

# Voice models (downloaded separately)
campus_rag_chatbot/voice/models/whisper/
campus_rag_chatbot/voice/models/piper/

# OS files
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/

# Logs
*.log
```

> [!IMPORTANT]
> The `vector_store/` directory should **NOT** be gitignored. The RPI runs in runtime mode only — it loads the pre-ingested vector store from git. This is correct and intentional per `pi-setup.sh` design.

---

### 3C. Create `.env.example`

```
# CoCo Campus RAG Chatbot - Environment Configuration
# Copy this file to .env and fill in your values

# Required: OpenAI API Key
OPENAI_API_KEY=sk-your-openai-api-key-here

# Required: Admin panel access
ADMIN_PASSWORD=your_admin_password
ADMIN_API_KEY=your-uuid-api-key

# Optional: Voice integration
VOICE_ENABLED=true

# Optional: Google Cloud STT (requires service account JSON)
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

---

### 3D. Fix `pi-setup.sh`

| Fix | Lines | Change |
|-----|-------|--------|
| Remove edge-tts fallback mention | 68, 193 | Remove references to "edge-tts (cloud) as fallback" |
| Fix .env.example path reference | 146-160 | Add check for `.env.example` existence before `cp`, or inline-generate the template |
| Update venv dir for RPi deploy path | 97 | Currently `$PROJECT_ROOT/venv` — fine, but should match deployment instructions |

---

## 4. GitHub Deployment Workflow

### Pre-Deployment (Dev Machine)

```
1. Ingest documents (if not already done)
   → cd campus_rag_chatbot && python admin.py ingest documents_to_ingest/

2. Verify vector store exists
   → ls campus_rag_chatbot/vector_store/index.faiss

3. Commit vector store to git
   → git add campus_rag_chatbot/vector_store/
   → git commit -m "Update vector store"
   → git push origin <branch>
```

### RPI First-Time Setup

```
1. SSH into RPi5
   → ssh pi@<rpi5-ip>

2. Clone repository
   → mkdir -p /home/pi/coco && cd /home/pi/coco
   → git clone https://github.com/Kiruzato/coco-kiosk.git .

3. Run setup script
   → chmod +x pi-setup.sh
   → ./pi-setup.sh
   (15-30 minutes for full dependency install)

4. Configure environment
   → nano campus_rag_chatbot/.env
   (Set OPENAI_API_KEY, ADMIN_PASSWORD)

5. Configure swap (4GB recommended)
   → sudo fallocate -l 4G /swapfile
   → sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
   → echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

6. Download voice models (optional, ~135MB)
   → chmod +x download-voice-models.sh
   → ./download-voice-models.sh

7. Launch
   → source venv/bin/activate
   → cd campus_rag_chatbot && python app.py
```

### Subsequent Updates

```
1. git pull origin <branch>
2. source venv/bin/activate
3. pip install -r campus_rag_chatbot/requirements_rpi.txt  (if deps changed)
4. cd campus_rag_chatbot && python app.py
```

---

## 5. RPI5 Performance Considerations

| Factor | Constraint | Mitigation |
|--------|-----------|------------|
| **RAM** (8GB) | Vector store + LangChain + FastAPI = ~1.5-2GB baseline | 4GB swap file covers spikes during ingestion |
| **CPU** (Cortex-A76) | No GPU acceleration for FAISS | Index is pre-built on dev machine; RPi only runs similarity search (fast) |
| **SD Card I/O** | Slow random reads for large models | Voice models load once at startup; vector store cached in memory |
| **Cold start** | First `pip install` takes 15-30 min on ARM64 | Some packages (numpy, cryptography) compile from source on ARM |
| **FAISS on ARM64** | `faiss-cpu` has ARM64 wheels since 1.7.4 | `pi-setup.sh` already has fallback `--no-cache-dir` reinstall |
| **Piper TTS** | Requires Python 3.11 specifically | `pi-setup.sh` already detects and prefers 3.11 |
| **Temperature** | CPU-intensive tasks can throttle at >80°C | Active cooling (fan) recommended; kiosk workload is I/O-bound, not CPU-bound |
| **Network** | LLM calls require stable internet to OpenAI | Wired Ethernet recommended; WiFi is fallback |

---

## 6. Risk Assessment

| Risk | Probability | Severity | Mitigation |
|------|------------|----------|------------|
| `pip install` fails mid-way on ARM64 | Medium | High | Add `--retries 3 --timeout 120` to pip calls in `pi-setup.sh` |
| `piper-tts` wheel unavailable for ARM64 Python | Low | Medium | `pi-setup.sh` already has fallback messaging; espeak-ng is installed as backup |
| SD card corruption during writes | Low | High | Use `raspi-config` to enable filesystem journaling; regular backups |
| OpenAI API key exposed in git | Medium | Critical | `.gitignore` + `.env.example` pattern prevents this |
| `unstructured[pdf]` build fails on ARM64 | Medium | Medium | Large package with many C dependencies; consider adding `--no-binary :all:` fallback or pre-built wheel cache |
| Python 3.11 not in Bookworm repos | Low | Medium | Bookworm ships 3.11.2 by default; script already handles fallback |

---

## 7. Validation Checklist

### Post-Setup Verification

- [ ] `python app.py` starts without errors
- [ ] `curl http://localhost:8000/health` returns 200
- [ ] Browser at `http://<rpi5-ip>:8000/` loads the kiosk UI
- [ ] Test query returns LLM-generated answer
- [ ] Admin panel accessible at `/admin`
- [ ] `free -m` shows >500MB available after startup
- [ ] `vcgencmd measure_temp` shows <75°C under load

### Deployment Script Verification

- [ ] `.env.example` exists and `pi-setup.sh` copies it successfully
- [ ] `.gitignore` prevents `venv/`, `.env`, `__pycache__/` from being committed
- [ ] `vector_store/index.faiss` and `index.pkl` are in the git repo
- [ ] `requirements_rpi.txt` installs without errors on ARM64 Python 3.11
- [ ] Voice model download completes successfully
- [ ] Systemd service starts and survives reboot (optional)

### Non-Regression

- [ ] Non-directory queries work identically
- [ ] Directory queries reach the LLM via orchestrator
- [ ] Streaming endpoint `/chat/stream` works
- [ ] Voice STT/TTS works (if models downloaded)

---

## Summary of Proposed Changes

| File | Action | Severity |
|------|--------|----------|
| `.gitignore` | **[NEW]** Create at project root | Critical |
| `.env.example` | **[NEW]** Create in `campus_rag_chatbot/` | Critical |
| `requirements.txt` | **[MODIFY]** Add `sse-starlette`, `httpx`, fix `audioop-lts` guard | Moderate |
| `requirements_py311.txt` | **[DELETE]** Merge into `requirements.txt` | Moderate |
| `requirements_rpi.txt` | **[MODIFY]** Sync with updated `requirements.txt` | Moderate |
| `pi-setup.sh` | **[MODIFY]** Remove edge-tts refs, fix `.env.example` handling, add pip retry flags | Moderate |
| `RPI5_DEPLOYMENT_INSTRUCTIONS.txt` | **[MODIFY]** Fix branch references, phase numbering, stale prompts | Minor |
