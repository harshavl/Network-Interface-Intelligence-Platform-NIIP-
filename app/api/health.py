"""Health check endpoints — for load balancers, k8s probes, and CI."""

from datetime import datetime, timezone

from flask_restx import Namespace, Resource, fields

ns = Namespace("health", description="Liveness and readiness probes")

health_response = ns.model(
    "HealthResponse",
    {
        "status": fields.String(required=True, example="ok"),
        "service": fields.String(required=True, example="niip"),
        "version": fields.String(required=True, example="1.0.0"),
        "timestamp": fields.String(required=True),
    },
)


@ns.route("")
class HealthCheck(Resource):
    """Liveness probe."""

    @ns.marshal_with(health_response)
    def get(self):
        """Return service health status."""
        return {
            "status": "ok",
            "service": "niip",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
