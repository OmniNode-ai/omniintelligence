"""
Quality dimension enums for omniintelligence.

Contains quality assessment dimensions.
"""

from enum import Enum


class EnumQualityDimension(str, Enum):
    """Quality assessment dimensions."""
    MAINTAINABILITY = "MAINTAINABILITY"
    READABILITY = "READABILITY"
    COMPLEXITY = "COMPLEXITY"
    DOCUMENTATION = "DOCUMENTATION"
    TESTING = "TESTING"
    SECURITY = "SECURITY"


__all__ = [
    "EnumQualityDimension",
]
