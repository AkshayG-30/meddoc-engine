# 001 — Project Setup

## What Was Built
Initialized the project repository with a clean, modular structure following Python best practices.

## Structure
```
tri9t-ai/
├── backend/
│   ├── config.py           # Centralized settings via pydantic-settings
│   ├── parser/             # PDF extraction & hierarchy reconstruction
│   ├── versioning/         # Document version management
│   ├── llm/                # LLM integration (Groq)
│   ├── database/           # SQLAlchemy + MongoDB persistence
│   └── tests/              # Unit & integration tests
├── data/                   # CT-200 manual PDFs (v1 + v2)
├── artifacts/              # Engineering decision logs
├── .env.example            # Environment variable template
├── .gitignore              # Python/IDE/DB exclusions
├── requirements.txt        # All dependencies
└── README.md               # Setup and usage instructions
```

## Design Decisions

### Why this structure?
- **Separation of concerns**: Each package (parser, versioning, llm, database) is independently testable
- **Config via pydantic-settings**: Type-safe, validated, .env-aware configuration
- **data/ not gitignored**: PDFs are part of the assignment deliverable

### Dependencies chosen
| Dependency | Purpose | Why this one? |
|---|---|---|
| pdfplumber | PDF text extraction | Best balance of accuracy and simplicity for text-based PDFs; handles tables natively |
| SQLAlchemy 2.0 | ORM for document tree | Assignment requirement; 2.0 for modern async-compatible API |
| pymongo | MongoDB driver | Direct driver — no ODM overhead for simple document storage |
| groq | LLM API client | Official SDK, clean interface, free tier available |

### What was NOT included
- Tesseract/OCR: The CT-200 PDF is text-based, not scanned. pdfplumber handles it directly.
- Docker: Out of scope for the assignment timeline.
- Pre-commit hooks: Would add in production.

## Known Limitations
- No CI/CD pipeline yet
- .env must be manually created from .env.example

## Future Work
- Add Docker Compose for MongoDB + app
- Add pre-commit hooks (black, ruff, mypy)
