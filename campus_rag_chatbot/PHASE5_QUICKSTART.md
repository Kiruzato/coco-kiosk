# Phase 5 Quick Start Guide

## What Phase 5 Adds

Phase 5 creates a **web-based kiosk interface** for the campus information chatbot:

1. **Web Interface** - Kiosk-optimized UI (large text, high contrast, touch-friendly)
2. **Backend API** - FastAPI endpoints for chat, feedback, session management
3. **Session Handling** - Maintains conversation state per browser session
4. **Response Transparency** - Shows sources, confidence, rejection reasons
5. **User Feedback** - Captures helpful/not helpful ratings

## Quick Start (3 Steps)

### Step 1: Install Dependencies

```bash
cd campus_rag_chatbot
pip install -r requirements.txt
```

**New dependencies:**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `pydantic` - Data validation

### Step 2: Ingest Documents (if not done)

```bash
python admin.py ingest data/
```

### Step 3: Start the Server

```bash
python app.py
```

**Or using uvicorn directly:**
```bash
uvicorn app:app --reload
```

**Expected output:**
```
================================================================================
Campus Information Kiosk API - Phase 5
================================================================================
Documents loaded: 5
API ready at: http://localhost:8000
Kiosk interface at: http://localhost:8000/
================================================================================
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Step 4: Access the Kiosk

Open your browser and go to:

```
http://localhost:8000
```

## What You'll See

### Kiosk Interface Features

**Header:**
- University name and "Campus Information Kiosk" title
- "Start New Conversation" button (top right)

**Welcome Message:**
- Lists example topics (library, dining, parking, IT, employment, events)
- Prompts user to ask a question

**Chat Area:**
- User messages (right side, blue background)
- Assistant messages (left side, white background with border)
- Confidence badges (High/Medium/Low with color coding)
- Source citations (document name + section)
- Warning messages for low-confidence answers

**Feedback Buttons:**
- "👍 Yes, helpful" and "👎 Not helpful" for each answer
- Disabled after clicking (shows "✓ Thank you for your feedback!")

**Input Area:**
- Large text input field
- "Send" button
- Touch-friendly sizing

### Example Interaction

**User types:** "What are the library hours?"

**System responds with:**
```
According to the Library Hours and Services section in campus_info.txt,
the Springfield University Library is open Monday through Friday from
8:00 AM to 10:00 PM, Saturday from 10:00 AM to 8:00 PM, and Sunday from
12:00 PM to 8:00 PM.

Confidence: High (92/100)
Score: 92/100

Sources:
• campus_info.txt - Library Hours and Services

Was this answer helpful?
[👍 Yes, helpful] [👎 Not helpful]
```

## API Endpoints

The backend exposes these endpoints:

### POST /chat

Send a question and get an answer.

**Request:**
```json
{
  "message": "What are the library hours?",
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "session_id": "uuid-generated-id",
  "answer": "According to the Library Hours and Services section...",
  "sources": [
    {
      "document_name": "campus_info.txt",
      "section": "Library Hours and Services",
      "chunk_id": 0
    }
  ],
  "confidence_level": "High",
  "confidence_score": 92.0,
  "rejected": false,
  "timestamp": "2025-01-04T15:30:22.123456"
}
```

### POST /feedback

Submit user feedback.

**Request:**
```json
{
  "session_id": "uuid",
  "query_id": "query-id",
  "is_helpful": true,
  "comment": "optional comment"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Feedback recorded"
}
```

### POST /reset

Reset a conversation session.

**Request:**
```json
{
  "session_id": "uuid"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Session reset"
}
```

### GET /health

Health check.

**Response:**
```json
{
  "status": "healthy",
  "documents_loaded": 5,
  "active_sessions": 3,
  "timestamp": "2025-01-04T15:30:22"
}
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 Browser                          │
│  http://localhost:8000                           │
│                                                  │
│  ┌────────────────────────────────────────┐     │
│  │  Frontend (index.html)                  │     │
│  │  - Chat UI                              │     │
│  │  - Confidence display                   │     │
│  │  - Source citations                     │     │
│  │  - Feedback buttons                     │     │
│  └────────────────────────────────────────┘     │
│          │                                       │
│          │ HTTP/JSON                             │
│          ▼                                       │
└─────────────────────────────────────────────────┘
         │
         │ POST /chat
         ▼
