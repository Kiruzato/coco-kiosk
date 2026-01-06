Documents to Ingest - Staging Area
====================================

This folder is used for staging new documents before ingestion into the
vector database. Place PDF, DOCX, or TXT files here and use the admin
CLI to ingest them.

Usage:
------

1. Place documents in this folder
2. Run: python admin.py ingest

Supported Formats:
------------------
- .txt  (Plain text files)
- .pdf  (PDF documents)
- .docx (Microsoft Word documents)

Example Documents:
------------------
- it_services.txt: Information about campus IT services
- student_employment.txt: On-campus and off-campus job opportunities

Notes:
------
- Duplicate files (same content) will be skipped automatically
- Documents are chunked into ~500 character segments
- Each chunk preserves metadata (filename, file type, ingestion time)
- Successfully ingested files can be moved or deleted from this folder
