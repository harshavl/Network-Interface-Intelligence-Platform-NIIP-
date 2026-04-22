"""Domain-specific exceptions used throughout the application."""


class NIIPException(Exception):
    """Base exception for all NIIP errors."""

    status_code = 500
    error_code = "NIIP_ERROR"

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class ValidationException(NIIPException):
    """Raised when input data fails validation."""

    status_code = 400
    error_code = "VALIDATION_ERROR"


class DataIngestionException(NIIPException):
    """Raised when CSV ingestion or parsing fails."""

    status_code = 422
    error_code = "DATA_INGESTION_ERROR"


class MLEngineException(NIIPException):
    """Raised by ML engines on inference failures."""

    status_code = 500
    error_code = "ML_ENGINE_ERROR"


class FileTooLargeException(NIIPException):
    """Raised when uploaded file exceeds the configured size limit."""

    status_code = 413
    error_code = "FILE_TOO_LARGE"
