"""
Admin CLI for Document Management - Phase 3
============================================
This script provides administrative functions for managing the document collection.

Usage:
    python admin.py list
    python admin.py ingest <directory_or_file>
    python admin.py delete <document_id>
    python admin.py rebuild
    python admin.py info <document_id>

Functions can also be imported and used programmatically:
    from admin import ingest_documents, list_documents, delete_document
"""

import sys
import argparse
from pathlib import Path
from typing import Optional
from tabulate import tabulate
from dotenv import load_dotenv
from document_manager import DocumentManager

# Load environment variables
load_dotenv()


# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Paths
PROJECT_ROOT = Path(__file__).parent
REGISTRY_PATH = PROJECT_ROOT / "document_registry.json"
VECTOR_STORE_PATH = PROJECT_ROOT / "vector_store"
DOCUMENTS_TO_INGEST_PATH = PROJECT_ROOT / "documents_to_ingest"


# ==============================================================================
# ADMIN FUNCTIONS
# ==============================================================================

def get_document_manager() -> DocumentManager:
    """
    Create and return a DocumentManager instance.

    Returns:
        Initialized DocumentManager
    """
    manager = DocumentManager(
        registry_path=REGISTRY_PATH,
        vector_store_path=VECTOR_STORE_PATH
    )
    # Load existing vector store if available
    manager.load_vector_store()
    return manager


def ingest_documents(
    path: Optional[str] = None,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    skip_duplicates: bool = True
) -> dict:
    """
    Ingest documents from a file or directory.

    Args:
        path: Path to file or directory (uses documents_to_ingest/ if not provided)
        chunk_size: Chunk size for text splitting
        chunk_overlap: Overlap between chunks
        skip_duplicates: Skip files that have already been ingested

    Returns:
        Dictionary with ingestion results
    """
    print("=" * 80)
    print("DOCUMENT INGESTION")
    print("=" * 80)

    # Use default directory if no path provided
    if path is None:
        path = str(DOCUMENTS_TO_INGEST_PATH)

    target_path = Path(path)

    if not target_path.exists():
        print(f"❌ Error: Path not found: {target_path}")
        return {"error": "Path not found"}

    # Initialize document manager
    manager = get_document_manager()

    # Ingest single file or directory
    if target_path.is_file():
        print(f"\nIngesting single file: {target_path.name}")
        print("-" * 80)
        success, message = manager.ingest_document(
            file_path=target_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            skip_duplicates=skip_duplicates
        )

        if success:
            print(f"✓ {message}")
            results = {"success": [target_path.name], "failed": [], "skipped": []}
        elif "Duplicate" in message:
            print(f"⊘ {message}")
            results = {"success": [], "failed": [], "skipped": [target_path.name]}
        else:
            print(f"✗ {message}")
            results = {"success": [], "failed": [target_path.name], "skipped": []}

    else:
        print(f"\nIngesting documents from directory: {target_path}")
        print("-" * 80)
        results = manager.ingest_directory(
            directory_path=target_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            skip_duplicates=skip_duplicates
        )

    # Display summary
    print("\n" + "=" * 80)
    print("INGESTION SUMMARY")
    print("=" * 80)
    print(f"✓ Successfully ingested: {len(results['success'])} document(s)")
    print(f"⊘ Skipped (duplicates):  {len(results['skipped'])} document(s)")
    print(f"✗ Failed:                {len(results['failed'])} document(s)")

    if results['success']:
        print(f"\nSuccessfully ingested:")
        for filename in results['success']:
            print(f"  - {filename}")

    if results['skipped']:
        print(f"\nSkipped (already ingested):")
        for filename in results['skipped']:
            print(f"  - {filename}")

    if results['failed']:
        print(f"\nFailed:")
        for filename in results['failed']:
            print(f"  - {filename}")

    print("=" * 80)

    return results


def list_documents() -> list:
    """
    List all ingested documents.

    Returns:
        List of document metadata dictionaries
    """
    print("=" * 80)
    print("DOCUMENT REGISTRY")
    print("=" * 80)

    manager = get_document_manager()
    documents = manager.list_documents()

    if not documents:
        print("\nNo documents in registry.")
        print("Use 'python admin.py ingest <path>' to add documents.")
        return []

    # Prepare table data
    table_data = []
    for doc in documents:
        table_data.append([
            doc['document_id'][:12] + "...",  # Shortened ID
            doc['document_name'],
            doc['file_type'],
            doc['num_chunks'],
            doc['ingestion_timestamp'][:19]  # Remove microseconds
        ])

    # Display as table
    headers = ["Document ID", "Filename", "Type", "Chunks", "Ingested"]
    print("\n" + tabulate(table_data, headers=headers, tablefmt="grid"))
    print(f"\nTotal documents: {len(documents)}")
    print("=" * 80)

    return documents


