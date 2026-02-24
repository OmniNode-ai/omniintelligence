# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Insight identity key generation for deduplication.

This module provides functions for generating unique identity keys
for codebase insights, enabling deduplication across sessions and
pattern extraction runs.

The identity key composition varies by insight type to capture the
semantic identity of each pattern category.
"""

from __future__ import annotations

import hashlib

from omniintelligence.nodes.node_pattern_extraction_compute.models import (
    EnumInsightType,
    ModelCodebaseInsight,
)


def insight_identity_key(insight: ModelCodebaseInsight) -> str:
    """Generate unique identity key for deduplication.

    The key composition varies by insight type to capture semantic identity.
    This allows insights with the same semantic meaning to be deduplicated
    even if they have different metadata (timestamps, occurrence counts).

    Key Format: "{insight_type}:{working_directory}:{type_specific_identifier}"

    Type-specific identifiers:
        - FILE_ACCESS_PATTERN: First 5 sorted evidence files
        - ERROR_PATTERN: Primary file + description hash
        - ARCHITECTURE_PATTERN: Working directory prefix
        - TOOL_USAGE_PATTERN: Description hash
        - ENTRY_POINT_PATTERN: First 3 sorted evidence files
        - MODIFICATION_CLUSTER: First 5 sorted evidence files

    Args:
        insight: The codebase insight to generate a key for.

    Returns:
        A unique identity key string for deduplication.

    Example:
        >>> from datetime import datetime
        >>> insight = ModelCodebaseInsight(
        ...     insight_id="test-1",
        ...     insight_type=EnumInsightType.FILE_ACCESS_PATTERN,
        ...     description="Common file access pattern",
        ...     confidence=0.85,
        ...     evidence_files=("src/main.py", "src/utils.py"),
        ...     evidence_session_ids=("session-1",),
        ...     occurrence_count=5,
        ...     first_observed=datetime.now(),
        ...     last_observed=datetime.now(),
        ...     working_directory="/path/to/repo",
        ... )
        >>> key = insight_identity_key(insight)
        >>> key.startswith("file_access_pattern:/path/to/repo:")
        True
    """
    base = f"{insight.insight_type.value}:{insight.working_directory or '_'}:"

    match insight.insight_type:
        case EnumInsightType.FILE_ACCESS_PATTERN:
            files_key = "|".join(sorted(insight.evidence_files[:5]))
            return f"{base}files:{files_key}"

        case EnumInsightType.ERROR_PATTERN:
            primary_file = insight.evidence_files[0] if insight.evidence_files else "_"
            desc_hash = hashlib.md5(
                insight.description.encode(), usedforsecurity=False
            ).hexdigest()[:8]
            return f"{base}error:{primary_file}:{desc_hash}"

        case EnumInsightType.ARCHITECTURE_PATTERN:
            dir_prefix = insight.working_directory or "_"
            return f"{base}arch:{dir_prefix}"

        case EnumInsightType.TOOL_USAGE_PATTERN:
            desc_hash = hashlib.md5(
                insight.description.encode(), usedforsecurity=False
            ).hexdigest()[:8]
            return f"{base}tool:{desc_hash}"

        case EnumInsightType.ENTRY_POINT_PATTERN:
            files_key = "|".join(sorted(insight.evidence_files[:3]))
            return f"{base}entry:{files_key}"

        case EnumInsightType.MODIFICATION_CLUSTER:
            files_key = "|".join(sorted(insight.evidence_files[:5]))
            return f"{base}mod:{files_key}"

        case _:
            # Fallback for any new insight types added to the enum.
            # This is intentionally defensive - mypy sees it as unreachable
            # because all current enum values are handled, but we want
            # runtime safety if new values are added without updating this match.
            desc_hash = hashlib.md5(  # type: ignore[unreachable]
                insight.description.encode(), usedforsecurity=False
            ).hexdigest()[:8]
            return f"{base}unknown:{desc_hash}"


__all__ = ["insight_identity_key"]
