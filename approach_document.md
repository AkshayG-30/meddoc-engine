# Approach Document — MedDoc Engine

## 1. System Architecture

### Data Model
```
Document (1) ──→ (N) DocumentVersion (1) ──→ (N) Node
                                                   ↑
Selection (1) ──→ (N) SelectionItem ──────────────┘
                                                   
Generation (MongoDB) ──→ Selection ──→ Node+Version ──→ Content Hash
```

**SQLite** stores the document tree (structured, relational queries needed).
**MongoDB** stores LLM-generated output (semi-structured, variable schema).

### Why Two Databases?
The document tree is inherently relational: parent-child relationships, cross-version references, version-pinned selections — all benefit from foreign keys and JOINs. Generated test cases are semi-structured documents that vary in shape and are best stored as-is.

---

## 2. PDF Parsing Approach

### Tool Selection
**pdfplumber** was selected over alternatives:

| Tool | Pros | Cons | Verdict |
|---|---|---|---|
| pdfplumber | Character-level font metadata, native table extraction | Slower on large PDFs | ✅ Selected |
| PyMuPDF | Fast, mature | Less convenient font metadata API | Could work |
| Tesseract OCR | Handles scanned documents | CT-200 is text-based; OCR is unnecessary overhead | Not needed |

### Heading Detection Strategy
The CT-200 PDF uses a consistent font hierarchy:
- **22.0pt Bold**: Document title
- **16.5pt Bold**: Top-level sections (1., 2., ...)
- **12.9pt Bold**: Subsections (1.1, 2.1, ...)
- **11.0pt Bold**: Sub-subsections (2.1.1.1)
- **11.0pt Regular**: Body text

Detection algorithm:
1. Extract characters with font metadata
2. Group by vertical position (same line)
3. Check: `is_bold AND matches_numbered_pattern` → heading
4. Level = depth of numbering (e.g., 2.1.1 = level 3)

### Hierarchy Reconstruction
Stack-based parent tracking (O(n)):
```python
for section in document_order:
    while stack.top.level >= section.level:
        stack.pop()
    parent = stack.top (if any)
    stack.push(section)
```

---

## 3. Structural Inconsistencies Discovered

### Edge Case 1: Out-of-Order Numbering
Section 3.4 (Auto Shutoff) appears in the PDF before 3.3 (Result Display and Classification).

**Handling**: We preserve document order, not numerical order. Both are children of section 3, positioned by their appearance in the PDF. This is intentional — the PDF is the source of truth, not our assumptions about numbering.

### Edge Case 2: Skipped Heading Levels
Section 2.1.1.1 (Battery Life Under Typical Use) exists, but there is no 2.1.1. The hierarchy jumps from level 2 (2.1) to level 4 (2.1.1.1).

**Handling**: The stack algorithm naturally handles this — it pops to find the nearest ancestor with a lower level. 2.1 (level 2) becomes the parent of 2.1.1.1 (level 4).

### Edge Case 3: Duplicate Heading Text
"Error Codes" appears as both section 4.2 and section 7.1, with different content and different parents.

**Handling**: Every node receives a UUID. Identification is by ID, never by heading text. Both "Error Codes" nodes exist independently with correct parent assignments.

### Edge Case 4: Table Extraction
Section 2.1 (General Specifications) and 4.2 (Error Codes) contain tables.

**Handling**: pdfplumber's native table extraction captures bordered tables. Tables are stored as formatted text within their parent section's body, marked with [TABLE]/[/TABLE] delimiters. They are never silently discarded.

---

## 4. What My Initial Implementation Failed to Handle

My first implementation used regex-only heading detection without font metadata. This failed because:
1. Section 3.2 has font size 11.0pt (same as body text) — only the bold attribute distinguishes it
2. The title spans 3 lines at 22.0pt — regex expected it on one line

I identified these failures by:
- **Manual inspection**: Compared extracted headings against the PDF visually
- **Automated test**: `test_complete_tree_structure` caught missing nodes (got 25 instead of 27)
- **Font metadata dump**: Wrote `_inspect_pdf.py` to print all font sizes and names

Fix: Combined font-based detection (size + bold) with numbering pattern matching.

---

## 5. Version-Matching Strategy

### Algorithm
Composite similarity scoring for cross-version node matching:

```
score = title_similarity(0.4) + parent_path_similarity(0.3) + content_hash_match(0.3)
```

