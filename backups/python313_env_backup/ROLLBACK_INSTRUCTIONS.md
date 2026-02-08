# Rollback Instructions - Python 3.13 Environment

## If Python 3.12 migration fails, follow these steps:

### 1. Restore Python 3.13 environment
```bash
# Use Python 3.13 again
py -3.13 -m venv venv313
venv313\Scripts\activate

# Install exact packages from backup
pip install -r backups/python313_env_backup/requirements_frozen.txt
```

### 2. Restore requirements.txt
```bash
cp backups/python313_env_backup/requirements_original.txt campus_rag_chatbot/requirements.txt
```

### 3. Restore data (if corrupted)
```bash
cp -r backups/python313_env_backup/data_backup/* campus_rag_chatbot/data/
```

### 4. Switch TTS to edge-tts (workaround)
If Piper still doesn't work, update voice_settings.json:
```json
{
  "tts_provider": "edge-tts"
}
```

## Original Environment Details
- Python: 3.13.5
- Date: 2026-02-07
- Reason for migration: Piper TTS incompatibility with Python 3.13
