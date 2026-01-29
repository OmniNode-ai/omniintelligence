"""Pattern lifecycle status enum for OmniIntelligence.

This module contains the canonical pattern lifecycle status enumeration
for tracking learned patterns through their promotion/demotion lifecycle.

ONEX Compliance:
    - Enum-based naming: Enum{Category}
    - String-based enum for JSON serialization
    - Integration with Pydantic models

Ticket: OMN-1667
"""

from enum import Enum


class EnumPatternLifecycleStatus(str, Enum):
    """Pattern lifecycle status for learned patterns.

    This enum defines the promotion/demotion lifecycle for learned patterns.
    Patterns progress through these statuses based on rolling quality metrics
    and temporal stability.

    Lifecycle Flow:
        CANDIDATE → PROVISIONAL → VALIDATED → (deprecated: DEPRECATED)

    Promotion Gates:
        - CANDIDATE → PROVISIONAL: Initial quality threshold met
        - PROVISIONAL → VALIDATED: Temporal stability + consistent quality
        - Any → DEPRECATED: Failure streak or manual deprecation

    Attributes:
        CANDIDATE: Newly discovered pattern, under evaluation
        PROVISIONAL: Passed initial quality gates, building track record
        VALIDATED: Production-ready pattern with proven track record
        DEPRECATED: Pattern no longer recommended for use

    Example:
        >>> from omniintelligence.enums import EnumPatternLifecycleStatus
        >>> status = EnumPatternLifecycleStatus.CANDIDATE
        >>> assert status.value == "candidate"

    See Also:
        - deployment/database/migrations/005_create_learned_patterns.sql
        - Manifest Injection Enhancement Plan for promotion/demotion rules
    """

    CANDIDATE = "candidate"
    PROVISIONAL = "provisional"
    VALIDATED = "validated"
    DEPRECATED = "deprecated"


__all__ = ["EnumPatternLifecycleStatus"]
