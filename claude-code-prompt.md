Title: Move Unstructured Document Ingestion to Standalone Module and Add RAG Package Upload in Admin UI
You are working on the CoCo campus kiosk AI system, a FastAPI web application with a FAISS vector store and a document ingestion pipeline managed by document_manager.py.
This task applies ONLY to the unstructured document ingestion system (PDF, DOCX, TXT). Do NOT modify structured entity systems or other parts of the application.
Currently, ingestion is performed by the server using the Document Manager, which processes files and writes to the FAISS vector store under:
campus_rag_chatbot/vector_store/
This must be changed so that ingestion happens in a standalone module on a separate computer, and the server only loads pre-built vector store packages.
Do NOT redesign architecture. Do NOT modify retrieval logic, response orchestration, registry logic, or chat pipeline.
________________________________________
Requirements
1. Remove ingestion capability from server runtime
Modify the FastAPI server so it no longer ingests raw documents.
Specifically:
•	Disable or remove endpoints and logic that parse and embed PDF, DOCX, and TXT files
•	Do NOT remove:
o	retrieval_validator.py
o	response_orchestrator.py
o	vector store loading logic
o	document registry reading logic
The server must ONLY load an existing vector store from:
campus_rag_chatbot/vector_store/
The server must NEVER create or modify FAISS index files.
________________________________________
2. Create standalone ingestion module
Create a new top-level directory:
coco_ingestion/
This module must use the SAME ingestion logic currently implemented in:
campus_rag_chatbot/document_manager.py
Do NOT rewrite ingestion logic. Reuse or import existing logic where possible.
The ingestion module must:
•	Run independently from the server
•	Process documents from a specified folder
•	Build a complete vector store package
Output must match server expectations exactly.
________________________________________
3. Ingestion module output behavior
When run, the ingestion module must:
Create a folder on the Windows Desktop:
Desktop/CoCo_RAG_Packages/
Inside this folder, create a timestamped package folder:
Example:
Desktop/CoCo_RAG_Packages/campus_rag_2026-02-15_14-30/
This package folder must contain the complete vector store:
vector_store/
    index.faiss
    index.pkl
    document_registry.json
    (any other required files)
The structure must be identical to:
campus_rag_chatbot/vector_store/
This ensures compatibility with the server.
________________________________________
4. Add RAG Package Upload feature in Admin UI
Add new Admin feature accessible under:
/admin
Add a new sidebar navigation item:
RAG Package Upload
This opens a page allowing upload of:
vector_store package (.zip)
________________________________________
5. Add upload endpoint
Create FastAPI endpoint:
POST /admin/upload_rag_package
This endpoint must:
1.	Accept zip file upload
2.	Save zip to temporary location
3.	Extract zip
4.	Validate required files exist:
Required:
index.faiss
index.pkl
5.	Replace existing directory:
campus_rag_chatbot/vector_store/
Use safe replacement:
•	extract to temporary directory
•	validate
•	replace existing directory atomically
________________________________________
6. Reload vector store without restarting server
After successful upload, reload the vector store in memory.
Use existing vector store loading logic.
Do NOT modify retrieval logic beyond updating the loaded index reference.
________________________________________
7. Update Admin UI frontend
Modify:
campus_rag_chatbot/static/admin.html
campus_rag_chatbot/static/admin.js
Add sidebar item:
RAG Package Upload
Add upload interface:
Select vector_store zip file
[Upload Button]
After upload, show success message.
________________________________________
8. Do NOT modify these components
Do NOT modify:
retrieval_validator.py
response_orchestrator.py
voice/
data/
entity systems
chat endpoints
Do NOT modify structured entity ingestion.
This task applies ONLY to unstructured document ingestion.
________________________________________
9. Output requirements
Provide:
•	full updated file tree
•	all new files
•	all modified files
Ensure:
•	ingestion module runs independently
•	server loads uploaded vector store correctly
•	admin can upload vector store package from Admin UI sidebar
________________________________________
End of instructions.