- **Title similarity** (weight 0.4): `difflib.SequenceMatcher` ratio on heading text
- **Parent path similarity** (weight 0.3): Position-based matching (e.g., '2.1' vs '2.1')
- **Content hash match** (weight 0.3): 1.0 if SHA-256 hashes match, 0.0 otherwise
- **Threshold**: ≥ 0.6 to qualify as "same logical node"

### Known Failure Modes
1. **Complete heading rename**: If "Battery Life" becomes "Power Duration" but body text is unchanged, title_sim ≈ 0.0, path_sim = 1.0, hash_match = 1.0 → total = 0.6. Right at threshold — unreliable.
2. **Section reordering with renumbering**: If section 3.1 moves to become 5.2, path similarity drops to near 0 even if content is identical.
3. **Greedy matching**: We take the best match for each new node. In theory, a global optimal assignment (Hungarian algorithm) would be more accurate, but greedy is sufficient for this document.

### Why Not Embeddings?
Embedding-based matching would handle semantic similarity better but introduces:
- External model dependency
- Latency for embedding computation
- Complexity that's not justified for a 6-page document with numbered headings

Title similarity + path matching is "good enough" and fully explainable.

---

## 6. LLM Prompt Design

### System Prompt
Instructs the LLM to act as a medical device QA engineer. Enforces strict JSON output format with `{id, title, preconditions, steps[], expected_result, traceability_ref}`.

### Structured Output Strategy
1. JSON schema specified in system prompt
2. Extraction from response handles: raw JSON, code blocks, preamble text
3. Pydantic validation against `LLMTestCaseResponse` schema
4. If malformed → retry once → if still malformed → fail with raw response

### Why "Retry Once, Then Fail"?
A production system would implement:
```
retry → repair → retry → validator → partial parser
```
With one LLM call costing ~2-3 seconds, a full retry pipeline could take 10-15 seconds. For this assignment, retry-once with clear error reporting is sufficient and defensible.

### Duplicate Selection Policy
If `hash(selection_content + model + prompt_version)` matches an existing generation → return cached result. Same input + same model + same prompt = same output. No regeneration.

---

## 7. Staleness Detection

### Mechanism
At **retrieval time** (not ingestion time):
1. For each node in the generation's source selection
2. Find the corresponding node in the latest document version
3. Compare `content_hash` at generation time vs current
4. Status: CURRENT (match), STALE (changed), ORPHANED (node gone)

### Honest Limitations
- **Binary staleness**: Any text change = STALE. A cosmetic rewording and a changed safety threshold trigger the same status.
- **No semantic analysis**: "±3 mmHg" → "±5 mmHg" is not flagged differently from a grammar fix.
- **What it should do**: A production system would extract numerical values and requirements separately, flagging threshold changes as "critical" and wording changes as "minor."

---

## 8. Decision Log (Required)

### Q1: What's the one part most likely to silently give wrong results?
**The node matching algorithm.** If a heading is reworded significantly between versions, the matcher may create a new node instead of recognizing it as the same logical node. This means:
- Old test cases linked to that node become "orphaned" even though the content still exists
- The system reports staleness that doesn't actually exist

**How I'd catch it**: A validation report after re-ingestion showing unmatched nodes with content hash collisions — i.e., "these nodes have identical content but weren't matched."

### Q2: Where did you choose simplicity over correctness?
**The diff engine.** `difflib` treats all text changes equally. In a real medical device QA system, a change from "±3 mmHg" to "±5 mmHg" should be flagged as a requirement change, not just a text modification. This would break first if used for compliance reporting where numerical changes have regulatory implications.

### Q3: One input you did not handle?
**A completely restructured document** where sections are reordered, renumbered, merged, and split simultaneously. The greedy node matcher assumes a mostly stable structure with incremental changes. A document where section 3 becomes section 7 and section 4 is split into 4 and 5 would produce mostly orphaned nodes and false staleness. The system would still function (it wouldn't crash), but the matching quality would be poor.

---

## 9. What I'd Do Differently With More Time

1. **Embedding-based node matching** for better cross-version alignment when headings change
2. **Semantic diff** with numerical value extraction for requirement-aware change detection
3. **FTS5 search** instead of LIKE queries for better search quality
4. **Async processing** for PDF ingestion (it's synchronous and blocks the request)
5. **Alembic migrations** for database schema evolution
6. **Rate limiting** on the LLM generation endpoint
7. **LLM output repair pipeline** instead of retry-once-then-fail
8. **Visual diff view** showing exact character-level changes between versions
