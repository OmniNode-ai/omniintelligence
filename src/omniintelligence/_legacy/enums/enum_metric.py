"""
Metric type enums for omniintelligence.

Contains metric types for monitoring.
"""

from enum import Enum


class EnumMetricType(str, Enum):
    """Metric types for monitoring."""
    WORKFLOW = "WORKFLOW"
    PERFORMANCE = "PERFORMANCE"
    ERRORS = "ERRORS"
    RESOURCE = "RESOURCE"
    FSM = "FSM"
    LEASE = "LEASE"


__all__ = [
    "EnumMetricType",
]
