# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Preemptive Pattern Injection: inject stable patterns before code generation.

Public API:

    from omniintelligence.review_pairing.injection import (
        PatternConstraintCandidate,
        InjectionContext,
        InjectionResult,
        RewardSignal,
        PatternInjector,
    )

Reference: OMN-2577
"""

from omniintelligence.review_pairing.injection.injector import (
    InjectionContext,
    InjectionResult,
    PatternConstraintCandidate,
    PatternInjector,
    RewardSignal,
    RewardSignalType,
)

__all__ = [
    "InjectionContext",
    "InjectionResult",
    "PatternConstraintCandidate",
    "PatternInjector",
    "RewardSignal",
    "RewardSignalType",
]
