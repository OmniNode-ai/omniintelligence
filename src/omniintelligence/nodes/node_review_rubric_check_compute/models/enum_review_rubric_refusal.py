# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Why a review rubric file was refused (OMN-21186)."""

from __future__ import annotations

from enum import Enum


class EnumReviewRubricRefusal(str, Enum):
    """The named reasons the loader refuses a rubric file, in check order."""

    NOT_YAML = "not_yaml"
    NOT_A_MAPPING = "not_a_mapping"
    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
    MALFORMED = "malformed"
    CONTENT_HASH_MISMATCH = "content_hash_mismatch"
    OVER_BUDGET = "over_token_budget"


__all__ = ["EnumReviewRubricRefusal"]
