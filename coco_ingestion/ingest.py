#!/usr/bin/env python3
"""
CoCo Standalone Ingestion Module
================================
Processes documents and outputs complete vector store packages
for deployment to Raspberry Pi or other runtime environments.

Usage:
    python -m coco_ingestion.ingest <documents_folder>
    python -m coco_ingestion.ingest                      # Uses default folder
    python -m coco_ingestion.ingest --help

Output:
    Desktop/CoCo_RAG_Packages/campus_rag_YYYY-MM-DD_HH-MM/
        vector_store/
            index.faiss
            index.pkl
        document_registry.json
"""

import sys
import os
import argparse
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

# Add campus_rag_chatbot to path for imports
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CAMPUS_RAG_DIR = PROJECT_ROOT / "campus_rag_chatbot"

sys.path.insert(0, str(CAMPUS_RAG_DIR))

# Now import from campus_rag_chatbot
from document_manager import DocumentManager

# Import from our local config (relative import)
from .config import (
    DEFAULT_DOCUMENTS_PATH,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    REQUIRED_VECTOR_STORE_FILES
)


def create_package_folder(documents_path: Path) -> Path:
    """
    Create a timestamped package folder in the same directory as the documents.

    Args:
        documents_path: Path to the documents folder

    Returns:
        Path to the created package folder
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    package_name = f"rag_package_{timestamp}"
    package_dir = documents_path / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    return package_dir


def run_ingestion(
    documents_path: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    create_zip: bool = True
) -> Path:
    """
    Run document ingestion and create a vector store package.

    Args:
        documents_path: Path to folder containing documents to ingest
        chunk_size: Size of text chunks for splitting
        chunk_overlap: Overlap between chunks
        create_zip: Whether to create a .zip file of the package

    Returns:
        Path to the created package folder
    """
    print("=" * 70)
    print("  CoCo Standalone Ingestion")
    print("=" * 70)
    print()

    # Validate documents path
    if not documents_path.exists():
        print(f"ERROR: Documents path not found: {documents_path}")
        sys.exit(1)

    if not documents_path.is_dir():
        print(f"ERROR: Path is not a directory: {documents_path}")
        sys.exit(1)

    # Count documents (exclude rag_package_* folders from previous runs)
    doc_files = list(documents_path.glob("**/*"))
    doc_files = [
        f for f in doc_files
        if f.is_file()
        and f.suffix.lower() in ['.txt', '.pdf', '.docx']
        and 'rag_package_' not in str(f)  # Exclude previous package outputs
    ]
    print(f"Documents folder: {documents_path}")
    print(f"Documents found:  {len(doc_files)}")
    print()

    if len(doc_files) == 0:
        print("ERROR: No documents found (.txt, .pdf, .docx)")
        sys.exit(1)

    # Create package folder in the same directory as documents
    package_dir = create_package_folder(documents_path)
    vector_store_dir = package_dir / "vector_store"
    registry_path = package_dir / "document_registry.json"

    print(f"Output folder:    {package_dir}")
    print()
    print("-" * 70)
    print("  Ingesting Documents")
    print("-" * 70)
    print()

    # Initialize document manager with output paths
    manager = DocumentManager(
        registry_path=registry_path,
        vector_store_path=vector_store_dir
    )

    # Run ingestion
    results = manager.ingest_directory(
        directory_path=documents_path,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        skip_duplicates=True
    )

    # Save vector store
    manager.save_vector_store()

    print()
    print("-" * 70)
    print("  Ingestion Summary")
    print("-" * 70)
    print()
    print(f"  Successful: {len(results.get('success', []))}")
    print(f"  Skipped:    {len(results.get('skipped', []))}")
    print(f"  Failed:     {len(results.get('failed', []))}")
    print()

    # Validate output
    print("-" * 70)
    print("  Validating Output")
    print("-" * 70)
    print()

    all_valid = True
    for required_file in REQUIRED_VECTOR_STORE_FILES:
        file_path = vector_store_dir / required_file
        if file_path.exists():
            size = file_path.stat().st_size
            size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024*1024):.1f} MB"
            print(f"  [OK] {required_file} ({size_str})")
        else:
            print(f"  [MISSING] {required_file}")
            all_valid = False

    # Check registry
    if registry_path.exists():
        size = registry_path.stat().st_size
        size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024*1024):.1f} MB"
        print(f"  [OK] document_registry.json ({size_str})")
    else:
        print(f"  [MISSING] document_registry.json")
        all_valid = False

    print()

    if not all_valid:
        print("ERROR: Package validation failed!")
        sys.exit(1)

    # Create zip file
    if create_zip:
        print("-" * 70)
        print("  Creating ZIP Package")
        print("-" * 70)
        print()

        zip_path = package_dir.parent / f"{package_dir.name}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add vector_store folder
            for file_path in vector_store_dir.rglob("*"):
                if file_path.is_file():
                    arcname = f"vector_store/{file_path.relative_to(vector_store_dir)}"
                    zipf.write(file_path, arcname)

            # Add registry
            if registry_path.exists():
                zipf.write(registry_path, "document_registry.json")

        zip_size = zip_path.stat().st_size
        zip_size_str = f"{zip_size / 1024:.1f} KB" if zip_size < 1024 * 1024 else f"{zip_size / (1024*1024):.1f} MB"
        print(f"  Created: {zip_path.name} ({zip_size_str})")
        print()

    # Final summary
    print("=" * 70)
    print("  Package Ready!")
    print("=" * 70)
    print()
    print(f"  Folder: {package_dir}")
    if create_zip:
        print(f"  ZIP:    {zip_path}")
    print()
    print("  To deploy to Raspberry Pi:")
    print("    1. Upload the .zip via Admin UI > RAG Package")
    print("    2. Or copy vector_store/ to campus_rag_chatbot/")
    print()

    return package_dir


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="CoCo Standalone Ingestion - Create vector store packages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m coco_ingestion.ingest
      Ingest from default folder (campus_rag_chatbot/documents_to_ingest/)

  python -m coco_ingestion.ingest ./my_documents
      Ingest from custom folder

  python -m coco_ingestion.ingest --chunk-size 1000 --no-zip
      Custom chunk size, skip zip creation
        """
    )

    parser.add_argument(
        "documents_path",
        nargs="?",
        default=None,
        help="Path to documents folder (default: campus_rag_chatbot/documents_to_ingest/)"
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Chunk size for text splitting (default: {DEFAULT_CHUNK_SIZE})"
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=DEFAULT_CHUNK_OVERLAP,
        help=f"Overlap between chunks (default: {DEFAULT_CHUNK_OVERLAP})"
    )

    parser.add_argument(
        "--no-zip",
        action="store_true",
        help="Skip creating .zip file"
    )

    args = parser.parse_args()

    # Determine documents path
    if args.documents_path:
        documents_path = Path(args.documents_path).resolve()
    else:
        documents_path = DEFAULT_DOCUMENTS_PATH

    # Run ingestion
    run_ingestion(
        documents_path=documents_path,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        create_zip=not args.no_zip
    )


if __name__ == "__main__":
    main()
