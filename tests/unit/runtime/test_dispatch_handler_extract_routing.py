# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for file extension routing in extract handler (OMN-5680)."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from omniintelligence.runtime.dispatch_handler_code_extract import (
    _get_extraction_strategy,
    create_code_extract_dispatch_handler,
)

LANG_CONFIG = {
    "python": {"enabled": True, "strategy": "ast"},
    "typescript": {
        "enabled": True,
        "strategy": "regex",
        "patterns": {
            "class": r"class\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+extends\s+([A-Za-z_][A-Za-z0-9_]*))?\s*\{",
            "function": r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            "interface": r"(?:export\s+)?interface\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+extends\s+[^{]+)?\s*\{",
        },
    },
    "javascript": {
        "enabled": True,
        "strategy": "regex",
        "patterns": {
            "function": r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        },
    },
}


@pytest.mark.unit
class TestExtractionStrategyRouting:
    """Tests for _get_extraction_strategy routing."""

    def test_python_uses_ast(self) -> None:
        assert _get_extraction_strategy("py", LANG_CONFIG) == "ast"

    def test_typescript_uses_regex(self) -> None:
        assert _get_extraction_strategy("ts", LANG_CONFIG) == "regex"

    def test_javascript_uses_regex(self) -> None:
        assert _get_extraction_strategy("js", LANG_CONFIG) == "regex"

    def test_unknown_extension_skips(self) -> None:
        assert _get_extraction_strategy("rs", LANG_CONFIG) == "skip"

    def test_disabled_language_skips(self) -> None:
        config = {"go": {"enabled": False, "strategy": "regex", "patterns": {}}}
        assert _get_extraction_strategy("go", config) == "skip"


@pytest.mark.unit
class TestExtractHandlerTsRouting:
    """Test that extract handler routes .ts files to regex extractor."""

    @pytest.mark.asyncio
    async def test_ts_file_produces_entities(self) -> None:
        """Extract handler receives .ts file event and dispatches to regex extractor."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "server" / "app.ts"
            ts_file.parent.mkdir(parents=True)
            ts_file.write_text(
                "export class EventBus {\n"
                "    constructor() {}\n"
                "}\n"
                "\n"
                "export function handleEvent(e: Event) {\n"
                "    console.log(e);\n"
                "}\n"
            )

            mock_publisher = AsyncMock()

            handler = create_code_extract_dispatch_handler(
                repo_paths={"omnidash": tmpdir},
                kafka_publisher=mock_publisher,
                publish_topic="onex.evt.omniintelligence.code-entities-extracted.v1",
                language_extractors_config=LANG_CONFIG,
            )

            envelope = MagicMock()
            envelope.payload = {
                "event_id": "evt-1",
                "crawl_id": "crawl-1",
                "repo_name": "omnidash",
                "file_path": "server/app.ts",
                "file_hash": "abc123",
                "file_size_bytes": 100,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            context = MagicMock()
            context.correlation_id = "test-cid"

            result = await handler(envelope, context)
            assert result == "ok"

            # Should have published entities
            mock_publisher.publish.assert_called_once()
            call_kwargs = mock_publisher.publish.call_args.kwargs
            event_data = call_kwargs["value"]
            assert event_data["repo_name"] == "omnidash"
            assert event_data["extractor_version"] == "multilang-regex-1.0.0"
            assert len(event_data["entities"]) >= 2  # class + function
