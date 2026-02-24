# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

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

    IMPORTANT: Valid transitions are defined in contract.yaml (intelligence_reducer),
    NOT in this enum. This enum provides type safety only.

    See: OMN-1805 - contract.yaml is the single source of truth for transitions.

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
        - nodes/node_intelligence_reducer/contract.yaml (authoritative transitions)
    """

    CANDIDATE = "candidate"
    PROVISIONAL = "provisional"
    VALIDATED = "validated"
    DEPRECATED = "deprecated"


__all__ = ["EnumPatternLifecycleStatus"]
