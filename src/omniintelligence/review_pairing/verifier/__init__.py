# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Finding Disappearance Verifier for the Review-Fix Pairing subsystem.

Implements post-fix CI confirmation that a finding has disappeared (OMN-2560).

Public API:
    FindingDisappearanceVerifier — Main verifier class
    VerificationOutcome          — Enum of possible outcomes
    VerificationResult           — Result of a verification attempt
    PostFixCIFindings            — Input container for post-fix CI results
    PostFixFinding               — Single finding from a post-fix CI run
"""

from omniintelligence.review_pairing.verifier.verifier import (
    FindingDisappearanceVerifier,
    PostFixCIFindings,
    PostFixFinding,
    VerificationOutcome,
    VerificationResult,
)

__all__ = [
    "FindingDisappearanceVerifier",
    "PostFixCIFindings",
    "PostFixFinding",
    "VerificationOutcome",
    "VerificationResult",
]
