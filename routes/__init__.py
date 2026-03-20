"""
Blueprint registration.
Import and register all route blueprints here.
"""
from __future__ import annotations

from flask import Flask


def register_blueprints(app: Flask) -> None:
    """Register all Flask Blueprints with the app."""
    from routes.projects import projects_bp
    from routes.booking import booking_bp
    from routes.splitter import splitter_bp
    from routes.precheck import precheck_bp
    app.register_blueprint(projects_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(splitter_bp)
    app.register_blueprint(precheck_bp)
