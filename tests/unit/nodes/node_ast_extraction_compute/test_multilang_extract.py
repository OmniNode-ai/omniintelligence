# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for multi-language extraction (OMN-5679)."""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_multilang_extract import (
    REGEX_CONFIDENCE,
    MultiLangExtractor,
)

LANG_CONFIG = {
    "python": {"enabled": True, "strategy": "ast"},
    "typescript": {
        "enabled": True,
        "strategy": "regex",
        "patterns": {
            "class": r"class\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+extends\s+([A-Za-z_][A-Za-z0-9_]*))?\s*\{",
            "function": r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            "arrow_function": r"(?:export\s+)?(?:const|let)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s+)?\(",
            "interface": r"(?:export\s+)?interface\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+extends\s+[^{]+)?\s*\{",
            "type_alias": r"(?:export\s+)?type\s+([A-Za-z_][A-Za-z0-9_]*)\s*=",
            "import": r"import\s+(?:\{[^}]+\}|\*\s+as\s+\w+|\w+)\s+from\s+['\"]([^'\"]+)['\"]",
            "enum": r"(?:export\s+)?(?:const\s+)?enum\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{",
        },
    },
    "javascript": {
        "enabled": True,
        "strategy": "regex",
        "patterns": {
            "class": r"class\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+extends\s+([A-Za-z_][A-Za-z0-9_]*))?\s*\{",
            "function": r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            "arrow_function": r"(?:export\s+)?(?:const|let)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s+)?\(",
            "import": r"(?:import|require)\s*\(?['\"]([^'\"]+)['\"]\)?",
        },
    },
    "go": {"enabled": False, "strategy": "regex", "patterns": {}},
}


@pytest.mark.unit
class TestMultiLangExtractor:
    """Tests for multi-language regex extraction."""

    def test_typescript_class_and_interface(self) -> None:
        """TypeScript file with class and interface extracts correctly."""
        extractor = MultiLangExtractor(LANG_CONFIG)
        source = """
export class EventBus extends BaseService {
    constructor() {
        super();
    }
}

export interface EventHandler {
    handle(event: Event): Promise<void>;
}
"""
        entities = extractor.extract(
            source_content=source,
            source_path="server/event_bus.ts",
            source_repo="omnidash",
            file_hash="abc123",
            extension="ts",
        )

        assert len(entities) == 2
        class_entity = next(e for e in entities if e["entity_name"] == "EventBus")
        assert class_entity["entity_type"] == "class"
        assert class_entity["bases"] == ["BaseService"]
        assert class_entity["confidence"] == REGEX_CONFIDENCE

        interface_entity = next(
            e for e in entities if e["entity_name"] == "EventHandler"
        )
        assert interface_entity["entity_type"] == "interface"
        assert interface_entity["source_language"] == "typescript"

    def test_typescript_interface_type(self) -> None:
        """TypeScript interface produces entity_type='interface' not 'class'."""
        extractor = MultiLangExtractor(LANG_CONFIG)
        source = """
export interface KafkaConfig {
    brokers: string[];
    topic: string;
}
"""
        entities = extractor.extract(
            source_content=source,
            source_path="server/config.ts",
            source_repo="omnidash",
            file_hash="def456",
            extension="ts",
        )

        assert len(entities) == 1
        assert entities[0]["entity_type"] == "interface"
        assert entities[0]["entity_name"] == "KafkaConfig"
        assert entities[0]["source_language"] == "typescript"

    def test_javascript_arrow_function(self) -> None:
        """JavaScript arrow function extraction."""
        extractor = MultiLangExtractor(LANG_CONFIG)
        source = """
export const handleEvent = async (event) => {
    console.log(event);
};

function processData(data) {
    return data.map(d => d.value);
}
"""
        entities = extractor.extract(
            source_content=source,
            source_path="server/handlers.js",
            source_repo="omnidash",
            file_hash="ghi789",
            extension="js",
        )

        names = {e["entity_name"] for e in entities}
        assert "handleEvent" in names
        assert "processData" in names
        for entity in entities:
            assert entity["entity_type"] == "function"
            assert entity["source_language"] == "javascript"
            assert entity["line_number"] > 0

    def test_go_disabled(self) -> None:
        """Go extraction is disabled in config."""
        extractor = MultiLangExtractor(LANG_CONFIG)
        assert not extractor.can_extract("go")

    def test_python_not_handled(self) -> None:
        """Python files are not handled (strategy: ast, not regex)."""
        extractor = MultiLangExtractor(LANG_CONFIG)
        assert not extractor.can_extract("py")
