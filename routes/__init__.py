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
    from routes.pipeline import pipeline_bp
    from routes.ds160 import ds160_bp
    from routes.canada_forms import canada_forms_bp
    app.register_blueprint(projects_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(splitter_bp)
    app.register_blueprint(precheck_bp)
    app.register_blueprint(pipeline_bp)
    app.register_blueprint(ds160_bp)
    app.register_blueprint(canada_forms_bp)
