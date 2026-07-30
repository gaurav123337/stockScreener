"""Standardized API response models — consistent error/success shapes.

Every API endpoint returns one of these, ensuring the frontend always
gets a predictable JSON structure, never an HTML error page.
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Structured error information."""
    code: str
    message: str
    details: dict[str, Any] | None = None


class ApiError(BaseModel):
    """Top-level error response — always JSON, never HTML."""
    error: ErrorDetail

    @classmethod
    def make(
        cls,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> "ApiError":
        return cls(error=ErrorDetail(code=code, message=message, details=details))


class ApiResponse(BaseModel):
    """Generic success wrapper."""
    data: Any = None
    message: str | None = None
    warnings: list[str] | None = None


# --------------------------------------------------------------------------- #
# Common error codes (used across the API)
# --------------------------------------------------------------------------- #

class ErrorCodes:
    """Central registry of error codes."""
    # Auth
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID = "AUTH_INVALID"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    AUTH_FORBIDDEN = "AUTH_FORBIDDEN"
    USER_EXISTS = "USER_EXISTS"
    USER_NOT_FOUND = "USER_NOT_FOUND"

    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_FIELD = "MISSING_FIELD"

    # Data
    SYMBOL_NOT_FOUND = "SYMBOL_NOT_FOUND"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DATA_SOURCE_ERROR = "DATA_SOURCE_ERROR"
    DATA_TIMEOUT = "DATA_TIMEOUT"

    # Config
    UNKNOWN_SETTING = "UNKNOWN_SETTING"
    INVALID_SETTING = "INVALID_SETTING"

    # Broker
    BROKER_NOT_CONNECTED = "BROKER_NOT_CONNECTED"
    BROKER_ERROR = "BROKER_ERROR"

    # Knowledge
    INGESTION_ERROR = "INGESTION_ERROR"
    UNSUPPORTED_FILE = "UNSUPPORTED_FILE"

    # Server
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    REQUEST_TIMEOUT = "REQUEST_TIMEOUT"


# --------------------------------------------------------------------------- #
# Exception → JSON mapping
# --------------------------------------------------------------------------- #

class AppException(Exception):
    """Base application exception that carries a structured error."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details

    def to_response(self) -> dict[str, Any]:
        return ApiError.make(self.code, self.message, self.details).model_dump()


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found", details: dict | None = None):
        super().__init__(ErrorCodes.NOT_FOUND, message, 404, details)


class AuthError(AppException):
    def __init__(self, code: str = ErrorCodes.AUTH_REQUIRED, message: str = "Authentication required"):
        super().__init__(code, message, 401)


class ForbiddenError(AppException):
    def __init__(self, message: str = "Access forbidden"):
        super().__init__(ErrorCodes.AUTH_FORBIDDEN, message, 403)


class ValidationError(AppException):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(ErrorCodes.VALIDATION_ERROR, message, 422, details)


class DataSourceError(AppException):
    def __init__(self, message: str = "Data source temporarily unavailable"):
        super().__init__(ErrorCodes.DATA_SOURCE_ERROR, message, 503)
