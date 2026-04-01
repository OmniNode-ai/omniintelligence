# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for crawler ModelCodeFileDiscoveredEvent.

Validates the source_content field addition for OMN-7232.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from omniintelligence.nodes.node_code_crawler_effect.models.model_code_file_discovered_event import (
    ModelCodeFileDiscoveredEvent,
)

pytestmark = pytest.mark.unit


def test_discovered_event_includes_source_content() -> None:
    event = ModelCodeFileDiscoveredEvent(
        event_id="test-id",
        crawl_id="crawl-1",
        repo_name="omnibase_core",
        file_path="src/omnibase_core/nodes/node_compute.py",
        file_hash="abc123",
        file_size_bytes=1234,
        source_content="class NodeCompute: pass",
        timestamp=datetime.now(tz=timezone.utc),
    )
    assert event.source_content == "class NodeCompute: pass"