┌─────────────────────────────────────────────────┐
│           FastAPI Backend (app.py)               │
│                                                  │
│  ┌────────────────────────────────────────┐     │
│  │  Session Management                     │     │
│  │  - Per-browser sessions                 │     │
│  │  - Conversation memory (5 turns)        │     │
│  │  - Auto-expire (30 min)                 │     │
│  └────────────────────────────────────────┘     │
│          │                                       │
│          ▼                                       │
│  ┌────────────────────────────────────────┐     │
│  │  RAG Pipeline (Phases 1-4)              │     │
│  │  - Document retrieval                   │     │
│  │  - Confidence scoring                   │     │
│  │  - Answer generation                    │     │
│  │  - Grounding validation                 │     │
│  └────────────────────────────────────────┘     │
│          │                                       │
│          ▼                                       │
│  ┌────────────────────────────────────────┐     │
│  │  Logging                                │     │
│  │  - queries.jsonl                        │     │
│  │  - retrievals.jsonl                     │     │
│  │  - responses.jsonl                      │     │
│  │  - feedback.jsonl (NEW)                 │     │
│  └────────────────────────────────────────┘     │
└─────────────────────────────────────────────────┘
```

## Key Features

### 1. Kiosk-Optimized Design

**Large Text:**
- Headers: 48px / 28px
- User messages: 22px
- Assistant messages: 20px
- Input field: 20px

**High Contrast:**
- Dark blue header (#1e3c72)
- White messages on light gray background
- Clear borders and spacing

**Touch-Friendly:**
- Large buttons (padding: 20px 40px)
- Big click targets
- Clear visual feedback on hover/click

### 2. Session Handling

**Auto-Created:**
- First message creates a session with UUID
- Session ID returned and stored in frontend

**Conversation Memory:**
- Maintains last 5 turns per session
- Enables follow-up questions with pronouns
- Example: "What are the library hours?" → "Can I print there?"

**Auto-Expire:**
- Sessions timeout after 30 minutes of inactivity
- Automatic cleanup to prevent memory leaks

**Manual Reset:**
- "Start New Conversation" button
- Clears chat history
- Creates fresh session

### 3. Response Transparency

**Confidence Display:**
- Color-coded badges:
  - High (green): 🟢 Strong relevance
  - Medium (orange): 🟠 Moderate relevance
  - Low (red): 🔴 Weak relevance
- Numerical score (0-100)

**Source Citations:**
- Document name
- Section name
- Chunk ID
- Grouped by document

**Rejection Messages:**
- Clear explanation when answer is rejected
- Suggests rephrasing or different topic
- Yellow warning box for visibility

### 4. User Feedback

**Simple Buttons:**
- "👍 Yes, helpful"
- "👎 Not helpful"

**Immediate Feedback:**
- Buttons disabled after click
- "✓ Thank you for your feedback!" message

**Logged Data:**
```json
{
  "session_id": "uuid",
  "query_id": "query-id",
  "is_helpful": true,
  "comment": null,
  "timestamp": "2025-01-04T15:30:22"
}
```

**Stored in:** `logs/feedback.jsonl`

## Configuration

### Backend Settings (app.py)

```python
# Retrieval
RETRIEVAL_TOP_K = 4                      # Chunks to retrieve
RELEVANCE_SCORE_THRESHOLD = 0.5           # Minimum similarity

# Memory
MEMORY_WINDOW_SIZE = 5                    # Conversation turns

# Confidence
MIN_CONFIDENCE_TO_ANSWER = ConfidenceLevel.MEDIUM  # Reject LOW

# Sessions
SESSION_TIMEOUT_MINUTES = 30              # Auto-expire sessions
```

### Frontend Customization (static/style.css)

```css
/* Change university colors */
.kiosk-header {
    background: #1e3c72;  /* Your school color */
}

