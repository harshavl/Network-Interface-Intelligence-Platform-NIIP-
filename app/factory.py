"""
Application factory.

Builds the Flask app with all middleware, error handlers, and the
analysis service wired in. Importable as `app:create_app` for gunicorn.
"""

from __future__ import annotations

import traceback

from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.api import create_api_blueprint
from app.core import (
    NIIPException,
    Settings,
    configure_logging,
    get_logger,
    get_settings,
)
from app.services import AnalysisService

__version__ = "1.0.0"


def create_app(settings: Settings | None = None) -> Flask:
    """Construct and configure the Flask application."""
    settings = settings or get_settings()
    configure_logging(settings)
    logger = get_logger(__name__)

    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.secret_key
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_bytes
    app.config["MAX_UPLOAD_BYTES"] = settings.max_upload_bytes
    app.config["RESTX_MASK_SWAGGER"] = False
    app.config["JSON_SORT_KEYS"] = False
    app.config["PROPAGATE_EXCEPTIONS"] = False

    # CORS — open in dev, restricted in prod (configure via env)
    origins = (
        settings.cors_origins.split(",") if settings.cors_origins != "*" else "*"
    )
    CORS(app, resources={r"/api/*": {"origins": origins}})

    # Rate limiting
    Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[settings.api_rate_limit],
        storage_uri="memory://",
    )

    # Wire services
    app.extensions["analysis_service"] = AnalysisService(settings)
    app.extensions["settings"] = settings

    # Register API blueprint
    app.register_blueprint(create_api_blueprint(settings.api_prefix))

    # Root index
    @app.route("/")
    def index():
        return jsonify(
            {
                "service": "Network Interface Intelligence Platform",
                "version": __version__,
                "docs": f"{settings.api_prefix}/docs",
                "health": f"{settings.api_prefix}/health",
            }
        )

    _register_error_handlers(app, settings)

    logger.info(
        "app_initialized",
        env=settings.flask_env,
        api_prefix=settings.api_prefix,
        log_level=settings.log_level,
    )
    return app


def _register_error_handlers(app: Flask, settings: Settings) -> None:
    logger = get_logger(__name__)

    @app.errorhandler(NIIPException)
    def handle_niip_exception(exc: NIIPException):
        logger.warning(
            "niip_exception",
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        )
        return jsonify(exc.to_dict()), exc.status_code

    @app.errorhandler(404)
    def handle_404(_):
        return (
            jsonify(
                {
                    "error": "NOT_FOUND",
                    "message": "The requested resource was not found",
                    "details": {},
                }
            ),
            404,
        )

    @app.errorhandler(405)
    def handle_405(_):
        return (
            jsonify(
                {
                    "error": "METHOD_NOT_ALLOWED",
                    "message": "Method not allowed for this endpoint",
                    "details": {},
                }
            ),
            405,
        )

    @app.errorhandler(413)
    def handle_413(_):
        return (
            jsonify(
                {
                    "error": "FILE_TOO_LARGE",
                    "message": (
                        f"Request body exceeds {settings.max_upload_mb} MB limit"
                    ),
                    "details": {},
                }
            ),
            413,
        )

    @app.errorhandler(Exception)
    def handle_uncaught(exc: Exception):
        logger.exception("uncaught_exception", error=str(exc))
        details = {} if settings.is_production else {"trace": traceback.format_exc()}
        return (
            jsonify(
                {
                    "error": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "details": details,
                }
            ),
            500,
        )
