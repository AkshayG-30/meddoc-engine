"""End-to-end integration tests.

Tests the full flow: ingest → browse → select → generate → version → staleness.
Uses the FastAPI TestClient for API testing against a fresh database.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi.testclient import TestClient
from backend.main import app


# Use the running app's database for e2e tests
client = TestClient(app)

PDF_V1_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "ct200_manual.pdf")
PDF_V2_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "ct200_manual_v2.pdf")


class TestDocumentIngestion:
    """Tests for document ingestion and versioning."""

    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_ingest_v1(self):
        """Ingest v1 of the CT-200 manual."""
        with open(PDF_V1_PATH, "rb") as f:
            response = client.post(
                "/api/documents/ingest",
                files={"file": ("ct200_manual.pdf", f, "application/pdf")},
                data={"document_name": "CT-200 E2E Test"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["version_number"] == 1
        assert data["nodes_created"] == 27
        # Store for later tests
        TestDocumentIngestion.doc_id = data["document_id"]
        TestDocumentIngestion.v1_id = data["version_id"]

    def test_ingest_v2(self):
        """Ingest v2 — should create version 2, not destroy v1."""
        with open(PDF_V2_PATH, "rb") as f:
            response = client.post(
                "/api/documents/ingest",
                files={"file": ("ct200_manual_v2.pdf", f, "application/pdf")},
                data={"document_name": "CT-200 E2E Test"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["version_number"] == 2
        TestDocumentIngestion.v2_id = data["version_id"]

    def test_list_versions(self):
        """Both versions should exist."""
        response = client.get(f"/api/documents/{TestDocumentIngestion.doc_id}/versions")
        assert response.status_code == 200
        versions = response.json()
        assert len(versions) == 2
        assert versions[0]["version_number"] == 1
        assert versions[1]["version_number"] == 2

    def test_duplicate_ingestion_blocked(self):
        """Re-ingesting the same exact file should return duplicate status."""
        with open(PDF_V1_PATH, "rb") as f:
            response = client.post(
                "/api/documents/ingest",
                files={"file": ("ct200_manual.pdf", f, "application/pdf")},
                data={"document_name": "CT-200 E2E Test"},
            )
        assert response.status_code == 200
        assert response.json()["status"] == "duplicate"


class TestBrowseAPI:
    """Tests for tree browsing and node detail."""

    def test_get_tree_v1(self):
        response = client.get(
            f"/api/documents/{TestDocumentIngestion.doc_id}/tree?version=1"
        )
        assert response.status_code == 200
        tree = response.json()
        assert len(tree["sections"]) == 8
        TestBrowseAPI.v1_node_id = tree["sections"][0]["id"]

    def test_get_tree_latest(self):
        """Default to latest version."""
        response = client.get(
            f"/api/documents/{TestDocumentIngestion.doc_id}/tree"
        )
        assert response.status_code == 200
        tree = response.json()
        assert tree["version_number"] == 2

    def test_get_node_detail(self):
        response = client.get(f"/api/nodes/{TestBrowseAPI.v1_node_id}")
        assert response.status_code == 200
        node = response.json()
        assert node["heading"] is not None
        assert node["content_hash"] is not None
        assert "children" in node

    def test_node_not_found(self):
        response = client.get("/api/nodes/nonexistent-id")
        assert response.status_code == 404


class TestSearchAPI:
    """Tests for search functionality."""

    def test_search_by_heading(self):
        response = client.get("/api/search?q=Overpressure")
        assert response.status_code == 200
        results = response.json()
        assert results["total"] > 0

    def test_search_by_body_text(self):
        response = client.get("/api/search?q=oscillometric")
        assert response.status_code == 200
        results = response.json()
        assert results["total"] > 0

    def test_search_no_results(self):
        response = client.get("/api/search?q=xyznonexistent123")
        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestSelectionAPI:
    """Tests for version-pinned selections."""

    def test_create_selection(self):
        # Get a node from v1
        tree_resp = client.get(
            f"/api/documents/{TestDocumentIngestion.doc_id}/tree?version=1"
        )
        sections = tree_resp.json()["sections"]
        version_id = tree_resp.json()["version_id"]
        node_id = sections[3]["id"]  # Section 4

        response = client.post("/api/selections", json={
            "name": "Safety Test Selection",
            "items": [{"node_id": node_id, "version_id": version_id}],
        })
        assert response.status_code == 200
        sel = response.json()
        assert sel["name"] == "Safety Test Selection"
        assert len(sel["items"]) == 1
        assert sel["items"][0]["content_hash_at_selection"] is not None
        TestSelectionAPI.selection_id = sel["id"]

    def test_get_selection(self):
        response = client.get(f"/api/selections/{TestSelectionAPI.selection_id}")
        assert response.status_code == 200
        sel = response.json()
        assert sel["name"] == "Safety Test Selection"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
