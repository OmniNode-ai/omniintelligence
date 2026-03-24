# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Regression test: projection snapshot must stay under 4MB even with 500 patterns.

Reference: OMN-6341 (Kafka MessageSizeTooLarge fix)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from omniintelligence.models.events.model_pattern_projection_event import (
    ModelPatternProjectionEvent,
)
from omniintelligence.models.repository.model_pattern_summary import (
    ModelPatternSummary,
)


@pytest.mark.unit
def test_projection_snapshot_size_bounded_with_truncated_signatures() -> None:
    """500 patterns with 512-char signatures must serialize to under 4MB."""
    # Simulate the truncated signature (512 chars, realistic worst case)
    long_signature = "x" * 512

    patterns = [
        ModelPatternSummary(
            id=uuid4(),
            pattern_signature=long_signature,
            signature_hash=f"sha256:{uuid4().hex}",
            domain_id="test-domain",
            project_scope="omniclaude",
            quality_score=0.85,
            confidence=0.9,
            status="validated",
            is_current=True,
            version=1,
            created_at=datetime.now(UTC),
        )
        for _ in range(500)
    ]

    snapshot = ModelPatternProjectionEvent(
        snapshot_id=uuid4(),
        snapshot_at=datetime.now(UTC),
        patterns=patterns,
        total_count=len(patterns),
        version=1,
    )

    serialized = json.dumps(
        snapshot.model_dump(mode="json"),
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")

    # 500 patterns with 512-char signatures should be well under 4MB
    # Estimated: ~500 * (512 + 200 overhead) = ~356KB
    assert len(serialized) < 4_000_000, (
        f"Projection snapshot too large: {len(serialized)} bytes with "
        f"{len(patterns)} patterns. Expected < 4MB (max_request_size). "
        f"Review truncation limit."
    )

    # Also verify it's under the old 1MB limit for sanity
    assert len(serialized) < 1_000_000, (
        f"Projection snapshot {len(serialized)} bytes -- still over 1MB even "
        f"with truncation. The truncation limit may need to be reduced."
    )
