"""
Blueprint registration.
Import and register all route blueprints here.
"""
from __future__ import annotations
import logging

from flask import Flask


def register_blueprints(app: Flask) -> None:
    """Register all Flask Blueprints with the app."""
    from routes.projects import projects_bp
    from routes.booking import booking_bp
    from routes.booking_serpapi import booking_serpapi_bp
    from routes.splitter import splitter_bp
    from routes.splitter_manual import splitter_manual_bp
    from routes.splitter_translate import splitter_translate_bp
    from routes.precheck import precheck_bp
    from routes.precheck_processor import precheck_processor_bp
    from routes.pipeline import pipeline_bp
    from routes.pipeline_classifier import pipeline_classifier_bp
    from routes.pipeline_scan import pipeline_scan_bp
    from routes.pipeline_pdf import pipeline_pdf_bp
    from routes.pipeline_itinerary import pipeline_itinerary_bp
    from routes.ds160 import ds160_bp
    from routes.canada_forms import canada_forms_bp
    from routes.australia_forms import australia_forms_bp
    from routes.insurance import insurance_bp

    from routes.letter_gen import letter_gen_bp
    app.register_blueprint(projects_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(booking_serpapi_bp)
    app.register_blueprint(splitter_bp)
    app.register_blueprint(splitter_manual_bp)
    app.register_blueprint(splitter_translate_bp)
    app.register_blueprint(precheck_bp)
    app.register_blueprint(precheck_processor_bp)
    app.register_blueprint(pipeline_bp)
    app.register_blueprint(pipeline_classifier_bp)
    app.register_blueprint(pipeline_scan_bp)
    app.register_blueprint(pipeline_pdf_bp)
    app.register_blueprint(pipeline_itinerary_bp)
    app.register_blueprint(ds160_bp)
    app.register_blueprint(canada_forms_bp)
    app.register_blueprint(australia_forms_bp)
    app.register_blueprint(insurance_bp)

    app.register_blueprint(letter_gen_bp)



