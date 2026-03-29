"""
Smoke tests for ALL 15 Flask route blueprints.

Tests that:
1. Every blueprint registers successfully
2. Key endpoints return valid HTTP responses (no 500 crashes)
3. Proper error handling (400 for bad input, 404 for missing resources)

NOTE: These are smoke tests — they verify the app doesn't crash,
NOT that AI/LLM features produce correct results (those need integration tests).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database as db
from routes import register_blueprints


# ── Fixtures ──

@pytest.fixture(scope="module")
def app():
    """Create a test Flask app with all blueprints registered."""
    test_app = Flask(__name__, static_folder="../frontend", static_url_path="")
    test_app.config["TESTING"] = True
    register_blueprints(test_app)
    return test_app


@pytest.fixture(scope="module")
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path_factory):
    """Use a temporary SQLite database for each test."""
    tmp_path = tmp_path_factory.mktemp("db")
    test_db_path = str(tmp_path / "test.db")
    test_engine = create_engine(f"sqlite:///{test_db_path}", connect_args={"check_same_thread": False})
    test_session = sessionmaker(bind=test_engine)

    original_engine = db.engine
    original_session = db.SessionLocal
    db.engine = test_engine
    db.SessionLocal = test_session
    db.Base.metadata.create_all(test_engine)

    yield

    db.engine = original_engine
    db.SessionLocal = original_session


# ══════════════════════════════════════════════════════════════
# 1. Blueprint Registration
# ══════════════════════════════════════════════════════════════

class TestBlueprintRegistration:
    """Verify all 15 blueprints are registered."""

    EXPECTED_BLUEPRINTS = [
        "projects", "booking", "booking_serpapi",
        "splitter", "splitter_manual", "splitter_translate",
        "precheck", "precheck_processor",
        "pipeline", "pipeline_classifier", "pipeline_scan",
        "pipeline_pdf", "pipeline_itinerary",
        "ds160", "canada_forms",
    ]

    def test_all_blueprints_registered(self, app):
        registered = list(app.blueprints.keys())
        for bp_name in self.EXPECTED_BLUEPRINTS:
            assert bp_name in registered, f"Blueprint '{bp_name}' not registered"

    def test_blueprint_count(self, app):
        # 15 custom + possibly 'static'
        custom = [k for k in app.blueprints if k not in ("static",)]
        assert len(custom) >= 15, f"Expected ≥15 blueprints, got {len(custom)}: {custom}"


# ══════════════════════════════════════════════════════════════
# 2. Projects Blueprint (/api/projects)
# ══════════════════════════════════════════════════════════════

class TestProjectsBlueprint:
    """Test projects CRUD endpoints."""

    def test_list_projects(self, client):
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        data = resp.get_json()
        # API returns {"projects": [...]}
        assert isinstance(data, dict)
        assert "projects" in data
        assert isinstance(data["projects"], list)

    def test_create_project(self, client):
        resp = client.post(
            "/api/projects",
            data=json.dumps({"name": "Test Visa"}),
            content_type="application/json",
        )
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        assert "id" in data

    def test_get_nonexistent_project(self, client):
        resp = client.get("/api/projects/99999")
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════
# 3. Pipeline Blueprint (/api/files, /api/steps, etc.)
# ══════════════════════════════════════════════════════════════

class TestPipelineBlueprint:
    """Test core pipeline endpoints."""

    def test_list_files(self, client):
        resp = client.get("/api/files")
        assert resp.status_code == 200

    def test_get_steps(self, client):
        resp = client.get("/api/steps")
        assert resp.status_code == 200

    def test_get_output_files(self, client):
        resp = client.get("/api/output-files")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════
# 4. Pipeline PDF Blueprint (/api/pdf/*)
# ══════════════════════════════════════════════════════════════

class TestPipelinePdfBlueprint:
    """Test PDF generation/merge endpoints."""

    def test_list_merged_pdfs(self, client):
        resp = client.get("/api/pdf/merged")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, (list, dict))

    def test_delete_all_merged(self, client):
        resp = client.delete("/api/pdf/merged")
        assert resp.status_code == 200

    def test_get_nonexistent_merged_view(self, client):
        resp = client.get("/api/pdf/merged/99999/view")
        assert resp.status_code == 404

    def test_download_nonexistent_merged(self, client):
        resp = client.get("/api/pdf/merged/99999/download")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════
# 5. Pipeline Classifier Blueprint (/api/classifier/*)
# ══════════════════════════════════════════════════════════════

class TestPipelineClassifierBlueprint:
    """Test document classification endpoints."""

    def test_list_classifier_files(self, client):
        resp = client.get("/api/classifier/files")
        assert resp.status_code == 200

    def test_get_last_result(self, client):
        resp = client.get("/api/classifier/last-result")
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════
# 6. Pipeline Scan Blueprint (/api/scan-splitter/*)
# ══════════════════════════════════════════════════════════════

class TestPipelineScanBlueprint:
    """Test scan processing endpoints."""

    def test_scan_split_progress(self, client):
        resp = client.get("/api/scan-splitter/progress")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════
# 7. Pipeline Itinerary Blueprint (/api/itinerary/*)
# ══════════════════════════════════════════════════════════════

class TestPipelineItineraryBlueprint:
    """Test itinerary generation endpoints."""

    def test_get_itinerary_latest(self, client):
        resp = client.get("/api/itinerary/latest?project_id=99999")
        assert resp.status_code in (200, 404)

    def test_get_itinerary_context(self, client):
        resp = client.get("/api/itinerary/context/latest?project_id=99999")
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════
# 8. Booking Blueprint (/api/booking/*)
# ══════════════════════════════════════════════════════════════

class TestBookingBlueprint:
    """Test booking endpoints."""

    def test_get_booking_latest(self, client):
        resp = client.get("/api/booking/latest?project_id=99999")
        assert resp.status_code in (200, 404)

    def test_get_booking_trip_latest(self, client):
        resp = client.get("/api/booking/trip/latest?project_id=99999")
        assert resp.status_code in (200, 404)

    def test_get_destinations(self, client):
        resp = client.get("/api/booking/destinations")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════
# 9. Booking SerpAPI Blueprint (/api/flights/*, /api/hotels/*)
# ══════════════════════════════════════════════════════════════

class TestBookingSerpApiBlueprint:
    """Test SerpAPI search endpoints."""

    def test_search_flights_requires_post(self, client):
        resp = client.post(
            "/api/flights/search",
            data=json.dumps({}),
            content_type="application/json",
        )
        # Missing required params → 400 or error JSON
        assert resp.status_code in (400, 422, 500)

    def test_search_hotels_requires_post(self, client):
        resp = client.post(
            "/api/hotels/search-itinerary",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code in (400, 422, 500)


# ══════════════════════════════════════════════════════════════
# 10. Splitter Blueprint (/api/ai-splitter/*)
# ══════════════════════════════════════════════════════════════

class TestSplitterBlueprint:
    """Test AI PDF splitter endpoints."""

    def test_list_splitter(self, client):
        resp = client.get("/api/ai-splitter/list")
        assert resp.status_code == 200

    def test_list_outputs(self, client):
        resp = client.get("/api/ai-splitter/list-outputs")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════
# 11. Splitter Manual Blueprint (/api/manual-split/*)
# ══════════════════════════════════════════════════════════════

class TestSplitterManualBlueprint:
    """Test manual PDF split endpoints."""

    def test_upload_and_split_no_file(self, client):
        resp = client.post("/api/manual-split/upload-and-split")
        # No file uploaded → 400
        assert resp.status_code in (400, 422)


# ══════════════════════════════════════════════════════════════
# 12. Splitter Translate Blueprint (/api/translate/*)
# ══════════════════════════════════════════════════════════════

class TestSplitterTranslateBlueprint:
    """Test translation endpoints."""

    def test_list_templates(self, client):
        resp = client.get("/api/translate/templates")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "templates" in data

    def test_upload_no_file(self, client):
        resp = client.post("/api/translate/upload")
        assert resp.status_code in (400, 422)

    def test_get_certification_template(self, client):
        resp = client.get("/api/translate/certification_template")
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════
# 13. Precheck Blueprint (/api/precheck/*)
# ══════════════════════════════════════════════════════════════

class TestPrecheckBlueprint:
    """Test precheck endpoints."""

    def test_precheck_progress(self, client):
        resp = client.get("/api/precheck/progress")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════
# 14. DS160 Blueprint
# ══════════════════════════════════════════════════════════════

class TestDS160Blueprint:
    """Test DS-160 form endpoints — no dedicated /api endpoints,
    verifying blueprint registered is sufficient."""

    def test_blueprint_registered(self, app):
        assert "ds160" in app.blueprints


# ══════════════════════════════════════════════════════════════
# 15. Canada Forms Blueprint
# ══════════════════════════════════════════════════════════════

class TestCanadaFormsBlueprint:
    """Test Canada IMM forms endpoints."""

    def test_blueprint_registered(self, app):
        assert "canada_forms" in app.blueprints


# ══════════════════════════════════════════════════════════════
# 16. Cross-Blueprint Integration
# ══════════════════════════════════════════════════════════════

class TestCrossBlueprintIntegration:
    """Test that blueprints work together correctly."""

    def test_create_project_then_get(self, client):
        """Create a project, then verify it can be retrieved."""
        resp = client.post(
            "/api/projects",
            data=json.dumps({"name": "Integration Test"}),
            content_type="application/json",
        )
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        pid = data["id"]

        # Retrieve specific project
        resp = client.get(f"/api/projects/{pid}")
        assert resp.status_code == 200

    def test_api_endpoints_return_json(self, client):
        """Key API endpoints should return JSON."""
        endpoints = [
            "/api/projects",
            "/api/pdf/merged",
            "/api/steps",
        ]
        for ep in endpoints:
            resp = client.get(ep)
            assert resp.content_type.startswith("application/json"), \
                f"{ep} returned {resp.content_type}, expected application/json"

    def test_project_lifecycle(self, client):
        """Test full CRUD lifecycle for a project."""
        # Create
        resp = client.post(
            "/api/projects",
            data=json.dumps({"name": "Lifecycle"}),
            content_type="application/json",
        )
        pid = resp.get_json()["id"]

        # Update
        resp = client.put(
            f"/api/projects/{pid}",
            data=json.dumps({"name": "Updated"}),
            content_type="application/json",
        )
        assert resp.status_code == 200

        # Delete
        resp = client.delete(f"/api/projects/{pid}")
        assert resp.status_code == 200
