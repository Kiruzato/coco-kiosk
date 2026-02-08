"""Check why prayer consolidation didn't work."""
import sys
sys.path.insert(0, r"C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\campus_rag_chatbot")

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv(r"C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\campus_rag_chatbot\.env")

embeddings = OpenAIEmbeddings()
vector_store = FAISS.load_local(
    r"C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\campus_rag_chatbot\vector_store",
    embeddings,
    allow_dangerous_deserialization=True
)

docs = list(vector_store.docstore._dict.values())

print("=== SEARCHING FOR PRAYER CONTENT ===\n")

# Search for various prayer-related keywords
keywords = ['prayer', 'blessed columban', 'beloved columban', 'intercede', 'o blessed', 'o beloved']

for keyword in keywords:
    print(f"\n--- Keyword: '{keyword}' ---")
    matches = []
    for doc in docs:
        content = doc.page_content.lower()
        if keyword in content:
            chunk_id = doc.metadata.get('chunk_id', 'N/A')
            section = doc.metadata.get('section', 'N/A')
            matches.append((chunk_id, section, doc.page_content[:150]))

    print(f"Found {len(matches)} matches:")
    for chunk_id, section, preview in matches[:5]:  # Show first 5
        print(f"  Chunk {chunk_id} | {section}: {preview}...")

print("\n\n=== ALL CHUNKS WITH 'columban' ===")
columban_chunks = [(doc.metadata.get('chunk_id'), doc.metadata.get('section'), doc.page_content)
                   for doc in docs if 'columban' in doc.page_content.lower()]
print(f"Total: {len(columban_chunks)}")

for chunk_id, section, content in sorted(columban_chunks, key=lambda x: x[0] if isinstance(x[0], int) else 999):
    if 'prayer' in content.lower() or 'blessed' in content.lower() or 'intercede' in content.lower() or 'beloved' in content.lower():
        print(f"\nChunk {chunk_id} | {section}:")
        print(content)
