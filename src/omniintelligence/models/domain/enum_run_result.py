"""Pipeline run result enum."""

from enum import StrEnum


class EnumRunResult(StrEnum):
    """Valid pipeline run result values."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"


__all__ = ["EnumRunResult"]
