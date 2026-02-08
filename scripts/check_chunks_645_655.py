"""Check chunks 645-655 to see current structure."""
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

print("=== CHUNKS 645-655 ===\n")
target_chunks = [(doc.metadata.get('chunk_id'), doc.metadata.get('section'), doc.page_content)
                 for doc in docs if isinstance(doc.metadata.get('chunk_id'), int) and 645 <= doc.metadata.get('chunk_id') <= 655]

for chunk_id, section, content in sorted(target_chunks, key=lambda x: x[0]):
    print(f"=== Chunk {chunk_id} | Section: {section} ===")
    print(f"Length: {len(content)} chars")
    print(content)
    print()
