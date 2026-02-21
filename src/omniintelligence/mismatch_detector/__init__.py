# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Rationale mismatch detector module.

Detects conflicts between Layer 2 agent_rationale and Layer 1 provenance
in DecisionRecords, and emits evaluation signals via Kafka.

Ticket: OMN-2472
"""

from omniintelligence.mismatch_detector.consumer import MismatchDetectionConsumer
from omniintelligence.mismatch_detector.detector import (
    DecisionRecordDict,
    detect_mismatches,
)
from omniintelligence.mismatch_detector.models import (
    MismatchReport,
    MismatchSeverity,
    MismatchType,
)

__all__ = [
    "DecisionRecordDict",
    "MismatchDetectionConsumer",
    "MismatchReport",
    "MismatchSeverity",
    "MismatchType",
    "detect_mismatches",
]
