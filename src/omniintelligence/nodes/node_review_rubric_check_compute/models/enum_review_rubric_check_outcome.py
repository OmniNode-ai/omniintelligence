# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Outcome of a review rubric check (OMN-21186)."""

from __future__ import annotations

from enum import Enum


class EnumReviewRubricCheckOutcome(str, Enum):
    ACCEPTED = "pass"
    REFUSED = "refused"


__all__ = ["EnumReviewRubricCheckOutcome"]
