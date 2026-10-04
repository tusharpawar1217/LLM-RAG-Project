"""
Custom exception classes for domain-specific errors.
All exceptions include proper HTTP status codes for API responses.
"""

from typing import Any


class AskDocsException(Exception):
    """Base exception for all AskDocs errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


# Authentication & Authorization
class AuthenticationError(AskDocsException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed", details: dict[str, Any] | None = None):
        super().__init__(message, status_code=401, details=details)


class AuthorizationError(AskDocsException):
    """Raised when user lacks permission."""

    def __init__(self, message: str = "Permission denied", details: dict[str, Any] | None = None):
        super().__init__(message, status_code=403, details=details)


class InvalidAPIKeyError(AuthenticationError):
    """Raised when API key is invalid or expired."""

    def __init__(self, message: str = "Invalid or expired API key"):
        super().__init__(message)


# Tenant & Multi-tenancy
class TenantNotFoundError(AskDocsException):
    """Raised when tenant does not exist."""

    def __init__(self, tenant_id: str | None = None):
        message = f"Tenant not found: {tenant_id}" if tenant_id else "Tenant not found"
        super().__init__(message, status_code=404)


class TenantIsolationError(AskDocsException):
    """Raised when tenant isolation is violated."""

    def __init__(self, message: str = "Cross-tenant access denied"):
        super().__init__(message, status_code=403)


# Resource Errors
class ResourceNotFoundError(AskDocsException):
    """Raised when a resource is not found."""

    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            f"{resource_type} not found: {resource_id}",
            status_code=404,
        )


class ResourceAlreadyExistsError(AskDocsException):
    """Raised when trying to create a duplicate resource."""

    def __init__(self, resource_type: str, identifier: str):
        super().__init__(
            f"{resource_type} already exists: {identifier}",
            status_code=409,
        )


# Document Processing
class DocumentProcessingError(AskDocsException):
    """Raised when document processing fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, status_code=422, details=details)


class DocumentError(AskDocsException):
    """Raised when document operation fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, status_code=400, details=details)


class IngestionError(AskDocsException):
    """Raised when document ingestion fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, status_code=500, details=details)


class ParsingError(AskDocsException):
    """Raised when document parsing fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, status_code=422, details=details)


class ChunkingError(AskDocsException):
    """Raised when document chunking fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, status_code=500, details=details)


class EmbeddingError(AskDocsException):
    """Raised when embedding generation fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, status_code=500, details=details)


class UnsupportedFileTypeError(DocumentProcessingError):
    """Raised when file type is not supported."""

    def __init__(self, file_type: str):
        super().__init__(f"Unsupported file type: {file_type}")


class DocumentTooLargeError(DocumentProcessingError):
    """Raised when document exceeds size limit."""

    def __init__(self, size_mb: float, max_size_mb: float = 10):
        super().__init__(
            f"Document too large: {size_mb:.2f}MB (max: {max_size_mb}MB)",
            details={"size_mb": size_mb, "max_size_mb": max_size_mb},
        )


# Retrieval & Generation
class RetrievalError(AskDocsException):
    """Raised when retrieval fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, status_code=500, details=details)


class GenerationError(AskDocsException):
    """Raised when LLM generation fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, status_code=500, details=details)


class InsufficientContextError(AskDocsException):
    """Raised when no relevant context is found."""

    def __init__(self, message: str = "No relevant information found in documents"):
        super().__init__(message, status_code=404)


# Billing & Limits
class QuotaExceededError(AskDocsException):
    """Raised when tenant exceeds plan limits."""

    def __init__(self, resource: str, limit: int, current: int):
        super().__init__(
            f"{resource} limit exceeded: {current}/{limit}",
            status_code=429,
            details={"resource": resource, "limit": limit, "current": current},
        )


class PaymentRequiredError(AskDocsException):
    """Raised when payment is required to continue."""

    def __init__(self, message: str = "Payment required"):
        super().__init__(message, status_code=402)


class SubscriptionInactiveError(PaymentRequiredError):
    """Raised when subscription is inactive."""

    def __init__(self):
        super().__init__("Subscription is inactive or expired")


# Rate Limiting
class RateLimitExceededError(AskDocsException):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int | None = None):
        message = "Rate limit exceeded"
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(message, status_code=429, details=details)


# Validation
class ValidationError(AskDocsException):
    """Raised when input validation fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, status_code=422, details=details)


# External Service Errors
class ExternalServiceError(AskDocsException):
    """Raised when external service call fails."""

    def __init__(self, service: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            f"{service} error: {message}",
            status_code=502,
            details=details,
        )


class OpenAIError(ExternalServiceError):
    """Raised when OpenAI API call fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__("OpenAI", message, details)


class QdrantError(ExternalServiceError):
    """Raised when Qdrant operation fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__("Qdrant", message, details)


class StripeError(ExternalServiceError):
    """Raised when Stripe operation fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__("Stripe", message, details)


