"""
Database module using SQLAlchemy ORM.
SQLite for development, easily switchable to PostgreSQL for cloud deployment.
"""

import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text,
    create_engine, desc, func
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "visa_app.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# ==================== MODELS ====================

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    input_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    trip_infos = relationship("TripInfo", back_populates="project", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="project", cascade="all, delete-orphan")
    itineraries = relationship("Itinerary", back_populates="project", cascade="all, delete-orphan")
    letter_states = relationship("LetterState", back_populates="project", cascade="all, delete-orphan")


class TripInfo(Base):
    __tablename__ = "trip_infos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    data = Column(Text, nullable=False)  # JSON blob
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=func.now())

    project = relationship("Project", back_populates="trip_infos")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    booking_data = Column(Text, nullable=False)  # JSON: AI selections + reasoning
    hotel_htmls = Column(Text, nullable=False)   # JSON array of HTML strings
    flight_html = Column(Text, nullable=False)
    reasoning = Column(Text, default="")
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=func.now())

    project = relationship("Project", back_populates="bookings")


class Itinerary(Base):
    __tablename__ = "itineraries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    context = Column(Text, nullable=False)  # JSON: participants, dates, purpose
    html_content = Column(Text, default="")
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=func.now())

    project = relationship("Project", back_populates="itineraries")


class LetterState(Base):
    __tablename__ = "letter_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    files_data = Column(Text, default="[]")      # JSON: ingested files
    summary_profile = Column(Text, default="")
    writer_context = Column(Text, default="")
    letter_content = Column(Text, default="")
    step_ingest = Column(Boolean, default=False)
    step_summary = Column(Boolean, default=False)
    step_writer = Column(Boolean, default=False)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=func.now())

    project = relationship("Project", back_populates="letter_states")


# ==================== INIT ====================

def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)


def get_session():
    """Get a new database session."""
    return SessionLocal()


# ==================== PROJECTS ====================

def create_project(name: str) -> Dict[str, Any]:
    session = get_session()
    try:
        project = Project(name=name)
        session.add(project)
        session.commit()
        session.refresh(project)
        return _project_to_dict(project)
    finally:
        session.close()


def list_projects() -> List[Dict[str, Any]]:
    session = get_session()
    try:
        projects = session.query(Project).order_by(desc(Project.updated_at)).all()
        return [_project_to_dict(p) for p in projects]
    finally:
        session.close()


def get_project(project_id: int) -> Optional[Dict[str, Any]]:
    session = get_session()
    try:
        project = session.query(Project).filter_by(id=project_id).first()
        return _project_to_dict(project) if project else None
    finally:
        session.close()


def update_project(project_id: int, **kwargs) -> Optional[Dict[str, Any]]:
    session = get_session()
    try:
        project = session.query(Project).filter_by(id=project_id).first()
        if not project:
            return None
        for key, value in kwargs.items():
            if hasattr(project, key):
                setattr(project, key, value)
        project.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(project)
        return _project_to_dict(project)
    finally:
        session.close()


def delete_project(project_id: int) -> bool:
    session = get_session()
    try:
        project = session.query(Project).filter_by(id=project_id).first()
        if not project:
            return False
        session.delete(project)
        session.commit()
        return True
    finally:
        session.close()


def _project_to_dict(p: Project) -> Dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "input_hash": p.input_hash,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


# ==================== TRIP INFO ====================

def save_trip_info(project_id: int, data: Dict) -> Dict[str, Any]:
    session = get_session()
    try:
        # Get current max version
        latest = session.query(TripInfo).filter_by(project_id=project_id) \
            .order_by(desc(TripInfo.version)).first()
        version = (latest.version + 1) if latest else 1

        trip = TripInfo(
            project_id=project_id,
            data=json.dumps(data, ensure_ascii=False),
            version=version,
        )
        session.add(trip)
        # Touch project updated_at
        project = session.query(Project).filter_by(id=project_id).first()
        if project:
            project.updated_at = datetime.utcnow()
        session.commit()
        return {"id": trip.id, "version": version, "data": data}
    finally:
        session.close()


