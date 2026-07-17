# MedDoc Engine — Implementation Plan

## Project Overview

Build a backend API that ingests the **CardioTrack CT-200** medical device manual (PDF), reconstructs it as a versioned hierarchical tree, generates LLM-powered QA test cases from user-selected sections, and tracks traceability/staleness as the document evolves.

**Tech Stack:** FastAPI · Pydantic · SQLAlchemy + SQLite · MongoDB · Groq (LLM) · Python 3.11+

---

## Strength / Weakness Strategy

### MUST be production-quality
| Component | Why |
|---|---|
| PDF Parser + Hierarchy | Explicitly the highest-scoring component per assignment |
| Traceability chain | node → version → content hash → generated QA |
| Versioning + node matching | Must detect same logical node across versions |
| Content hashing | Foundation for staleness detection |
| Node relationships | Parent/child integrity is graded |

### Intentionally "good enough" (with documented justification)
| Component | Approach | Known limitation to document |
|---|---|---|
| Semantic node matching | Title + parent similarity + content hash (no embeddings) | Fails when heading changes completely but content stays |
| LLM error recovery | Retry once → fail | No repair/partial-parse pipeline |
| Duplicate selection policy | Return cached if selection_hash + model + prompt_version match | No regeneration option |
| Diff summary | `difflib` — insertions/deletions/modified | No semantic diff for numerical thresholds |
| Search | SQLite `LIKE` | No BM25/vector/embeddings |
| Table extraction | Simple bordered tables only; low-confidence → store as plain text | Never silently discard |

---

## Phase-by-Phase Plan

