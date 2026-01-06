"""
Phase 3 Demo - Document Management System
==========================================
This script demonstrates the Phase 3 document management capabilities.

It shows:
1. Ingesting documents from the documents_to_ingest/ folder
2. Listing ingested documents
3. Querying the chatbot with newly ingested documents
4. (Optional) Deleting a document and rebuilding the index

Run this script to see the full Phase 3 workflow in action.
"""

from pathlib import Path
from admin import ingest_documents, list_documents, get_document_manager
from document_manager import DocumentManager


def main():
    print("="*80)
    print("PHASE 3 DEMONSTRATION")
    print("Document Management System for Campus RAG Chatbot")
    print("="*80)
    print()

    # Configuration
    PROJECT_ROOT = Path(__file__).parent
    DOCUMENTS_TO_INGEST = PROJECT_ROOT / "documents_to_ingest"

    print("This demo will:")
    print("  1. Ingest sample documents (IT services, student employment)")
    print("  2. List all ingested documents")
    print("  3. Show document details")
    print("  4. Run the chatbot to query newly ingested information")
    print()
    input("Press Enter to continue...")

    # Step 1: Ingest documents
    print("\n" + "="*80)
    print("STEP 1: INGEST DOCUMENTS")
    print("="*80)
    print(f"\nIngesting documents from: {DOCUMENTS_TO_INGEST}")
    print()

    results = ingest_documents(
        path=str(DOCUMENTS_TO_INGEST),
        skip_duplicates=True
    )

    # Step 2: List documents
    print("\n" + "="*80)
    print("STEP 2: LIST ALL DOCUMENTS")
    print("="*80)
    print()

    documents = list_documents()

    # Step 3: Show detailed info for first document
    if documents:
        print("\n" + "="*80)
        print("STEP 3: DOCUMENT DETAILS EXAMPLE")
        print("="*80)
        print()

        # Get first document
        first_doc = documents[0]
        doc_id = first_doc['document_id']

        print(f"Showing details for: {first_doc['document_name']}")
        print()

        # Show details
        from admin import show_document_info
        show_document_info(doc_id)

    # Step 4: Run the chatbot
    print("\n" + "="*80)
    print("STEP 4: RUN CHATBOT WITH NEW DOCUMENTS")
    print("="*80)
    print()
    print("Now let's test the chatbot with questions about the newly ingested documents.")
    print()
    input("Press Enter to continue...")

    # Import and run main chatbot
    print("\nLaunching chatbot...")
    print()

    from main import main as run_chatbot
    run_chatbot()

    # Final summary
    print("\n" + "="*80)
    print("PHASE 3 DEMO COMPLETE")
    print("="*80)
    print()
    print("You've successfully:")
    print("  ✓ Ingested multi-format documents (TXT in this demo)")
    print("  ✓ Viewed document metadata and details")
    print("  ✓ Queried the chatbot using the ingested documents")
    print()
    print("Additional Commands:")
    print("  python admin.py delete <doc_id>   - Delete a document")
    print("  python admin.py rebuild           - Rebuild the vector store")
    print("  python admin.py ingest <path>     - Ingest more documents")
    print()
    print("To run the chatbot again:")
    print("  python main.py")
    print()
    print("="*80)


if __name__ == "__main__":
    main()