def delete_document(document_id: str) -> bool:
    """
    Delete a document from the registry and vector store.

    Args:
        document_id: Document identifier (can be partial, will match prefix)

    Returns:
        True if successful, False otherwise
    """
    print("=" * 80)
    print("DELETE DOCUMENT")
    print("=" * 80)

    manager = get_document_manager()

    # Find matching document (support partial ID)
    all_docs = manager.list_documents()
    matches = [doc for doc in all_docs if doc['document_id'].startswith(document_id)]

    if not matches:
        print(f"\n❌ No document found with ID starting with: {document_id}")
        print("\nUse 'python admin.py list' to see all document IDs.")
        return False

    if len(matches) > 1:
        print(f"\n⚠ Multiple documents match '{document_id}':")
        for doc in matches:
            print(f"  - {doc['document_id']}: {doc['document_name']}")
        print("\nPlease provide a more specific document ID.")
        return False

    # Found unique match
    doc = matches[0]
    full_id = doc['document_id']
    doc_name = doc['document_name']

    print(f"\nDeleting document:")
    print(f"  ID:   {full_id}")
    print(f"  Name: {doc_name}")
    print(f"  Type: {doc['file_type']}")

    # Confirm deletion
    confirm = input("\nAre you sure you want to delete this document? (yes/no): ")
    if confirm.lower() not in ['yes', 'y']:
        print("❌ Deletion cancelled.")
        return False

    # Delete document
    print("\nDeleting...")
    success, message = manager.delete_document(full_id)

    if success:
        print(f"✓ {message}")
        print("=" * 80)
        return True
    else:
        print(f"✗ {message}")
        print("=" * 80)
        return False


def rebuild_vector_store() -> bool:
    """
    Rebuild the entire vector store from the document registry.

    Returns:
        True if successful, False otherwise
    """
    print("=" * 80)
    print("REBUILD VECTOR STORE")
    print("=" * 80)

    manager = get_document_manager()
    documents = manager.list_documents()

    print(f"\nThis will rebuild the vector store from {len(documents)} registered document(s).")
    print("All documents will be re-processed and re-indexed.")

    confirm = input("\nContinue? (yes/no): ")
    if confirm.lower() not in ['yes', 'y']:
        print("❌ Rebuild cancelled.")
        return False

    print("\nRebuilding...")
    success, message = manager.rebuild_vector_store()

    if success:
        print(f"✓ {message}")
        print("=" * 80)
        return True
    else:
        print(f"✗ {message}")
        print("=" * 80)
        return False


def show_document_info(document_id: str) -> Optional[dict]:
    """
    Show detailed information about a document.

    Args:
        document_id: Document identifier (can be partial)

    Returns:
        Document metadata dictionary or None
    """
    print("=" * 80)
    print("DOCUMENT INFORMATION")
    print("=" * 80)

    manager = get_document_manager()

    # Find matching document
    all_docs = manager.list_documents()
    matches = [doc for doc in all_docs if doc['document_id'].startswith(document_id)]

    if not matches:
        print(f"\n❌ No document found with ID starting with: {document_id}")
        return None

    if len(matches) > 1:
        print(f"\n⚠ Multiple documents match '{document_id}':")
        for doc in matches:
            print(f"  - {doc['document_id']}: {doc['document_name']}")
        return None

    # Display document info
    doc = matches[0]
    print(f"\nDocument Details:")
    print(f"  Document ID:         {doc['document_id']}")
    print(f"  Filename:            {doc['document_name']}")
    print(f"  File Type:           {doc['file_type']}")
    print(f"  File Path:           {doc['file_path']}")
    print(f"  Ingestion Time:      {doc['ingestion_timestamp']}")
    print(f"  Number of Chunks:    {doc['num_chunks']}")
    print(f"  Chunk Size:          {doc['chunk_size']} characters")
    print(f"  Chunk Overlap:       {doc['chunk_overlap']} characters")
    print(f"  File Hash:           {doc['file_hash'][:16]}...")
    print("=" * 80)

    return doc


# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Admin CLI for Campus RAG Chatbot Document Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  List all documents:
    python admin.py list

  Ingest documents from default directory:
    python admin.py ingest

  Ingest a specific file:
    python admin.py ingest path/to/document.pdf

  Ingest from a directory:
    python admin.py ingest path/to/documents/

  Show document information:
    python admin.py info abc123

  Delete a document:
    python admin.py delete abc123

  Rebuild vector store:
    python admin.py rebuild
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Admin commands')

    # List command
    subparsers.add_parser('list', help='List all ingested documents')

    # Ingest command
    ingest_parser = subparsers.add_parser('ingest', help='Ingest documents')
    ingest_parser.add_argument(
        'path',
        nargs='?',
        default=None,
        help='Path to file or directory (default: documents_to_ingest/)'
    )
    ingest_parser.add_argument(
        '--chunk-size',
        type=int,
        default=500,
        help='Chunk size in characters (default: 500)'
    )
    ingest_parser.add_argument(
        '--chunk-overlap',
        type=int,
        default=50,
        help='Chunk overlap in characters (default: 50)'
    )
    ingest_parser.add_argument(
        '--allow-duplicates',
        action='store_true',
        help='Allow duplicate documents (default: skip duplicates)'
    )

    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a document')
    delete_parser.add_argument('document_id', help='Document ID (or prefix)')

    # Rebuild command
    subparsers.add_parser('rebuild', help='Rebuild the vector store')

    # Info command
    info_parser = subparsers.add_parser('info', help='Show document information')
    info_parser.add_argument('document_id', help='Document ID (or prefix)')

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Execute command
    try:
        if args.command == 'list':
            list_documents()

        elif args.command == 'ingest':
            ingest_documents(
                path=args.path,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
                skip_duplicates=not args.allow_duplicates
            )

        elif args.command == 'delete':
            delete_document(args.document_id)

        elif args.command == 'rebuild':
            rebuild_vector_store()

        elif args.command == 'info':
            show_document_info(args.document_id)

    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
