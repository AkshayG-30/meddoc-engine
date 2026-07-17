# 010 — Search API

## What Was Built
Simple search endpoint using SQLite LIKE queries across node headings and body text.

## Endpoint
`GET /api/search?q=overpressure&version=1&doc_id=...`

## Implementation
```sql
WHERE (heading LIKE '%query%') OR (body_text LIKE '%query%')
```

## Known Limitations
- No ranking or relevance scoring
- No BM25, TF-IDF, or vector search
- Case-sensitive on SQLite (could be improved with COLLATE NOCASE)
- No stemming or fuzzy matching

## Why This Is Acceptable
The assignment asks for "search/filter across node headings or text." LIKE-based search satisfies this requirement. A production system would use full-text search (FTS5) or a dedicated search engine.
