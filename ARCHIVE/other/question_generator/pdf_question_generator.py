import pdfplumber
from transformers import pipeline
import random

PDF_PATH = "2022_student_manual_latest.pdf"  # change this
MAX_QUESTIONS = 100
CHUNK_SIZE = 500  # characters per chunk

print("Loading PDF...")

# 1. Extract text from PDF
text = ""
with pdfplumber.open(PDF_PATH) as pdf:
    for page in pdf.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

print("PDF loaded.")

# 2. Split into chunks
chunks = []
for i in range(0, len(text), CHUNK_SIZE):
    chunk = text[i:i+CHUNK_SIZE]
    if len(chunk.strip()) > 100:
        chunks.append(chunk)

print(f"Created {len(chunks)} text chunks.")

# 3. Load local question-generation model
print("Loading local question generator model...")
qg = pipeline("text2text-generation", model="iarfmoose/t5-base-question-generator")

questions = []

# 4. Generate questions
for chunk in chunks:
    if len(questions) >= MAX_QUESTIONS:
        break

    try:
        prompt = f"generate questions: {chunk}"
        outputs = qg(prompt, max_length=128, num_return_sequences=3)
        for out in outputs:
            q = out["generated_text"].strip()
            if q.endswith("?") and q not in questions:
                questions.append(q)
                if len(questions) >= MAX_QUESTIONS:
                    break
    except Exception as e:
        continue

# 5. Shuffle and save
random.shuffle(questions)

with open("generated_questions.txt", "w", encoding="utf-8") as f:
    for i, q in enumerate(questions, 1):
        f.write(f"{i}. {q}\n")

print(f"\nDone! Generated {len(questions)} questions.")
print("Saved to generated_questions.txt")
