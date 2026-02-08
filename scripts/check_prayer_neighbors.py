"""Check chunks 646-650 to see the prayer split."""
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

# Find chunks 644-652
print("=== CHUNKS 644-652 ===\n")
target_chunks = []
for doc in docs:
    chunk_id = doc.metadata.get('chunk_id', -999)
    if 644 <= chunk_id <= 652:
        target_chunks.append((chunk_id, doc.metadata.get('section', 'N/A'), doc.page_content))

# Sort by chunk_id
target_chunks.sort(key=lambda x: x[0])

for chunk_id, section, content in target_chunks:
    print(f"=== Chunk {chunk_id} | Section: {section} ===")
    print(f"Length: {len(content)} chars")
    print(content)
    print()
