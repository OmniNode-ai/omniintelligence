"""
Custom Exceptions for Langextract HTTP Client

Provides specific exception types for different failure scenarios when
communicating with the langextract service.
"""


# NOTE: correlation_id support enabled for tracing
class LangextractError(Exception):
    """
    Base exception for langextract client errors.

    All langextract-specific exceptions inherit from this base class,
    allowing callers to catch all langextract errors with a single except clause.
    """

    def __init__(
        self, message: str, status_code: int = None, response_data: dict = None
    ):
        """
        Initialize langextract error.

        Args:
            message: Error description
            status_code: Optional HTTP status code
            response_data: Optional response data from service
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}


class LangextractUnavailableError(LangextractError):
    """
    Exception raised when langextract service is unavailable.

    This includes scenarios such as:
    - Service not responding (connection refused)
    - Service returning 503 Service Unavailable
    - Circuit breaker open state
    - Network connectivity issues

    Usage:
        Indicates the service cannot be reached and the client should
        implement retry logic or fail gracefully.
    """

    def __init__(self, message: str = "Langextract service is unavailable"):
        """
        Initialize unavailable error.

        Args:
            message: Error description (default: service unavailable message)
        """
        super().__init__(message, status_code=503)


class LangextractTimeoutError(LangextractError):
    """
    Exception raised when a request to langextract times out.

    This indicates the service did not respond within the configured timeout period.
    The default timeout is 5 seconds, but can be customized per request.

    Usage:
        Indicates a slow or hung service. The client may retry with a longer timeout
        or fail gracefully.
    """

    def __init__(
        self,
        message: str = "Request to langextract service timed out",
        timeout_seconds: float = None,
    ):
        """
        Initialize timeout error.

        Args:
            message: Error description (default: timeout message)
            timeout_seconds: Optional timeout value that was exceeded
        """
        super().__init__(message, status_code=408)
        self.timeout_seconds = timeout_seconds


class LangextractValidationError(LangextractError):
    """
    Exception raised when request validation fails.

    This indicates the request payload did not meet the service's validation requirements,
    such as missing required fields or invalid data types.

    Usage:
        Indicates a client-side error that should not be retried without fixing
        the request data.
    """

    def __init__(self, message: str, validation_errors: list = None):
        """
        Initialize validation error.

        Args:
            message: Error description
            validation_errors: Optional list of specific validation failures
        """
        super().__init__(message, status_code=422)
        self.validation_errors = validation_errors or []


class LangextractRateLimitError(LangextractError):
    """
    Exception raised when rate limit is exceeded.

    This indicates the client has made too many requests and should back off
    before retrying.

    Usage:
        Indicates temporary throttling. The client should implement exponential
        backoff before retrying.
    """

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = None):
        """
        Initialize rate limit error.

        Args:
            message: Error description (default: rate limit message)
            retry_after: Optional seconds to wait before retrying
        """
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class LangextractServerError(LangextractError):
    """
    Exception raised when langextract service returns a 5xx error.

    This indicates an internal server error on the langextract side.
    The client may retry after a delay.

    Usage:
        Indicates a temporary service-side issue. Retry with exponential backoff.
    """

    def __init__(
        self, message: str, status_code: int = 500, response_data: dict = None
    ):
        """
        Initialize server error.

        Args:
            message: Error description
            status_code: HTTP status code (5xx)
            response_data: Optional response data from service
        """
        super().__init__(message, status_code=status_code, response_data=response_data)
