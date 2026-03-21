"""Tests for database.py — CRUD operations using in-memory SQLite."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# We need to monkey-patch the database module to use in-memory DB for tests
import database as db


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    """Use a temporary SQLite database for each test."""
    test_db_path = str(tmp_path / "test.db")
    test_engine = create_engine(f"sqlite:///{test_db_path}", connect_args={"check_same_thread": False})
    test_session = sessionmaker(bind=test_engine)

    # Replace the module's engine and session
    original_engine = db.engine
    original_session = db.SessionLocal
    db.engine = test_engine
    db.SessionLocal = test_session
    db.Base.metadata.create_all(test_engine)

    yield

    # Restore originals
    db.engine = original_engine
    db.SessionLocal = original_session


class TestProjectCRUD:
    """Test Project create/read/update/delete."""

    def test_create_project(self):
        result = db.create_project("Test Visa Application")
        assert result["id"] is not None
        assert result["name"] == "Test Visa Application"
        assert result["created_at"] is not None

    def test_list_projects_empty(self):
        projects = db.list_projects()
        assert projects == []

    def test_list_projects_returns_created(self):
        db.create_project("Project 1")
        db.create_project("Project 2")
        projects = db.list_projects()
        assert len(projects) == 2

    def test_get_project_by_id(self):
        created = db.create_project("Get Me")
        result = db.get_project(created["id"])
        assert result is not None
        assert result["name"] == "Get Me"

    def test_get_nonexistent_project(self):
        result = db.get_project(999)
        assert result is None

    def test_update_project_name(self):
        created = db.create_project("Old Name")
        updated = db.update_project(created["id"], name="New Name")
        assert updated["name"] == "New Name"

    def test_update_nonexistent_project(self):
        result = db.update_project(999, name="Nothing")
        assert result is None

    def test_delete_project(self):
        created = db.create_project("Delete Me")
        assert db.delete_project(created["id"]) is True
        assert db.get_project(created["id"]) is None

    def test_delete_nonexistent_project(self):
        assert db.delete_project(999) is False


class TestTripInfo:
    """Test trip info save/retrieve operations."""

    def test_save_and_get_trip_info(self):
        project = db.create_project("Trip Test")
        data = {"destination": "Japan", "dates": "2026-04-01"}
        db.save_trip_info(project["id"], data)

        result = db.get_latest_trip_info(project["id"])
        assert result is not None
        assert result["data"]["destination"] == "Japan"
        assert result["version"] == 1

    def test_versioning(self):
        project = db.create_project("Versioning Test")
        db.save_trip_info(project["id"], {"v": 1})
        db.save_trip_info(project["id"], {"v": 2})

        result = db.get_latest_trip_info(project["id"])
        assert result["version"] == 2
        assert result["data"]["v"] == 2

    def test_get_trip_info_nonexistent(self):
        result = db.get_latest_trip_info(999)
        assert result is None


class TestBooking:
    """Test booking save/retrieve operations."""

    def test_save_and_get_booking(self):
        project = db.create_project("Booking Test")
        booking_data = {"hotel": "Marriott", "city": "Tokyo"}
        hotel_htmls = ["<div>Hotel 1</div>", "<div>Hotel 2</div>"]
        flight_html = "<div>Flight VN123</div>"

        db.save_booking(project["id"], booking_data, hotel_htmls, flight_html, "AI reasoning")

        result = db.get_latest_booking(project["id"])
        assert result is not None
        assert result["booking_data"]["hotel"] == "Marriott"
        assert len(result["hotel_htmls"]) == 2
        assert "VN123" in result["flight_html"]
        assert result["reasoning"] == "AI reasoning"

    def test_save_booking_replaces_previous(self):
        project = db.create_project("Replace Test")
        db.save_booking(project["id"], {"v": 1}, ["h1"], "f1")
        db.save_booking(project["id"], {"v": 2}, ["h2"], "f2")

        result = db.get_latest_booking(project["id"])
        assert result["booking_data"]["v"] == 2

    def test_get_booking_nonexistent(self):
        result = db.get_latest_booking(999)
        assert result is None


class TestLetterState:
    """Test letter state save/retrieve operations."""

    def test_create_letter_state(self):
        project = db.create_project("Letter Test")
        result = db.save_letter_state(
            project["id"],
            summary_profile="Test profile",
            step_ingest=True,
        )
        assert result["summary_profile"] == "Test profile"
        assert result["step_ingest"] is True
        assert result["step_summary"] is False

    def test_update_letter_state(self):
        project = db.create_project("Update Letter")
        db.save_letter_state(project["id"], step_ingest=True)
        result = db.save_letter_state(project["id"], step_summary=True, summary_profile="Done")

        assert result["step_ingest"] is True  # preserved
        assert result["step_summary"] is True  # updated
        assert result["summary_profile"] == "Done"

    def test_get_letter_state(self):
        project = db.create_project("Get Letter")
        db.save_letter_state(project["id"], letter_content="Dear Sir...")
        result = db.get_latest_letter_state(project["id"])
        assert result["letter_content"] == "Dear Sir..."

    def test_get_letter_state_nonexistent(self):
        result = db.get_latest_letter_state(999)
        assert result is None


class TestResetDownstream:
    """Test resetting downstream letter steps."""

    def test_reset_from_ingest(self):
        project = db.create_project("Reset Test")
        db.save_letter_state(
            project["id"],
            step_ingest=True,
            step_summary=True,
            step_writer=True,
            summary_profile="profile",
            letter_content="letter",
        )
        db.reset_letter_downstream(project["id"], "ingest")

        result = db.get_latest_letter_state(project["id"])
        assert result["step_ingest"] is True  # not reset
        assert result["step_summary"] is False  # reset
        assert result["step_writer"] is False  # reset
        assert result["summary_profile"] == ""  # cleared
        assert result["letter_content"] == ""  # cleared

    def test_reset_from_summary(self):
        project = db.create_project("Reset Summary")
        db.save_letter_state(
            project["id"],
            step_ingest=True,
            step_summary=True,
            step_writer=True,
            letter_content="letter",
        )
        db.reset_letter_downstream(project["id"], "summary")

        result = db.get_latest_letter_state(project["id"])
        assert result["step_summary"] is True  # not reset
        assert result["step_writer"] is False  # reset
        assert result["letter_content"] == ""  # cleared


class TestClearProjectData:
    """Test clearing all project data while keeping the project."""

    def test_clear_removes_all_data(self):
        project = db.create_project("Clear Test")
        pid = project["id"]

        # Add data
        db.save_trip_info(pid, {"test": True})
        db.save_booking(pid, {"hotel": "test"}, ["<h>"], "<f>")
        db.save_letter_state(pid, step_ingest=True)

        # Clear
        db.clear_project_data(pid)

        # Verify project still exists
        assert db.get_project(pid) is not None

        # Verify all data cleared
        assert db.get_latest_trip_info(pid) is None
        assert db.get_latest_booking(pid) is None
        assert db.get_latest_letter_state(pid) is None


class TestInputHash:
    """Test input directory hashing for change detection."""

    def test_nonexistent_dir_returns_empty(self):
        result = db.compute_input_hash("/nonexistent/path")
        assert result == ""

    def test_empty_dir(self, tmp_path):
        result = db.compute_input_hash(str(tmp_path))
        assert isinstance(result, str)
        assert len(result) == 32  # MD5 hex digest

    def test_same_files_same_hash(self, tmp_path):
        (tmp_path / "file.txt").write_text("hello")
        hash1 = db.compute_input_hash(str(tmp_path))
        hash2 = db.compute_input_hash(str(tmp_path))
        assert hash1 == hash2

    def test_different_files_different_hash(self, tmp_path):
        (tmp_path / "file.txt").write_text("hello")
        hash1 = db.compute_input_hash(str(tmp_path))
        (tmp_path / "file2.txt").write_text("world")
        hash2 = db.compute_input_hash(str(tmp_path))
        assert hash1 != hash2
