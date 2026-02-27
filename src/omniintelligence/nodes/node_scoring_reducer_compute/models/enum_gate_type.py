# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Enum for gate types in objective specifications (OMN-2537)."""

from __future__ import annotations

from enum import Enum


class EnumGateType(str, Enum):
    """Hard-gate types that must pass before shaped reward is evaluated."""

    THRESHOLD = "threshold"
    """Evidence value must meet or exceed a numeric threshold."""

    BOOLEAN = "boolean"
    """Evidence value must be truthy."""

    RANGE = "range"
    """Evidence value must fall within a defined range."""

    REGEX = "regex"
    """Evidence value (string) must match a regular expression."""


__all__ = ["EnumGateType"]
