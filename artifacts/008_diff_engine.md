# 008 — Diff Engine

## What Was Built
Lightweight text diff engine using Python's `difflib.unified_diff`.

## Output Format
```json
{
  "changed": true,
  "insertions": 3,
  "deletions": 1,
  "modified_lines": ["+new line", "-old line"],
  "summary": "3 line(s) added, 1 line(s) removed."
}
```

## Known Limitations
- **No semantic diff**: A one-word wording change is treated identically to a changed pressure threshold
- **No numerical analysis**: "±3 mmHg" → "±5 mmHg" is just a text change, not flagged as a requirement change
- **Line-based**: Changes within a line are reported as full line replacement

## Why This Is Acceptable
The assignment says "lightweight diff summary" — this delivers exactly that. A production system would benefit from:
- NLP-based semantic diff
- Numerical value extraction and comparison
- Requirement-aware change classification
