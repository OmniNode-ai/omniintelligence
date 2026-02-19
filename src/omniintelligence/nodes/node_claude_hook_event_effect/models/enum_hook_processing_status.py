"""Hook processing status enum."""

from enum import StrEnum


class EnumHookProcessingStatus(StrEnum):
    """Status of hook event processing."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


__all__ = ["EnumHookProcessingStatus"]
