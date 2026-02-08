"""Check the prayer chunk content to diagnose truncation issue."""
import sys
sys.path.insert(0, r"C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\campus_rag_chatbot")

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
import os
from dotenv import load_dotenv

load_dotenv(r"C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\campus_rag_chatbot\.env")

embeddings = OpenAIEmbeddings()
vector_store = FAISS.load_local(
    r"C:\Users\chann\OneDrive\Desktop\restartcoco\vibecoding_coco\campus_rag_chatbot\vector_store",
    embeddings,
    allow_dangerous_deserialization=True
)

# Get all documents
docs = list(vector_store.docstore._dict.values())

# Find prayer-related chunks
print("=== PRAYER CHUNKS ===\n")
prayer_chunks = []
for doc in docs:
    if "columban" in doc.page_content.lower() and ("prayer" in doc.page_content.lower() or "blessed" in doc.page_content.lower()):
        chunk_id = doc.metadata.get('chunk_id', 'N/A')
        section = doc.metadata.get('section', 'N/A')
        prayer_chunks.append((chunk_id, section, doc.page_content))

# Sort by chunk_id
prayer_chunks.sort(key=lambda x: x[0] if isinstance(x[0], int) else 0)

for chunk_id, section, content in prayer_chunks:
    print(f"--- Chunk {chunk_id} | Section: {section} ---")
    print(f"Length: {len(content)} chars")
    print(content[:500] + "..." if len(content) > 500 else content)
    print()

# Check specifically for "Help Us" phrase (missing part)
print("\n=== SEARCHING FOR 'Help Us' ===")
for doc in docs:
    if "help us" in doc.page_content.lower() and "columban" in doc.page_content.lower():
        chunk_id = doc.metadata.get('chunk_id', 'N/A')
        section = doc.metadata.get('section', 'N/A')
        print(f"Found in Chunk {chunk_id} | Section: {section}")
        print(f"Content: {doc.page_content}")
        print()
