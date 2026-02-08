"""
Phase 19 Diagnosis: Vector Store Content Check
===============================================

Check if hymn and prayer content actually exists in the vector store.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'campus_rag_chatbot'))

from document_manager import DocumentManager
import re

def search_content(doc_manager, search_terms, context_chars=200):
    """Search for terms in vector store chunks"""
    print(f"\nSearching for: {search_terms}")
    print("-" * 70)
    
    vector_store = doc_manager.vector_store
    found_chunks = []
    
    try:
        # Access docstore
        docstore = vector_store.docstore
        
        for doc_id in vector_store.index_to_docstore_id.values():
            doc = docstore.search(doc_id)
            if doc and hasattr(doc, 'page_content'):
                content = doc.page_content.lower()
                
                # Check if any search term appears
                for term in search_terms:
                    if term.lower() in content:
                        found_chunks.append({
                            'chunk_id': doc.metadata.get('chunk_id', -1),
                            'document': doc.metadata.get('document_name', 'Unknown'),
                            'section': doc.metadata.get('section', 'Unknown'),
                            'content': doc.page_content,
                            'matched_term': term
                        })
                        break
        
        if found_chunks:
            print(f"✅ Found {len(found_chunks)} chunks containing search terms\n")
            
            # Group by document
            by_doc = {}
            for chunk in found_chunks:
                doc_name = chunk['document']
                if doc_name not in by_doc:
                    by_doc[doc_name] = []
                by_doc[doc_name].append(chunk)
            
            for doc_name, chunks in by_doc.items():
                print(f"Document: {doc_name}")
                chunks.sort(key=lambda x: x['chunk_id'])
                
                for chunk in chunks:
                    print(f"  Chunk {chunk['chunk_id']} (Section: {chunk['section']})")
                    print(f"  Matched: '{chunk['matched_term']}'")
                    
                    # Show excerpt
                    content = chunk['content']
                    term_pos = content.lower().find(chunk['matched_term'].lower())
                    start = max(0, term_pos - context_chars // 2)
                    end = min(len(content), term_pos + len(chunk['matched_term']) + context_chars // 2)
                    excerpt = content[start:end]
                    
                    print(f"  Excerpt: ...{excerpt}...")
                    print(f"  Total length: {len(content)} chars")
                    print()
        else:
            print("❌ No chunks found containing these terms")
            print("  → Content may not be ingested or terms are incorrect")
        
        return found_chunks
    
    except Exception as e:
        print(f"❌ Error searching: {e}")
        return []

def main():
    print("=" * 70)
    print("PHASE 19 DIAGNOSIS: Vector Store Content Check")
    print("=" * 70)
    
    # Initialize document manager
    print("\nInitializing document manager...")
    registry_path = os.path.join('campus_rag_chatbot', 'document_registry.json')
    vector_store_path = os.path.join('campus_rag_chatbot', 'vector_store')
    doc_manager = DocumentManager(registry_path, vector_store_path)
    
    total_chunks = len(doc_manager.vector_store.index_to_docstore_id)
    print(f"Total chunks in vector store: {total_chunks}")
    
    # Test 1: Hymn
    print("\n" + "=" * 70)
    print("TEST 1: Columban Hymn")
    print("=" * 70)
    hymn_chunks = search_content(
        doc_manager,
        ["hymn", "Columban hymn", "alma mater", "lyrics"],
        context_chars=300
    )
    
    # Test 2: Prayer
    print("\n" + "=" * 70)
    print("TEST 2: Prayer to Saint Columban")
    print("=" * 70)
    prayer_chunks = search_content(
        doc_manager,
        ["Saint Columban", "prayer", "blessed Columban"],
        context_chars=300
    )
    
    # Test 3: Check adjacency
    if prayer_chunks:
        print("\n" + "=" * 70)
        print("ADJACENCY CHECK: Prayer Chunks")
        print("=" * 70)
        
        chunk_ids = sorted([c['chunk_id'] for c in prayer_chunks])
        print(f"Prayer chunk IDs: {chunk_ids}")
        
        # Check if they're adjacent
        for i in range(len(chunk_ids) - 1):
            gap = chunk_ids[i + 1] - chunk_ids[i]
            if gap == 1:
                print(f"  ✅ Chunks {chunk_ids[i]} and {chunk_ids[i+1]} are adjacent")
            else:
                print(f"  ⚠️ Gap of {gap} chunks between {chunk_ids[i]} and {chunk_ids[i+1]}")
    
    # Summary
    print("\n" + "=" * 70)
    print("DIAGNOSIS SUMMARY")
    print("=" * 70)
    print(f"Hymn chunks found: {len(hymn_chunks)}")
    print(f"Prayer chunks found: {len(prayer_chunks)}")
    
    if len(hymn_chunks) == 0:
        print("\n❌ HYMN: Content NOT in vector store - ingestion issue")
    else:
        print(f"\n✅ HYMN: Content exists ({len(hymn_chunks)} chunks)")
        print("   → Retrieval or grounding may be the issue")
    
    if len(prayer_chunks) == 0:
        print("\n❌ PRAYER: Content NOT in vector store - ingestion issue")
    else:
        print(f"\n✅ PRAYER: Content exists ({len(prayer_chunks)} chunks)")
        print("   → Partial retrieval - expansion may help")

if __name__ == '__main__':
    main()
