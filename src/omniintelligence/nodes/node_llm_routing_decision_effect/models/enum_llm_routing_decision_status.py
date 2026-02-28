# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Enum for LLM routing decision processing status.

Reference: OMN-2939
"""

from __future__ import annotations

from enum import Enum


class EnumLlmRoutingDecisionStatus(str, Enum):
    """Processing status for an LLM routing decision event.

    Attributes:
        SUCCESS: Event was successfully processed and upserted.
        ERROR: Processing failed due to a database or unexpected error.
    """

    SUCCESS = "success"
    ERROR = "error"


__all__ = ["EnumLlmRoutingDecisionStatus"]
