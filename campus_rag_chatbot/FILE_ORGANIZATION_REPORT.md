# File Organization Report - campus_rag_chatbot/

**Date:** 2026-02-11
**Status:** PENDING APPROVAL - No files moved yet

---

## Executive Summary

After analyzing the `campus_rag_chatbot/` directory, I identified **39 files/directories** that should be moved to improve project organization. These are test scripts, development artifacts, validation reports, backup data, and temporary audio files that are not required for runtime or app startup.

---

## Proposed Directory Structure

```
campus_rag_chatbot/
├── archive/          # Development history & progress notes
├── backups/          # Vector store & registry backups
├── docs/             # Phase summaries & guides
├── reports/          # Test results & validation reports
├── tests/            # Test scripts & test data
└── [existing dirs]   # static/, voice/, data/, etc.
```

---

## Files to Move

### 1. TEST SCRIPTS (7 files) -> `tests/`

| Original Location | New Location | Justification |
|-------------------|--------------|---------------|
| `demo_phase3.py` | `tests/demo_phase3.py` | Demo/test script for Phase 3, not runtime |
| `evaluation.py` | `tests/evaluation.py` | Evaluation script, not runtime |
| `evaluate_demo.py` | `tests/evaluate_demo.py` | Demo evaluation, not runtime |
| `test_phase16_validation.py` | `tests/test_phase16_validation.py` | Phase 16 test script |
| `test_layout_aware_ingestion.py` | `tests/test_layout_aware_ingestion.py` | Ingestion test script |
| `validate_phase18_metadata.py` | `tests/validate_phase18_metadata.py` | Metadata validation script |
| `run_acceptance_tests.py` | `tests/run_acceptance_tests.py` | Test runner, not runtime |

### 2. TEST AUDIO FILES (5 files) -> `tests/audio/`

| Original Location | New Location | Justification |
|-------------------|--------------|---------------|
| `test_audio.wav` | `tests/audio/test_audio.wav` | Test audio artifact |
| `question_audio.wav` | `tests/audio/question_audio.wav` | Test audio artifact |
| `question_audio_normalized.wav` | `tests/audio/question_audio_normalized.wav` | Test audio artifact |
| `test_audio_normalized.wav` | `tests/audio/test_audio_normalized.wav` | Test audio artifact |
| `test_audio_normalized_normalized.wav` | `tests/audio/test_audio_normalized_normalized.wav` | Test audio artifact |

### 3. TEST DATA FILES (2 files) -> `tests/data/`

| Original Location | New Location | Justification |
|-------------------|--------------|---------------|
| `data/test_directory_entities.json` | `tests/data/test_directory_entities.json` | Test fixture data |
| `data/test_directory_entities.csv` | `tests/data/test_directory_entities.csv` | Test fixture data |

### 4. PHASE DOCUMENTATION (5 files) -> `docs/`

| Original Location | New Location | Justification |
|-------------------|--------------|---------------|
| `PHASE2_SUMMARY.md` | `docs/PHASE2_SUMMARY.md` | Historical phase summary |
| `PHASE3_SUMMARY.md` | `docs/PHASE3_SUMMARY.md` | Historical phase summary |
| `PHASE4_SUMMARY.md` | `docs/PHASE4_SUMMARY.md` | Historical phase summary |
| `PHASE4_QUICKSTART.md` | `docs/PHASE4_QUICKSTART.md` | Historical quickstart guide |
| `PHASE5_QUICKSTART.md` | `docs/PHASE5_QUICKSTART.md` | Historical quickstart guide |

### 5. DEVELOPMENT NOTES (5 files) -> `archive/`

| Original Location | New Location | Justification |
|-------------------|--------------|---------------|
| `dev_progress.txt` | `archive/dev_progress.txt` | Development notes |
| `dev_progress2.txt` | `archive/dev_progress2.txt` | Development notes |
| `dev_progress3.txt` | `archive/dev_progress3.txt` | Development notes |
| `run_commands.txt` | `archive/run_commands.txt` | Command reference notes |
| `DIRECTORY_GUIDE.txt` | `archive/DIRECTORY_GUIDE.txt` | Developer reference |

### 6. TEST RESULTS & REPORTS (6 files) -> `reports/`

