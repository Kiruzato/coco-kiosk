"""
CoCo Ingestion Configuration
============================
Configuration settings for the standalone ingestion module.
"""

from pathlib import Path
import os

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
CAMPUS_RAG_DIR = PROJECT_ROOT / "campus_rag_chatbot"

# Default documents path
DEFAULT_DOCUMENTS_PATH = CAMPUS_RAG_DIR / "documents_to_ingest"

# Output configuration
def get_output_base_dir() -> Path:
    """
    Get the base output directory for RAG packages.
    Creates Desktop/CoCo_RAG_Packages/ if it doesn't exist.
    """
    desktop = Path.home() / "Desktop"

    # Fallback if Desktop doesn't exist (e.g., headless Linux)
    if not desktop.exists():
        desktop = Path.home() / "coco_output"

    packages_dir = desktop / "CoCo_RAG_Packages"
    packages_dir.mkdir(parents=True, exist_ok=True)
    return packages_dir

# Ingestion settings
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50

# Required files for a valid vector store package
REQUIRED_VECTOR_STORE_FILES = [
    "index.faiss",
    "index.pkl"
]

# Optional files that may be included
OPTIONAL_VECTOR_STORE_FILES = [
    "document_registry.json"
]
