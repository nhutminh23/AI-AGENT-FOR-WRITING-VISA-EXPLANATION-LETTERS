"""
Blueprint registration.
Import and register all route blueprints here.
"""
from __future__ import annotations

from flask import Flask


def register_blueprints(app: Flask) -> None:
    """Register all Flask Blueprints with the app."""
    # Blueprints will be added here as we extract them from server.py.
    # Each blueprint handles one feature domain.
    #
    # Example:
    #   from routes.translate import translate_bp
    #   app.register_blueprint(translate_bp)
    pass
