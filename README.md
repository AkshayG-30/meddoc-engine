# MedDoc Engine — Tri9T AI

A backend API that parses medical device documentation (PDF), reconstructs it as a versioned hierarchical tree, generates LLM-powered QA test cases, and maintains traceability as documents evolve.

## Quick Start

### Prerequisites
- Python 3.11+
- MongoDB (local or Atlas)
- Groq API key (free tier)

### Setup

```bash
# Clone
git clone https://github.com/AkshayG-30/meddoc-engine.git
cd meddoc-engine

# Virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Environment variables
cp .env.example .env
# Edit .env with your GROQ_API_KEY and MONGO_URI

# Run
uvicorn backend.main:app --reload
```

### API Documentation
Once running, visit: `http://localhost:8000/docs`

### Document Ingestion

```bash
# Ingest v1
curl -X POST http://localhost:8000/api/documents/ingest \
  -F "file=@data/ct200_manual.pdf" \
  -F "document_name=CT-200 Manual"

# Ingest v2 (creates new version, preserves v1)
curl -X POST http://localhost:8000/api/documents/ingest \
  -F "file=@data/ct200_manual_v2.pdf" \
  -F "document_name=CT-200 Manual"
```

### v1 → v2 Re-ingestion Flow
1. Ingest `ct200_manual.pdf` — creates document with version 1
2. Ingest `ct200_manual_v2.pdf` with the same `document_name` — creates version 2
3. Node matching runs automatically: unchanged nodes are linked, changed nodes are flagged
4. Query any node's diff: `GET /api/nodes/{id}/diff?from_version=1&to_version=2`
5. Generate QA from v1 selection, then check staleness after v2 ingestion

## Project Structure

```
tri9t-ai/
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Settings
│   ├── parser/                 # PDF extraction & hierarchy
│   ├── versioning/             # Version management & diff
│   ├── llm/                    # Groq integration
│   ├── database/               # SQLAlchemy + MongoDB
│   └── tests/                  # Unit & integration tests
├── data/                       # CT-200 PDFs
├── artifacts/                  # Engineering decision logs
├── approach_document.md        # Design decisions & tradeoffs
└── requirements.txt
```

## Tech Stack
- **FastAPI** + **Pydantic** — API framework with validation
- **SQLAlchemy** + **SQLite** — Document tree, versions, selections
- **MongoDB** — LLM-generated QA outputs
- **pdfplumber** — PDF text and table extraction
- **Groq** (LLaMA 3.3 70B) — QA test case generation

## License
Private — Tri9T AI internship assignment