def get_latest_trip_info(project_id: int) -> Optional[Dict[str, Any]]:
    session = get_session()
    try:
        trip = session.query(TripInfo).filter_by(project_id=project_id) \
            .order_by(desc(TripInfo.version)).first()
        if not trip:
            return None
        return {
            "id": trip.id,
            "version": trip.version,
            "data": json.loads(trip.data),
            "created_at": trip.created_at.isoformat() if trip.created_at else None,
        }
    finally:
        session.close()


# ==================== BOOKINGS ====================

def save_booking(project_id: int, booking_data: Dict, hotel_htmls: List[str],
                 flight_html: str, reasoning: str = "") -> Dict[str, Any]:
    session = get_session()
    try:
        # Delete previous bookings for this project (replace with new)
        session.query(Booking).filter_by(project_id=project_id).delete()

        booking = Booking(
            project_id=project_id,
            booking_data=json.dumps(booking_data, ensure_ascii=False),
            hotel_htmls=json.dumps(hotel_htmls, ensure_ascii=False),
            flight_html=flight_html,
            reasoning=reasoning,
            version=1,
        )
        session.add(booking)
        project = session.query(Project).filter_by(id=project_id).first()
        if project:
            project.updated_at = datetime.utcnow()
        session.commit()
        return {"id": booking.id, "version": 1}
    finally:
        session.close()


def get_latest_booking(project_id: int) -> Optional[Dict[str, Any]]:
    session = get_session()
    try:
        booking = session.query(Booking).filter_by(project_id=project_id) \
            .order_by(desc(Booking.version)).first()
        if not booking:
            return None
        return {
            "id": booking.id,
            "version": booking.version,
            "booking_data": json.loads(booking.booking_data),
            "hotel_htmls": json.loads(booking.hotel_htmls),
            "flight_html": booking.flight_html,
            "reasoning": booking.reasoning,
            "created_at": booking.created_at.isoformat() if booking.created_at else None,
        }
    finally:
        session.close()


# ==================== ITINERARIES ====================

def save_itinerary_context(project_id: int, context: Dict) -> Dict[str, Any]:
    """Save or update itinerary context (without HTML yet)."""
    session = get_session()
    try:
        latest = session.query(Itinerary).filter_by(project_id=project_id) \
            .order_by(desc(Itinerary.version)).first()

        if latest and not latest.html_content:
            # Update existing context-only record
            latest.context = json.dumps(context, ensure_ascii=False)
            session.commit()
            return {"id": latest.id, "version": latest.version}

        version = (latest.version + 1) if latest else 1
        itinerary = Itinerary(
            project_id=project_id,
            context=json.dumps(context, ensure_ascii=False),
            version=version,
        )
        session.add(itinerary)
        project = session.query(Project).filter_by(id=project_id).first()
        if project:
            project.updated_at = datetime.utcnow()
        session.commit()
        return {"id": itinerary.id, "version": version}
    finally:
        session.close()


def save_itinerary_html(project_id: int, context: Dict, html_content: str) -> Dict[str, Any]:
    """Save a complete itinerary (context + HTML)."""
    session = get_session()
    try:
        latest = session.query(Itinerary).filter_by(project_id=project_id) \
            .order_by(desc(Itinerary.version)).first()
        version = (latest.version + 1) if latest else 1

        itinerary = Itinerary(
            project_id=project_id,
            context=json.dumps(context, ensure_ascii=False),
            html_content=html_content,
            version=version,
        )
        session.add(itinerary)
        project = session.query(Project).filter_by(id=project_id).first()
        if project:
            project.updated_at = datetime.utcnow()
        session.commit()
        return {"id": itinerary.id, "version": version}
    finally:
        session.close()


def get_latest_itinerary(project_id: int) -> Optional[Dict[str, Any]]:
    session = get_session()
    try:
        itinerary = session.query(Itinerary).filter_by(project_id=project_id) \
            .order_by(desc(Itinerary.version)).first()
        if not itinerary:
            return None
        return {
            "id": itinerary.id,
            "version": itinerary.version,
            "context": json.loads(itinerary.context) if itinerary.context else {},
            "html_content": itinerary.html_content or "",
            "created_at": itinerary.created_at.isoformat() if itinerary.created_at else None,
        }
    finally:
        session.close()