### Phase 1 — Repository Initialization
- **Commit:** `feat: initialize project structure`
- **Artifact:** `001_project_setup.md`
- **Deliverables:**
  - Project directory tree (`tri9t-ai/`)
  - `requirements.txt` with all dependencies
  - `.env.example` with `GROQ_API_KEY`, `MONGO_URI`, `DATABASE_URL`
  - `.gitignore` (venv, __pycache__, .env, *.db, data/*.pdf)
  - Empty `__init__.py` files for all packages
  - `data/` folder with both CT-200 PDFs (v1 + v2)
  - Skeleton `README.md`

### Phase 2 — Database Schema
- **Commit:** `feat: implement database schema`
- **Artifact:** `002_database_design.md`
- **Tables:**
  - `documents` — id, filename, created_at
  - `document_versions` — id, document_id, version_number, ingested_at, file_hash
  - `nodes` — id (UUID), version_id, heading, level, body_text, content_hash (SHA-256), parent_id, position, node_path
  - `selections` — id, name, created_at
  - `selection_items` — id, selection_id, node_id, version_id, content_hash_at_selection
- **Design decisions:** Why SHA-256 for content hash, why UUID for node IDs, why `node_path` for hierarchy queries

### Phase 3 — SQLAlchemy ORM Models
- **Commit:** `feat: implement ORM models`
- **Artifact:** `003_models.md`
- **Files:**
  - `backend/database/models.py` — all SQLAlchemy models
  - `backend/database/session.py` — engine + session factory
  - `backend/database/init_db.py` — create_all helper
- **Pydantic schemas** in `backend/database/schemas.py`

### Phase 4 — PDF OCR Pipeline
- **Commit:** `feat: implement OCR extraction pipeline`
- **Artifact:** `004_ocr_pipeline.md`
- **Approach:** `pdfplumber` for text/table extraction + `pytesseract` fallback for scanned pages
- **Files:**
  - `backend/parser/extractor.py` — raw page-level text + table extraction
  - `backend/parser/ocr_fallback.py` — Tesseract fallback for image-heavy pages
- **Key:** Extract per-page text blocks with bounding boxes, font sizes, bold/italic metadata

### Phase 5 — Hierarchy Reconstruction
- **Commit:** `feat: reconstruct document hierarchy`
- **Artifact:** `005_hierarchy.md`
- **Files:**
  - `backend/parser/hierarchy.py` — heading detection, level assignment, tree builder
  - `backend/parser/content_hasher.py` — SHA-256 of normalized body text
- **Algorithm:**
  1. Detect headings via font size + bold + numbering pattern (regex: `^\d+(\.\d+)*\s+`)
  2. Assign levels from numbering depth
  3. Build tree with stack-based parent tracking
  4. Handle edge cases: duplicate headings → distinct node IDs, skipped levels, unnumbered headings
- **This is the critical component** — must correctly produce `1 → 1.1 → 1.1.1 → 2 → 2.1`

### Phase 6 — Parser Validation Tests
- **Commit:** `test: add parser validation tests`
- **Artifact:** `006_parser_tests.md`
- **Files:** `backend/tests/test_parser.py`
- **Required tests (minimum 3, will do 5+):**
  1. Duplicate heading → two distinct node IDs with correct parents
  2. Skipped heading levels → still correct parent assignment
  3. Broken/inconsistent numbering → graceful handling
  4. Table within section → captured and associated with correct node
  5. Content hash determinism — same content → same hash

### Phase 7 — Document Versioning
- **Commit:** `feat: implement document versioning`
- **Artifact:** `007_versioning.md`
- **Files:**
  - `backend/versioning/version_manager.py`
  - `backend/versioning/node_matcher.py`
- **Matching strategy:** Composite score = `title_similarity(0.4) + parent_path_similarity(0.3) + content_hash_match(0.3)`
  - Uses `difflib.SequenceMatcher` for title/parent similarity
  - Threshold: score ≥ 0.6 → same logical node
- **Known failure:** Heading changes completely but content stays identical → will NOT match. Documented in decision log.
- **Never destroys v1** — creates new version rows, links matched nodes

### Phase 8 — Diff Engine
- **Commit:** `feat: implement node comparison`
- **Artifact:** `008_diff_engine.md`
- **Files:** `backend/versioning/diff_engine.py`
- **Approach:** `difflib.unified_diff` on body text
- **Returns:** `{ changed: bool, insertions: int, deletions: int, modified_lines: [...], summary: str }`
- **Known limitation:** No semantic diff — a one-word wording change is treated identically to a changed pressure threshold. Documented.

### Phase 9 — Browse API
- **Commit:** `feat: implement browse API`
- **Artifact:** `009_browse_api.md`
- **Endpoints:**
  - `GET /api/documents` — list documents
  - `POST /api/documents/ingest` — ingest PDF (v1 or v2)
  - `GET /api/documents/{doc_id}/versions` — list versions
  - `GET /api/documents/{doc_id}/tree?version=latest` — top-level sections
  - `GET /api/nodes/{node_id}` — node detail (children, text, content_hash)
  - `GET /api/nodes/{node_id}/diff?from_version=1&to_version=2` — diff across versions

### Phase 10 — Search API
- **Commit:** `feat: implement search API`
- **Artifact:** `010_search.md`
- **Endpoint:** `GET /api/search?q=...&version=latest`
- **Implementation:** SQLite `LIKE` on `heading` and `body_text`
- **Known limitation:** No ranking, no BM25, no embeddings. Documented as intentional trade-off.

### Phase 11 — Selection API
- **Commit:** `feat: implement version pinned selections`
- **Artifact:** `011_selection.md`
- **Endpoints:**
  - `POST /api/selections` — create named selection with `[{node_id, version_id}]`
  - `GET /api/selections/{id}` — retrieve selection with resolved text
- **Key design:** Selection items store `content_hash_at_selection` — pinned to exact text at creation time. Old selections still resolve even after re-ingestion.

### Phase 12 — LLM Integration
- **Commit:** `feat: integrate LLM test generation`
- **Artifact:** `012_llm_generation.md`
- **Files:**
  - `backend/llm/groq_client.py` — Groq API client wrapper
  - `backend/llm/prompt_templates.py` — versioned prompt templates
  - `backend/llm/generator.py` — orchestrator: gather text → prompt → call → parse
- **Prompt design:** System prompt instructs structured JSON output of 3-5 test cases with `{id, title, preconditions, steps[], expected_result, traceability_ref}`
- **Duplicate policy:** If `hash(selection_content + model + prompt_version)` matches existing generation → return cached. No regeneration. Documented.

### Phase 13 — Output Validation
- **Commit:** `feat: validate structured LLM output`
- **Artifact:** `013_output_validation.md`
- **Files:** `backend/llm/validator.py`
- **Approach:** Pydantic model validation of LLM JSON response
- **Error handling:** Retry once on malformed output → if still fails, return error with raw LLM response attached. No repair pipeline. Documented as intentional.

### Phase 14 — MongoDB Persistence
- **Commit:** `feat: store generated QA outputs`
- **Artifact:** `014_generation_storage.md`
- **Files:** `backend/database/mongo_client.py`
- **Collection `generations`:**
  ```json
  {
    "selection_id": "...",
    "node_ids": [...],
    "version_id": "...",
    "content_hashes": {...},
    "model": "llama-3.3-70b-versatile",
    "prompt_version": "v1",
    "test_cases": [...],
    "created_at": "...",
    "selection_content_hash": "..."
  }
  ```
- **Traceability chain preserved:** generation → selection → node+version → content_hash

### Phase 15 — Staleness Detection
- **Commit:** `feat: implement impact detection`
- **Artifact:** `015_staleness.md`
- **Files:** `backend/versioning/staleness.py`
- **Algorithm:**
  1. For each node in a generation's source selection
  2. Find the node in the latest version (via node_matcher)
  3. Compare `content_hash` at generation time vs current
  4. If different → `STALE`, if same → `CURRENT`, if node missing → `ORPHANED`
- **Returns:** per-node staleness status + overall generation staleness

### Phase 16 — Retrieval API
- **Commit:** `feat: implement generation retrieval`
- **Artifact:** `016_retrieval.md`
- **Endpoints:**
  - `GET /api/generations?selection_id=...` — by selection
  - `GET /api/generations?node_id=...` — by node
  - `GET /api/generations/{id}` — specific generation with **staleness check included**
- **Key:** Staleness check runs at retrieval time, not at ingestion time

### Phase 17 — End-to-End Tests
- **Commit:** `test: add integration tests`
- **Artifact:** `017_e2e_tests.md`
- **Files:** `backend/tests/test_e2e.py`
- **Scenarios:**
  1. Ingest v1 → browse tree → verify hierarchy
  2. Ingest v2 → verify versioning + node matching
  3. Create selection → generate QA → verify traceability
  4. Ingest v2 → check staleness on v1-based generation
  5. Search flow
  6. Diff flow between versions

### Phase 18 — Documentation
- **Commit:** `docs: add approach document and README`
- **Artifact:** `018_documentation.md`
- **Deliverables:**
  - Complete `README.md` with setup/run/test/demo instructions
  - `approach_document.md` with:
    - Data model description
    - Parser decisions + edge case handling
    - Version matching strategy + failure modes
    - LLM prompt design + structured output strategy
    - Decision log (3 required answers)
    - "What I'd do differently" section

### Phase 19 — Final Cleanup
- **Commit:** `chore: final cleanup`
- **Artifact:** `019_final_review.md`
- **Tasks:** Remove dead code, verify .env.example, ensure all tests pass, final README review

---

## Final Directory Structure

```
tri9t-ai/
├── backend/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry
│   ├── config.py                  # Settings via pydantic-settings
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── extractor.py           # PDF text/table extraction
│   │   ├── ocr_fallback.py        # Tesseract fallback
│   │   ├── hierarchy.py           # Tree reconstruction
│   │   └── content_hasher.py      # SHA-256 hashing
│   ├── versioning/
│   │   ├── __init__.py
│   │   ├── version_manager.py     # Version creation/management
│   │   ├── node_matcher.py        # Cross-version node matching
│   │   ├── diff_engine.py         # Text diff
│   │   └── staleness.py           # Impact detection
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── groq_client.py         # Groq API wrapper
│   │   ├── prompt_templates.py    # Versioned prompts
│   │   ├── generator.py           # Orchestrator
│   │   └── validator.py           # Pydantic output validation
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py              # SQLAlchemy models
│   │   ├── schemas.py             # Pydantic schemas
│   │   ├── session.py             # DB engine/session
│   │   ├── init_db.py             # Table creation
│   │   └── mongo_client.py        # MongoDB connection
│   └── tests/
│       ├── __init__.py
│       ├── test_parser.py         # Parser unit tests
│       └── test_e2e.py            # Integration tests
├── data/
│   ├── ct200_manual_v1.pdf
│   └── ct200_manual_v2.pdf
├── artifacts/
│   ├── 001_project_setup.md
│   ├── ...
│   └── 019_final_review.md
├── .env.example
├── .gitignore
├── README.md
├── approach_document.md
└── requirements.txt
```

---

## Key Dependencies

```
fastapi>=0.100.0
uvicorn[standard]
sqlalchemy>=2.0
pydantic>=2.0
pydantic-settings
pdfplumber
pytesseract
Pillow
pymongo
groq
python-multipart
difflib (stdlib)
hashlib (stdlib)
pytest
httpx (for test client)
```

---

## What I Need From You

> [!IMPORTANT]
> The following items are required before development can begin.

### 1. 📄 The CT-200 PDF Files (CRITICAL)
- Download both `ct200_manual_v1.pdf` and `ct200_manual_v2.pdf` from the [Google Drive folder](https://drive.google.com/drive/folders/1ybTlunyBpP7Q7Bkw0mbnmGfePWBuiWD4)
- Place them in `d:\PROJECTS\meddoc-engine\data\`
- **I cannot download from Google Drive programmatically** — this is a manual step

### 2. 🔧 Environment Confirmation
- **Python version** — confirm you have Python 3.11+ installed
- **Tesseract OCR** — do you have Tesseract installed on Windows? (needed for OCR fallback)
  - If not, I'll include installation instructions or we can use `pdfplumber`-only mode
- **MongoDB** — do you have MongoDB running locally, or should I use MongoDB Atlas free tier?
  - If local: confirm the connection URI
  - If Atlas: I'll set up a free cluster URI in `.env`

### 3. 🔑 Credentials Confirmation
- **Groq API Key:** ✅ Provided (`gsk_ubCH...q4iK`)
- **GitHub credentials:** Can you push to `AkshayG-30/meddoc-engine`? Or should I prepare commits locally for you to push?

### 4. 📋 Development Preferences
- **Commit strategy:** Should I make all 19 commits locally and you push them in batch? Or do you want me to implement phase-by-phase with you reviewing each?
- **Git author:** What name and email should the commits use?
- **Any deadline?** This affects whether I parallelize some phases

### 5. 🧪 Testing Preferences
- Should tests run with real PDFs or should I create synthetic test fixtures?
- For LLM integration tests: run against real Groq API or mock?

---

## Risk Assessment

| Risk | Mitigation |
|---|---|
| PDF structure inconsistencies not visible until parsing | Manual inspection of first 10 pages before writing parser rules |
| Groq API rate limits on free tier | Built-in retry with backoff; cached generations avoid re-calls |
| MongoDB connection issues | Fallback: JSON file store (justify in approach doc if needed) |
| Node matching false positives across versions | Tunable threshold + documented failure modes |
| Tesseract not available on Windows | `pdfplumber`-only primary path; Tesseract as optional enhancement |
