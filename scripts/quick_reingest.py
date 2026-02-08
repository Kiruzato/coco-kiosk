"""
Quick Re-ingest and Test
========================
"""

import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "campus_rag_chatbot"))

from document_manager import DocumentManager

# Paths
REGISTRY_PATH = Path(__file__).parent / "campus_rag_chatbot" / "document_registry.json"
VECTOR_STORE_PATH = Path(__file__).parent / "campus_rag_chatbot" / "vector_store"
PDF_PATH = Path(__file__).parent / "campus_rag_chatbot" / "documents_to_ingest" / "2022_student_manual_latest.pdf"

print("Re-ingesting with page-ordered consolidation...")

# Clear
if VECTOR_STORE_PATH.exists():
    shutil.rmtree(VECTOR_STORE_PATH)
if REGISTRY_PATH.exists():
    REGISTRY_PATH.unlink()

# Ingest
manager = DocumentManager(
    registry_path=REGISTRY_PATH,
    vector_store_path=VECTOR_STORE_PATH
)

success, message = manager.ingest_document(file_path=PDF_PATH)
print(message)
