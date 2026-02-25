# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Variant role enum for A/B objective testing (OMN-2571)."""

from __future__ import annotations

from enum import Enum


class EnumVariantRole(str, Enum):
    """Role of an objective variant in the A/B framework."""

    ACTIVE = "active"
    """The production variant. Its EvaluationResult drives policy state updates."""

    SHADOW = "shadow"
    """A shadow variant evaluated in parallel. Does NOT affect policy state."""


__all__ = ["EnumVariantRole"]