/* Adjust text sizes */
.large-text {
    font-size: 22px;  /* Make larger/smaller */
}

/* Modify button sizes */
#sendBtn {
    padding: 20px 40px;  /* Increase for touchscreens */
}
```

## Common Use Cases

### Use Case 1: Kiosk Deployment

**Setup:**
1. Deploy on a kiosk computer
2. Open browser in fullscreen (F11)
3. Navigate to http://localhost:8000
4. Optionally: Disable browser chrome, set as homepage

**Recommended:**
- Touchscreen monitor for easy interaction
- Auto-start server on boot
- Screensaver with "Touch to Start"

### Use Case 2: Testing API

```bash
# Test chat endpoint
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the library hours?"}'

# Test health
curl http://localhost:8000/health

# Test feedback
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test", "query_id": "q1", "is_helpful": true}'
```

### Use Case 3: Analyzing Feedback

```python
import json

# Read feedback logs
with open('logs/feedback.jsonl', 'r') as f:
    feedback = [json.loads(line) for line in f]

# Calculate helpfulness rate
total = len(feedback)
helpful = sum(1 for f in feedback if f['is_helpful'])
rate = helpful / total * 100

print(f"Helpfulness: {rate:.1f}% ({helpful}/{total})")
```

## Troubleshooting

### Problem: "No vector store found"

**Solution:**
```bash
python admin.py ingest data/
```

### Problem: Port 8000 already in use

**Solution:**
```bash
# Use different port
uvicorn app:app --port 8001

# Or kill existing process
# On Linux/Mac:
lsof -ti:8000 | xargs kill -9

# On Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Problem: Frontend not loading

**Solution:**
1. Check that `static/` directory exists
2. Verify files: index.html, style.css, app.js
3. Check browser console for errors
4. Try hard refresh (Ctrl+Shift+R)

### Problem: CORS errors

**Solution:**
- The API has CORS enabled for all origins
- If deploying, update `allow_origins` in app.py to specific domains

### Problem: Sessions not persisting

**Solution:**
- Sessions are in-memory (lost on server restart)
- For production, use Redis or database-backed sessions
- Currently designed for short kiosk interactions

## Next Steps

1. **Customize Branding**
   - Edit `static/index.html` - University name
   - Edit `static/style.css` - Colors, logos

2. **Add More Documents**
   ```bash
   python admin.py ingest path/to/new/docs
   ```

3. **Deploy to Production**
   - Use Gunicorn or Uvicorn with multiple workers
   - Add HTTPS (Let's Encrypt)
   - Set up reverse proxy (Nginx)

4. **Monitor Usage**
   ```python
   from query_logger import print_log_summary
   print_log_summary()
   ```

5. **Analyze Feedback**
   ```bash
   # View feedback logs
   cat logs/feedback.jsonl

   # Count helpful vs not helpful
   grep '"is_helpful": true' logs/feedback.jsonl | wc -l
   ```

## File Structure

```
campus_rag_chatbot/
├── app.py                   # FastAPI backend (NEW)
├── static/                  # Frontend files (NEW)
│   ├── index.html          # Kiosk UI
│   ├── style.css           # Kiosk styling
│   └── app.js              # Frontend JavaScript
├── logs/
│   └── feedback.jsonl      # User feedback (NEW)
├── main.py                  # Standalone chatbot (Phases 1-4)
├── document_manager.py      # Document management
├── confidence_scorer.py     # Confidence scoring
├── query_logger.py          # Structured logging
└── requirements.txt         # Updated with FastAPI
```

## Summary

Phase 5 provides a **production-ready kiosk interface**:

- ✅ Clean, large-text UI optimized for kiosks
- ✅ Backend API with session management
- ✅ Confidence transparency (shows scores)
- ✅ Source citations (document + section)
- ✅ Grounding validation (rejects low confidence)
- ✅ User feedback capture (helpful/not helpful)
- ✅ Automatic session cleanup
- ✅ Structured logging (feedback.jsonl)

**Result:** A complete web-based campus information kiosk ready for deployment.

---

For detailed documentation, see the main README.md and API documentation.
