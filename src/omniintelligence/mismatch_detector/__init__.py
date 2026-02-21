# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Rationale mismatch detection module.

Detects conflicts between agent_rationale (Layer 2) and the structured
provenance fields (Layer 1: constraints_applied, scoring_breakdown) in
DecisionRecords.

This module implements the enforcement mechanism for the trust invariant:
"If agent rationale conflicts with recorded constraints, structured
provenance wins."

Ticket: OMN-2472
"""

from omniintelligence.mismatch_detector.detector import detect_mismatches
from omniintelligence.mismatch_detector.models import (
    MismatchReport,
    MismatchSeverity,
    MismatchType,
)

__all__ = [
    "MismatchReport",
    "MismatchSeverity",
    "MismatchType",
    "detect_mismatches",
]
