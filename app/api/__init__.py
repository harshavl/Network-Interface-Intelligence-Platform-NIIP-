"""Flask-RESTX API namespace registration."""

from flask import Blueprint
from flask_restx import Api

from app.api.analysis import ns as analysis_ns
from app.api.health import ns as health_ns


def create_api_blueprint(prefix: str = "/api/v1") -> Blueprint:
    """Create the API blueprint with all namespaces registered."""
    blueprint = Blueprint("api", __name__, url_prefix=prefix)

    api = Api(
        blueprint,
        version="1.0.0",
        title="Network Interface Intelligence Platform API",
        description=(
            "ML-powered anomaly detection, forecasting, root cause analysis, "
            "and health scoring for network interface telemetry."
        ),
        doc="/docs",
    )

    api.add_namespace(health_ns, path="/health")
    api.add_namespace(analysis_ns, path="/analysis")

    return blueprint


__all__ = ["create_api_blueprint"]
