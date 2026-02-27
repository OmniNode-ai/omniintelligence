# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Policy lifecycle state enum (OMN-2557)."""

from __future__ import annotations

from enum import Enum


class EnumPolicyLifecycleState(str, Enum):
    """Lifecycle states for a policy entry.

    Transitions:
        CANDIDATE → VALIDATED when N runs with positive signal
        VALIDATED → PROMOTED when statistical significance threshold met
        PROMOTED → DEPRECATED when reliability falls below hard floor
    """

    CANDIDATE = "candidate"
    """Initial state — insufficient evidence to validate."""

    VALIDATED = "validated"
    """N positive runs observed — policy is confirmed."""

    PROMOTED = "promoted"
    """Statistical significance reached — policy is actively used."""

    DEPRECATED = "deprecated"
    """Reliability fell below floor — policy is no longer used."""


__all__ = ["EnumPolicyLifecycleState"]
