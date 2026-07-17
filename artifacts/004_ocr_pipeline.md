# 004 — OCR/PDF Extraction Pipeline

## What Was Built
PDF text extraction pipeline using `pdfplumber` with font-metadata-based heading detection.

## Approach
- **Tool**: `pdfplumber` — extracts text with character-level metadata (font size, font name, position)
- **No OCR needed**: The CT-200 PDF is text-based (not scanned), so pdfplumber extracts text directly
- **Heading detection**: Uses font size + bold attribute + numbered prefix pattern

### Font Size Mapping (discovered from PDF inspection)
| Font Size | Font Name | Role |
|---|---|---|
| 22.0 | Nimbus Sans Bold | Document title |
| 16.5 | Nimbus Sans Bold | Top-level sections (1., 2., etc.) |
| 12.9 | Nimbus Sans Bold | Subsections (1.1, 2.1, etc.) |
| 11.0 | Nimbus Sans Bold | Sub-subsections (2.1.1.1) |
| 11.0 | Nimbus Sans Regular | Body text |

### Heading Detection Algorithm
1. Extract all characters with font metadata
2. Group characters by vertical position (same line)
3. For each line, check: is it bold AND matches numbered heading pattern?
4. If yes → it's a heading; level = depth of numbering (1.2.3 = level 3)

## Design Decisions
- **Why pdfplumber over PyMuPDF/Tesseract?** pdfplumber provides direct access to character-level font metadata, which is essential for distinguishing headings from body text. PyMuPDF would work too but pdfplumber's table extraction is superior.
- **Why font-based detection instead of regex-only?** The document has a case where section 3.2 uses font size 11.0 (same as body text) but is bold — regex alone would miss the size distinction needed for some edge cases.
- **Table extraction**: Uses pdfplumber's built-in table detection. Tables are associated with the section that precedes them on the same page.

## Edge Cases Handled
1. **Title spanning multiple lines** (3 lines at size 22.0) — detected and concatenated
2. **Tables within sections** — extracted and stored as formatted text with [TABLE]/[/TABLE] markers

## Known Limitations
- Table association is page-based — a table at the top of a page might be associated with the wrong section
- Only supports text-based PDFs; truly scanned documents would need OCR fallback