| Original Location | New Location | Justification |
|-------------------|--------------|---------------|
| `phase13_test_results.txt` | `reports/phase13_test_results.txt` | Test output |
| `phase14_test_results.txt` | `reports/phase14_test_results.txt` | Test output |
| `phase14_1_test_results.txt` | `reports/phase14_1_test_results.txt` | Test output |
| `phase14_comprehensive_test.txt` | `reports/phase14_comprehensive_test.txt` | Test output |
| `phase14_validation_report.txt` | `reports/phase14_validation_report.txt` | Validation report |
| `phase15_validation_report.txt` | `reports/phase15_validation_report.txt` | Validation report |

### 7. BACKUP DATA (9 items) -> `backups/`

| Original Location | New Location | Justification |
|-------------------|--------------|---------------|
| `vector_store_backup_pre_phase18/` | `backups/vector_store_backup_pre_phase18/` | Historical backup |
| `vector_store_backup_pre_phase21/` | `backups/vector_store_backup_pre_phase21/` | Historical backup |
| `vector_store_backup_pre_phase22/` | `backups/vector_store_backup_pre_phase22/` | Historical backup |
| `document_registry_backup.json` | `backups/document_registry_backup.json` | Registry backup |
| `document_registry.json.backup_pre_phase21` | `backups/document_registry.json.backup_pre_phase21` | Registry backup |
| `document_registry.json.backup_pre_phase22` | `backups/document_registry.json.backup_pre_phase22` | Registry backup |
| `data/directory_entities.json.backup_20260131_163452` | `backups/directory_entities.json.backup_20260131_163452` | Entity backup |

---

## Files to KEEP in Place (Runtime Required)

### Core Application Files (KEEP)
- `app.py` - FastAPI server entry point
- `main.py` - Core RAG/chat logic
- `admin.py` - CLI admin interface
- `document_manager.py` - Document ingestion
- `intent_classifier.py` - Query classification
- `confidence_scorer.py` - Confidence scoring
- `text_normalizer.py` - Text normalization
- `text_normalizer_pipeline.py` - Multi-stage normalization
- `entity_analyzer.py` - Entity analysis
- `entity_registry.py` - Entity definitions
- `entity_resolver.py` - Entity resolution
- `response_formatter.py` - Response formatting
- `consolidation_engine.py` - Consolidation rules
- `entity_consolidation.py` - Legacy consolidation (may have imports)
- `metadata_index.py` - Fast chunk lookups
- `retrieval_validator.py` - Hybrid retrieval
- `event_tracker.py` - Analytics/observability
- `credential_manager.py` - Credential storage
- `query_logger.py` - Query logging
- `voice_routes.py` - Voice API endpoints

### Configuration & Dependencies (KEEP)
- `requirements.txt` - Legacy requirements
- `requirements_py311.txt` - Python 3.11 dependencies
- `.env` / `.env.example` - Environment config
- `README.md` - Main project documentation

### Runtime Data (KEEP)
- `document_registry.json` - Active document registry
- `data/` (core files) - Entity definitions, consolidation rules
- `vector_store/` - FAISS index (active)
- `documents_to_ingest/` - Source documents
- `static/` - Frontend files
- `voice/` - Voice engines & models
- `entity_extractors/` - Deterministic extractors
- `tests/golden_tests.json` - KEEP (used for golden test validation)

---

## Runtime Impact Confirmation

**CONFIRMED: No runtime/startup behavior will be affected by these moves.**

All files proposed for moving are:
- Test scripts (never imported by runtime code)
- Development documentation (not referenced by app)
- Test audio artifacts (temporary debug files)
- Backup data (historical snapshots)
- Progress notes (developer reference only)

---

## Summary Statistics

| Category | Files/Dirs | Destination |
|----------|------------|-------------|
| Test scripts | 7 | `tests/` |
| Test audio | 5 | `tests/audio/` |
| Test data | 2 | `tests/data/` |
| Phase docs | 5 | `docs/` |
| Dev notes | 5 | `archive/` |
| Test reports | 6 | `reports/` |
| Backups | 9 | `backups/` |
| **TOTAL** | **39** | - |

---

## Next Steps

**AWAITING YOUR APPROVAL before executing any file moves.**

Once approved, I will:
1. Create the new directories (`tests/`, `tests/audio/`, `tests/data/`, `docs/`, `archive/`, `reports/`, `backups/`)
2. Move all files as specified above
3. Verify no broken imports or runtime issues
4. Provide a completion confirmation

---

*Report generated following industry-standard project organization practices.*
