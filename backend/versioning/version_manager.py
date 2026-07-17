"""Document versioning — manages version creation and cross-version node matching.

Matching strategy: Composite score using title similarity + parent path similarity + content hash.
This is intentionally "good enough" — see known limitations below.
"""

import difflib
from typing import Optional

from sqlalchemy.orm import Session

from backend.database.models import Document, DocumentVersion, Node


def get_or_create_document(db: Session, name: str) -> Document:
    """Get existing document by name or create a new one."""
    doc = db.query(Document).filter(Document.name == name).first()
    if not doc:
        doc = Document(name=name)
        db.add(doc)
        db.commit()
        db.refresh(doc)
    return doc


def create_version(
    db: Session,
    document: Document,
    file_hash: str,
    filename: str,
) -> DocumentVersion:
    """Create a new version for a document.
    
    Version numbers auto-increment per document.
    """
    # Get next version number
    max_version = (
        db.query(DocumentVersion.version_number)
        .filter(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.version_number.desc())
        .first()
    )
    next_version = (max_version[0] + 1) if max_version else 1
    
    version = DocumentVersion(
        document_id=document.id,
        version_number=next_version,
        file_hash=file_hash,
        filename=filename,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def _title_similarity(a: str, b: str) -> float:
    """Compute title similarity using SequenceMatcher.
    
    Returns a float between 0.0 and 1.0.
    """
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _parent_path_similarity(path_a: str, path_b: str) -> float:
    """Compute parent path similarity.
    
    e.g., '2.1.1' vs '2.1.1' → 1.0
          '2.1.1' vs '2.1.2' → 0.67
    """
    parts_a = path_a.split('.') if path_a else []
    parts_b = path_b.split('.') if path_b else []
    
    if not parts_a and not parts_b:
        return 1.0
    if not parts_a or not parts_b:
        return 0.0
    
    # Compare from root down
    matches = 0
    max_len = max(len(parts_a), len(parts_b))
    for i in range(min(len(parts_a), len(parts_b))):
        if parts_a[i] == parts_b[i]:
            matches += 1
    
    return matches / max_len if max_len > 0 else 0.0


def match_nodes(
    db: Session,
    new_version_id: str,
    old_version_id: str,
    threshold: float = 0.6,
):
    """Match nodes between two versions using composite similarity.
    
    Matching strategy:
    - title_similarity (weight: 0.4) — SequenceMatcher on heading text
    - parent_path_similarity (weight: 0.3) — structural position match
    - content_hash_match (weight: 0.3) — exact content match
    
    Threshold: 0.6 — nodes scoring below this are considered new/deleted.
    
    KNOWN LIMITATION: If a heading changes completely but content stays identical,
    the title similarity (0.4 weight) will be near 0, and even with perfect content
    hash match (0.3), total score = 0.3 + path_sim*0.3, which may fall below 0.6.
    This is a deliberate trade-off: heading identity matters for traceability.
    """
    new_nodes = db.query(Node).filter(Node.version_id == new_version_id).all()
    old_nodes = db.query(Node).filter(Node.version_id == old_version_id).all()
    
    if not old_nodes:
        return  # First version, nothing to match
    
    # Track which old nodes have been matched
    matched_old_ids = set()
    
    for new_node in new_nodes:
        best_score = 0.0
        best_match: Optional[Node] = None
        
        for old_node in old_nodes:
            if old_node.id in matched_old_ids:
                continue
            
            # Compute composite similarity
            title_sim = _title_similarity(new_node.heading, old_node.heading)
            path_sim = _parent_path_similarity(new_node.node_path, old_node.node_path)
            hash_match = 1.0 if new_node.content_hash == old_node.content_hash else 0.0
            
            score = (title_sim * 0.4) + (path_sim * 0.3) + (hash_match * 0.3)
            
            if score > best_score:
                best_score = score
                best_match = old_node
        
        if best_match and best_score >= threshold:
            new_node.matched_node_id = best_match.id
            new_node.has_changed = (new_node.content_hash != best_match.content_hash)
            matched_old_ids.add(best_match.id)
    
    db.commit()