def get_latest_itinerary_context(project_id: int) -> Optional[Dict[str, Any]]:
    """Get the latest itinerary context (from any version)."""
    session = get_session()
    try:
        itinerary = session.query(Itinerary).filter_by(project_id=project_id) \
            .order_by(desc(Itinerary.version)).first()
        if not itinerary or not itinerary.context:
            return None
        return json.loads(itinerary.context)
    finally:
        session.close()


# ==================== LETTER STATE ====================

def save_letter_state(project_id: int, **kwargs) -> Dict[str, Any]:
    """Create or update letter state for a project."""
    session = get_session()
    try:
        latest = session.query(LetterState).filter_by(project_id=project_id) \
            .order_by(desc(LetterState.version)).first()

        if latest:
            # Update existing record
            for key, value in kwargs.items():
                if hasattr(latest, key):
                    if key == "files_data" and isinstance(value, (list, dict)):
                        value = json.dumps(value, ensure_ascii=False)
                    setattr(latest, key, value)
            session.commit()
            session.refresh(latest)
            return _letter_state_to_dict(latest)
        else:
            # Create new
            files_data = kwargs.get("files_data", [])
            if isinstance(files_data, (list, dict)):
                files_data = json.dumps(files_data, ensure_ascii=False)
            state = LetterState(
                project_id=project_id,
                files_data=files_data,
                summary_profile=kwargs.get("summary_profile", ""),
                writer_context=kwargs.get("writer_context", ""),
                letter_content=kwargs.get("letter_content", ""),
                step_ingest=kwargs.get("step_ingest", False),
                step_summary=kwargs.get("step_summary", False),
                step_writer=kwargs.get("step_writer", False),
            )
            session.add(state)
            project = session.query(Project).filter_by(id=project_id).first()
            if project:
                project.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(state)
            return _letter_state_to_dict(state)
    finally:
        session.close()


def get_latest_letter_state(project_id: int) -> Optional[Dict[str, Any]]:
    session = get_session()
    try:
        state = session.query(LetterState).filter_by(project_id=project_id) \
            .order_by(desc(LetterState.version)).first()
        if not state:
            return None
        return _letter_state_to_dict(state)
    finally:
        session.close()


def reset_letter_downstream(project_id: int, from_step: str):
    """Reset downstream steps when a step is re-run."""
    session = get_session()
    try:
        state = session.query(LetterState).filter_by(project_id=project_id) \
            .order_by(desc(LetterState.version)).first()
        if not state:
            return
        steps = ["ingest", "summary", "writer"]
        if from_step not in steps:
            return
        idx = steps.index(from_step)
        for s in steps[idx + 1:]:
            setattr(state, f"step_{s}", False)
        if "summary" in steps[idx + 1:]:
            state.summary_profile = ""
        if "writer" in steps[idx + 1:]:
            state.letter_content = ""
        session.commit()
    finally:
        session.close()


def _letter_state_to_dict(state: LetterState) -> Dict[str, Any]:
    files_data = state.files_data or "[]"
    try:
        files = json.loads(files_data)
    except (json.JSONDecodeError, TypeError):
        files = []
    return {
        "id": state.id,
        "project_id": state.project_id,
        "version": state.version,
        "files_data": files,
        "summary_profile": state.summary_profile or "",
        "writer_context": state.writer_context or "",
        "letter_content": state.letter_content or "",
        "step_ingest": bool(state.step_ingest),
        "step_summary": bool(state.step_summary),
        "step_writer": bool(state.step_writer),
        "created_at": state.created_at.isoformat() if state.created_at else None,
    }


# ==================== INPUT HASHING ====================

def compute_input_hash(input_dir: str) -> str:
    """Compute MD5 hash of all files in input directory for change detection."""
    if not os.path.isdir(input_dir):
        return ""
    hasher = hashlib.md5()
    for root, _, filenames in os.walk(input_dir):
        for fname in sorted(filenames):
            fpath = os.path.join(root, fname)
            try:
                hasher.update(fname.encode("utf-8"))
                hasher.update(str(os.path.getsize(fpath)).encode("utf-8"))
            except OSError:
                continue
    return hasher.hexdigest()


# Initialize DB on import
init_db()
