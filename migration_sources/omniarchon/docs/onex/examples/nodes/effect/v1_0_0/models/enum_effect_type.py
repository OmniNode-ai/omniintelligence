"""Effect operation types enum."""

from enum import Enum


class EnumEffectType(Enum):
    """
    Effect operation types supported by canonical node.

    Extensible design - add new types as needed for your use case.
    Each type should have a corresponding handler registered.
    """

    FILE_OPERATION = "file_operation"
    DATABASE_OPERATION = "database_operation"
    HTTP_REQUEST = "http_request"
    EMAIL_SEND = "email_send"
    AUDIT_LOG = "audit_log"
    API_CALL = "api_call"
    EVENT_EMISSION = "event_emission"
    DIRECTORY_OPERATION = "directory_operation"
    METRICS_COLLECTION = "metrics_collection"
