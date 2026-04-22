"""
Analysis API endpoints.

Three entry points:

- POST /upload    — multipart CSV file upload
- POST /analyze   — direct JSON payload (for service-to-service use)
- POST /summary   — same as /upload but returns only the aggregate summary
"""

from __future__ import annotations

import io

from flask import current_app, request
from flask_restx import Namespace, Resource, fields
from pydantic import ValidationError as PydanticValidationError
from werkzeug.datastructures import FileStorage

from app.core import (
    DataIngestionException,
    FileTooLargeException,
    NIIPException,
    ValidationException,
    get_logger,
)
from app.models import InterfaceMetric
from app.schemas import AnalysisRequestSchema
from app.services import AnalysisService
from app.utils import CSVLoader, serialize_report

logger = get_logger(__name__)

ns = Namespace("analysis", description="Network interface analysis operations")

# --- Swagger models ---

interface_metric_model = ns.model(
    "InterfaceMetric",
    {
        "device_name": fields.String(required=True, example="core-rtr-01"),
        "interface_name": fields.String(required=True, example="GigabitEthernet0/1"),
        "interface_description": fields.String(example="Uplink to ISP-A"),
        "in_utilization_percent": fields.Float(required=True, example=78.4),
        "out_utilization_percent": fields.Float(required=True, example=82.1),
        "in_errors_1h": fields.Integer(required=True, example=0),
        "out_errors_1h": fields.Integer(required=True, example=0),
        "in_discards_1h": fields.Integer(required=True, example=12),
        "out_discards_1h": fields.Integer(required=True, example=8),
    },
)

analyze_request_model = ns.model(
    "AnalyzeRequest",
    {
        "interfaces": fields.List(
            fields.Nested(interface_metric_model), required=True, min_items=1
        )
    },
)

# Multipart upload parser
upload_parser = ns.parser()
upload_parser.add_argument(
    "file",
    location="files",
    type=FileStorage,
    required=True,
    help="CSV file exported from LogicMonitor",
)


# ---------------- helpers ----------------

def _get_service() -> AnalysisService:
    """Pull the analysis service from the Flask app extensions."""
    return current_app.extensions["analysis_service"]


def _check_size(file: FileStorage) -> None:
    file.stream.seek(0, io.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    max_bytes = current_app.config["MAX_UPLOAD_BYTES"]
    if size > max_bytes:
        raise FileTooLargeException(
            f"File exceeds {max_bytes / (1024 * 1024):.0f} MB limit",
            details={"size_bytes": size, "max_bytes": max_bytes},
        )
    if size == 0:
        raise ValidationException("Uploaded file is empty")


# ---------------- endpoints ----------------

@ns.route("/upload")
class UploadAnalysis(Resource):
    """Analyze a CSV file uploaded via multipart/form-data."""

    @ns.expect(upload_parser)
    @ns.doc(
        responses={
            200: "Analysis succeeded",
            400: "Invalid request",
            413: "File too large",
            422: "CSV could not be parsed",
            500: "Internal server error",
        }
    )
    def post(self):
        """Run full analysis on an uploaded LogicMonitor CSV."""
        args = upload_parser.parse_args()
        file: FileStorage = args["file"]

        if not file or not file.filename:
            raise ValidationException("No file provided")

        if not file.filename.lower().endswith((".csv", ".txt")):
            raise ValidationException(
                "Only .csv files are accepted",
                details={"filename": file.filename},
            )

        _check_size(file)

        logger.info("upload_received", filename=file.filename)

        metrics = CSVLoader.load(file.stream)
        report = _get_service().analyze(metrics)
        return serialize_report(report), 200


@ns.route("/analyze")
class JsonAnalysis(Resource):
    """Analyze a JSON payload directly (no CSV)."""

    @ns.expect(analyze_request_model, validate=False)
    @ns.doc(
        responses={
            200: "Analysis succeeded",
            400: "Invalid request body",
            500: "Internal server error",
        }
    )
    def post(self):
        """Run full analysis on a JSON payload of interface metrics."""
        payload = request.get_json(silent=True)
        if payload is None:
            raise ValidationException("Request body must be valid JSON")

        try:
            req = AnalysisRequestSchema(**payload)
        except PydanticValidationError as exc:
            raise ValidationException(
                "Invalid request payload",
                details={"errors": exc.errors()},
            ) from exc

        metrics = [
            InterfaceMetric(
                device_name=i.device_name,
                interface_name=i.interface_name,
                interface_description=i.interface_description,
                in_utilization_percent=i.in_utilization_percent,
                out_utilization_percent=i.out_utilization_percent,
                in_errors_1h=i.in_errors_1h,
                out_errors_1h=i.out_errors_1h,
                in_discards_1h=i.in_discards_1h,
                out_discards_1h=i.out_discards_1h,
            )
            for i in req.interfaces
        ]

        report = _get_service().analyze(metrics)
        return serialize_report(report), 200


@ns.route("/summary")
class SummaryAnalysis(Resource):
    """Return only the aggregate summary — useful for dashboard tiles."""

    @ns.expect(upload_parser)
    @ns.doc(
        responses={
            200: "Analysis summary returned",
            400: "Invalid request",
            413: "File too large",
            422: "CSV could not be parsed",
        }
    )
    def post(self):
        """Run analysis on an uploaded CSV and return only the summary block."""
        args = upload_parser.parse_args()
        file: FileStorage = args["file"]

        if not file or not file.filename:
            raise ValidationException("No file provided")
        _check_size(file)

        metrics = CSVLoader.load(file.stream)
        report = _get_service().analyze(metrics)
        full = serialize_report(report)
        return {
            "analysis_timestamp": full["analysis_timestamp"],
            "summary": full["summary"],
        }, 200
