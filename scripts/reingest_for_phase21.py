"""
Phase 23: Re-ingest document with metadata validation.
"""
import sys
import os
import shutil

sys.path.insert(0, r"C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\campus_rag_chatbot")

from dotenv import load_dotenv
load_dotenv(r"C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\campus_rag_chatbot\.env")

from pathlib import Path
from document_manager import DocumentManager

# Paths
BASE_PATH = Path(r"C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\campus_rag_chatbot")
VECTOR_STORE_PATH = BASE_PATH / "vector_store"
REGISTRY_PATH = BASE_PATH / "document_registry.json"
PDF_PATH = BASE_PATH / "data" / "uploaded" / "2022_student_manual_latest.pdf"

print("Phase 22: Re-ingesting document with appendix-aware chunking")
print("=" * 60)

# Backup existing vector store
backup_path = str(VECTOR_STORE_PATH) + "_backup_pre_phase22"
if VECTOR_STORE_PATH.exists():
    if os.path.exists(backup_path):
        shutil.rmtree(backup_path)
    shutil.copytree(str(VECTOR_STORE_PATH), backup_path)
    print(f"Backed up vector store to: {backup_path}")

    # Remove existing vector store
    shutil.rmtree(str(VECTOR_STORE_PATH))
    print("Removed existing vector store")

# Clear registry to allow re-ingestion
import json
if REGISTRY_PATH.exists():
    backup_registry = str(REGISTRY_PATH) + ".backup_pre_phase22"
    shutil.copy(str(REGISTRY_PATH), backup_registry)
    print(f"Backed up registry to: {backup_registry}")

    # Clear the registry
    with open(REGISTRY_PATH, 'w') as f:
        json.dump({}, f)
    print("Cleared document registry")

# Initialize document manager
print("\nInitializing document manager...")
dm = DocumentManager(
    registry_path=REGISTRY_PATH,
    vector_store_path=VECTOR_STORE_PATH
)

# Re-ingest the PDF
print(f"\nIngesting: {PDF_PATH}")
result = dm.ingest_document(PDF_PATH)
print(f"Result: {result}")

# Verify chunks were created
print("\n" + "=" * 60)
print("Checking for chunks...")

if dm.vector_store:
    docs = list(dm.vector_store.docstore._dict.values())
    synthetic_chunks = [d for d in docs if d.metadata.get('is_synthetic', False)]
    appendix_chunks = [d for d in docs if d.metadata.get('is_appendix', False)]

    print(f"Total chunks: {len(docs)}")
    print(f"Synthetic chunks: {len(synthetic_chunks)}")
    print(f"Appendix chunks: {len(appendix_chunks)}")

    if synthetic_chunks:
        print("\n--- Synthetic Chunks ---")
        for sc in synthetic_chunks:
            entity_type = sc.metadata.get('entity_type', 'unknown')
            chunk_id = sc.metadata.get('chunk_id', 'N/A')
            content_len = len(sc.page_content)
            phase = sc.metadata.get('consolidation_phase', 'N/A')
            print(f"\n  - Entity: {entity_type}, Chunk ID: {chunk_id}, Length: {content_len} chars, Phase: {phase}")

            if entity_type == 'prayer':
                print(f"    Content preview: {sc.page_content[:200]}...")
                print(f"    Content end: ...{sc.page_content[-100:]}")

    if appendix_chunks:
        print("\n--- Appendix Chunks (Phase 22) ---")
        for ac in appendix_chunks:
            section_title = ac.metadata.get('section_title', 'unknown')
            chunk_id = ac.metadata.get('chunk_id', 'N/A')
            appendix_id = ac.metadata.get('appendix_id', 'N/A')
            content_len = len(ac.page_content)
            print(f"\n  - Section: {section_title}, Chunk ID: {chunk_id}, Appendix ID: {appendix_id}, Length: {content_len} chars")
            print(f"    Content preview: {ac.page_content[:150]}...")

print("\nDone!")
