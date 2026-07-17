"""SQLAlchemy database models for the document tree, versions, and selections."""

import uuid
import hashlib
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    Float,
    Boolean,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


class Document(Base):
    """Represents a logical document (e.g., 'CT-200 Manual').
    
    A document can have multiple versions when re-ingested.
    """
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=utc_now)

    versions = relationship("DocumentVersion", back_populates="document", order_by="DocumentVersion.version_number")

    def __repr__(self):
        return f"<Document(id={self.id}, name={self.name})>"


class DocumentVersion(Base):
    """A specific version of a document, created each time the PDF is re-ingested.
    
    Preserves the complete tree for that version — v1 is never destroyed.
    """
    __tablename__ = "document_versions"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    file_hash = Column(String, nullable=False)  # SHA-256 of the PDF file
    filename = Column(String, nullable=False)
    ingested_at = Column(DateTime, default=utc_now)

    document = relationship("Document", back_populates="versions")
    nodes = relationship("Node", back_populates="version", order_by="Node.position")

    def __repr__(self):
        return f"<DocumentVersion(id={self.id}, v={self.version_number})>"


class Node(Base):
    """A single node in the document hierarchy tree.
    
    Each node retains:
    - heading and level
    - body text
    - parent/child relationships
    - content hash for staleness detection
    - node_path for hierarchy reconstruction (e.g., '1.2.3')
    """
    __tablename__ = "nodes"

    id = Column(String, primary_key=True, default=generate_uuid)
    version_id = Column(String, ForeignKey("document_versions.id"), nullable=False)
    heading = Column(String, nullable=False)
    level = Column(Integer, nullable=False)  # 0 = root/document, 1 = top section, 2 = subsection, etc.
    body_text = Column(Text, default="")
    content_hash = Column(String, nullable=False)  # SHA-256 of normalized body text
    parent_id = Column(String, ForeignKey("nodes.id"), nullable=True)  # NULL for top-level nodes
    position = Column(Integer, nullable=False)  # Order within siblings
    node_path = Column(String, nullable=False)  # e.g., '1', '1.1', '1.1.2' — for hierarchy queries
    
    # For cross-version matching
    matched_node_id = Column(String, nullable=True)  # ID of corresponding node in previous version
    has_changed = Column(Boolean, default=False)  # True if content differs from matched node

    version = relationship("DocumentVersion", back_populates="nodes")
    parent = relationship("Node", remote_side=[id], backref="children")

    def __repr__(self):
        return f"<Node(id={self.id}, path={self.node_path}, heading={self.heading[:30]})>"

    @staticmethod
    def compute_content_hash(text: str) -> str:
        """Compute SHA-256 hash of normalized text content.
        
        Normalization: strip whitespace, lowercase, collapse multiple spaces.
        This ensures minor formatting changes don't trigger false staleness.
        """
        normalized = " ".join(text.lower().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class Selection(Base):
    """A named selection of nodes, version-pinned.
    
    Selections reference specific node+version pairs so that if the document
    is later re-ingested, old selections still resolve to the exact text
    they were created against.
    """
    __tablename__ = "selections"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    items = relationship("SelectionItem", back_populates="selection")

    def __repr__(self):
        return f"<Selection(id={self.id}, name={self.name})>"


class SelectionItem(Base):
    """An individual node reference within a selection.
    
    Stores the content_hash at the time of selection creation,
    enabling staleness detection even after re-versioning.
    """
    __tablename__ = "selection_items"

    id = Column(String, primary_key=True, default=generate_uuid)
    selection_id = Column(String, ForeignKey("selections.id"), nullable=False)
    node_id = Column(String, ForeignKey("nodes.id"), nullable=False)
    version_id = Column(String, ForeignKey("document_versions.id"), nullable=False)
    content_hash_at_selection = Column(String, nullable=False)  # Snapshot of node's content hash

    selection = relationship("Selection", back_populates="items")
    node = relationship("Node")
    version = relationship("DocumentVersion")

    def __repr__(self):
        return f"<SelectionItem(selection={self.selection_id}, node={self.node_id})>"
