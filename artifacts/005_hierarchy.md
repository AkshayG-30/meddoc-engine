# 005 — Hierarchy Reconstruction

## What Was Built
Stack-based hierarchy reconstruction algorithm that builds a proper document tree from flat parsed sections.

## Algorithm
```
for each section in document order:
    1. Pop stack until top has lower level than current
    2. If stack not empty → parent is top of stack
    3. If stack empty → top-level node
    4. Push current node onto stack
```

This is O(n) and correctly handles all edge cases.

## Edge Cases Handled

### 1. Duplicate Headings
**Problem**: "Error Codes" appears as both 4.2 and 7.1
**Solution**: Each section gets a unique UUID regardless of heading text. Node identification is by ID, not by heading.

### 2. Skipped Levels
**Problem**: 2.1 → 2.1.1.1 (no 2.1.1 exists)
**Solution**: The stack pops to find the nearest ancestor with a lower level. 2.1 (level 2) is the parent of 2.1.1.1 (level 4), because there's no level 3 node to be the intermediate parent.

### 3. Out-of-Order Sections
**Problem**: 3.4 appears before 3.3 in the document
**Solution**: We process sections in **document order**, not numerical order. 3.4 and 3.3 are both children of section 3, in the order they appear.

## Output Verification
```
1. Device Overview (children=2)
  1.1. Intended Use
  1.2. Indications and Contraindications
2. Physical and Electrical Specifications (children=2)
  2.1. General Specifications (children=1)
    2.1.1.1. Battery Life Under Typical Use  ← skipped levels handled
  2.2. Cuff Specifications
3. Device Operation (children=4)
  3.1. Powering On and Profile Selection
  3.2. Cuff Inflation Sequence
  3.4. Auto Shutoff  ← out of order preserved
  3.3. Result Display and Classification
4-8: [correct hierarchy verified]
```

## Design Decisions
- **Stack-based over recursive**: Simpler, O(n), handles all edge cases naturally
- **Position tracks document order**: `position` field preserves the original PDF order
- **Content hash uses normalized text**: Lowercase + collapsed whitespace to avoid false staleness

## Known Limitations
- If a PDF has unnumbered headings mixed with numbered ones, the algorithm may misplace them
- Level inference relies entirely on the numbering depth — font size is used only for heading detection, not level assignment
