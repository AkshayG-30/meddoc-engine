"""PDF text and structure extraction using pdfplumber.

Extracts text with font metadata (size, bold/italic, position) from PDF pages.
This is the foundation for hierarchy reconstruction.
"""

import re
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber


@dataclass
class TextBlock:
    """A contiguous block of text with consistent formatting."""
    text: str
    font_size: float
    is_bold: bool
    font_name: str
    page_number: int
    top_position: float  # vertical position on page


@dataclass
class TableData:
    """A table extracted from the PDF."""
    rows: list[list[str]]
    page_number: int
    top_position: float

    def to_text(self) -> str:
        """Convert table to plain text representation."""
        if not self.rows:
            return ""
        lines = []
        # Calculate column widths
        col_widths = []
        for row in self.rows:
            for i, cell in enumerate(row):
                cell_text = (cell or "").strip()
                if i >= len(col_widths):
                    col_widths.append(len(cell_text))
                else:
                    col_widths[i] = max(col_widths[i], len(cell_text))

        for row in self.rows:
            cells = []
            for i, cell in enumerate(row):
                cell_text = (cell or "").strip()
                width = col_widths[i] if i < len(col_widths) else 20
                cells.append(cell_text.ljust(width))
            lines.append(" | ".join(cells))
        return "\n".join(lines)


@dataclass
class RawHeading:
    """A detected heading with its numbering, text, level, and position."""
    number: str           # e.g., '2.1.1.1'
    title: str            # e.g., 'Battery Life Under Typical Use'
    level: int            # depth based on number (1=top, 2=sub, etc.)
    font_size: float
    is_bold: bool
    page_number: int
    top_position: float


@dataclass
class RawSection:
    """A section with its heading and body content."""
    heading: RawHeading
    body_text: str = ""
    tables: list[TableData] = field(default_factory=list)


def extract_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of the PDF file itself."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _group_chars_to_lines(chars: list[dict]) -> list[dict]:
    """Group characters into lines based on their vertical position.
    
    Characters with the same top position (within tolerance) form a line.
    Each line retains the dominant font size and bold status.
    """
    if not chars:
        return []
    
    lines = {}
    for c in chars:
        # Round top to nearest integer to group characters on the same line
        top_key = round(c['top'], 0)
        if top_key not in lines:
            lines[top_key] = []
        lines[top_key].append(c)
    
    result = []
    for top_key in sorted(lines.keys()):
        line_chars = lines[top_key]
        # Sort chars by x position
        line_chars.sort(key=lambda c: c['x0'])
        text = ''.join(c['text'] for c in line_chars).strip()
        if not text:
            continue
        
        sizes = [round(c['size'], 1) for c in line_chars if c['text'].strip()]
        fonts = [c.get('fontname', '') for c in line_chars if c['text'].strip()]
        
        max_size = max(sizes) if sizes else 11.0
        is_bold = any('Bold' in f for f in fonts)
        dominant_font = fonts[0] if fonts else 'unknown'
        
        result.append({
            'text': text,
            'size': max_size,
            'is_bold': is_bold,
            'font': dominant_font,
            'top': top_key,
        })
    
    return result


# Heading pattern: matches numbered sections like "1.", "1.1", "2.1.1.1", etc.
HEADING_PATTERN = re.compile(r'^(\d+(?:\.\d+)*\.?)\s+(.*)')


def _is_heading_line(line: dict) -> tuple[bool, str, str, int]:
    """Determine if a line is a heading based on font and numbering.
    
    Returns: (is_heading, number, title, level)
    
    Heading detection strategy:
    1. Bold text with numbered prefix → always a heading
    2. Font size > 11.0 (body text size) → heading
    3. Level determined by number depth (1=top, 1.1=sub, etc.)
    """
    text = line['text']
    size = line['size']
    is_bold = line['is_bold']
    
    match = HEADING_PATTERN.match(text)
    if match and (is_bold or size > 11.0):
        number = match.group(1).rstrip('.')
        title = match.group(2).strip()
        level = len(number.split('.'))
        return True, number, title, level
    
    return False, '', '', 0


def _is_title_line(line: dict) -> bool:
    """Check if a line is the document title (largest font)."""
    return line['size'] >= 20.0 and line['is_bold']


def extract_from_pdf(file_path: str) -> tuple[list[RawSection], list[str]]:
    """Extract structured sections from a PDF file.
    
    Returns:
        sections: List of RawSection objects with headings and body text
        title_lines: Lines that form the document title
    
    Strategy:
    1. Extract all characters with font metadata using pdfplumber
    2. Group characters into lines
    3. Identify headings via bold font + numbered prefix pattern
    4. Collect body text between headings
    5. Extract tables and associate with the preceding section
    """
    pdf = pdfplumber.open(file_path)
    
    all_lines = []
    all_tables = []
    title_lines = []
    
    for page_num, page in enumerate(pdf.pages):
        # Extract character-level data
        chars = page.chars
        if chars:
            lines = _group_chars_to_lines(chars)
            for line in lines:
                line['page'] = page_num + 1
                all_lines.append(line)
        
        # Extract tables
        tables = page.extract_tables()
        if tables:
            for table in tables:
                if table and any(any(cell for cell in row) for row in table):
                    td = TableData(
                        rows=table,
                        page_number=page_num + 1,
                        top_position=0,  # Approximate
                    )
                    all_tables.append(td)
    
    pdf.close()
    
    # Phase 1: Identify title lines and headings
    sections = []
    current_body_lines = []
    current_heading = None
    
    for line in all_lines:
        # Check for document title
        if _is_title_line(line) and not current_heading:
            title_lines.append(line['text'])
            continue
        
        # Check for heading
        is_heading, number, title, level = _is_heading_line(line)
        
        if is_heading:
            # Save previous section
            if current_heading:
                body = '\n'.join(current_body_lines).strip()
                sections.append(RawSection(
                    heading=current_heading,
                    body_text=body,
                ))
            
            current_heading = RawHeading(
                number=number,
                title=title,
                level=level,
                font_size=line['size'],
                is_bold=line['is_bold'],
                page_number=line['page'],
                top_position=line['top'],
            )
            current_body_lines = []
        else:
            # Body text
            if current_heading:
                current_body_lines.append(line['text'])
    
    # Don't forget the last section
    if current_heading:
        body = '\n'.join(current_body_lines).strip()
        sections.append(RawSection(
            heading=current_heading,
            body_text=body,
        ))
    
    # Associate tables with sections
    # Simple strategy: table belongs to the section that precedes it on the same page
    for table in all_tables:
        for section in sections:
            if section.heading.page_number == table.page_number:
                section.tables.append(table)
                break
        else:
            # If no section on the same page, attach to the last section before the table's page
            for section in reversed(sections):
                if section.heading.page_number <= table.page_number:
                    section.tables.append(table)
                    break
    
    return sections, title_lines
