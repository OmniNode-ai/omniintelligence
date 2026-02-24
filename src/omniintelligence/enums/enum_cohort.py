# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Cohort enum for A/B experiment assignment in pattern injection.

Ticket: OMN-1670
"""

from enum import Enum


class EnumCohort(str, Enum):
    """A/B experiment cohort for pattern injection.

    Sessions are assigned to cohorts using a deterministic hash-based
    algorithm: hash(session_id + salt) % 100. The split is currently
    20% control, 80% treatment.

    The cohort value is stored on each injection record so the assignment
    logic can evolve without rewriting historical data.

    Attributes:
        CONTROL: No pattern injection (baseline for comparison)
        TREATMENT: Receives validated pattern injection

    Example:
        >>> from omniintelligence.enums import EnumCohort
        >>> cohort = EnumCohort.TREATMENT
        >>> assert cohort.value == "treatment"

    Note:
        Values match the CHECK constraint in migration 007_create_pattern_injections.sql.
        If you add values here, update the SQL constraint too.

    See Also:
        - deployment/database/migrations/007_create_pattern_injections.sql
    """

    CONTROL = "control"
    TREATMENT = "treatment"


# Constants for cohort assignment
COHORT_CONTROL_PERCENTAGE = 20
COHORT_TREATMENT_PERCENTAGE = 80


__all__ = ["EnumCohort", "COHORT_CONTROL_PERCENTAGE", "COHORT_TREATMENT_PERCENTAGE"]
