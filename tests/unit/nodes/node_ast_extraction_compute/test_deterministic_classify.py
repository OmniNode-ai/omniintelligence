# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for deterministic Node Classifier (OMN-5674)."""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_deterministic_classify import (
    DeterministicClassifier,
)

# Contract config matching the plan's YAML specification
CLASSIFY_CONFIG: dict = {
    "enabled": True,
    "scoring_weights": {
        "domain": 0.30,
        "operation": 0.30,
        "keyword": 0.25,
        "feature": 0.15,
    },
    "classifications": {
        "effect": {
            "keywords": [
                "database",
                "api",
                "http",
                "kafka",
                "redis",
                "file",
                "send",
                "publish",
                "persist",
                "fetch",
            ],
            "domains": ["database", "api", "messaging", "storage", "cache"],
            "operations": [
                "create",
                "read",
                "update",
                "delete",
                "send",
                "receive",
                "publish",
                "subscribe",
            ],
            "features": [
                "connection_pooling",
                "retry_logic",
                "circuit_breaker",
                "rate_limiting",
            ],
        },
        "compute": {
            "keywords": [
                "transform",
                "convert",
                "parse",
                "format",
                "encode",
                "calculate",
                "compute",
                "hash",
                "validate",
            ],
            "domains": ["ml", "general"],
            "operations": [
                "transform",
                "calculate",
                "compute",
                "parse",
                "validate",
                "process",
            ],
            "features": ["validation", "caching"],
        },
        "reducer": {
            "keywords": [
                "aggregate",
                "reduce",
                "collect",
                "accumulate",
                "group",
                "summarize",
                "merge",
                "state",
                "metrics",
            ],
            "domains": ["monitoring"],
            "operations": [
                "aggregate",
                "reduce",
                "collect",
                "group",
                "summarize",
                "accumulate",
            ],
            "features": ["metrics", "logging"],
        },
        "orchestrator": {
            "keywords": [
                "orchestrate",
                "coordinate",
                "workflow",
                "pipeline",
                "dispatch",
                "schedule",
                "route",
            ],
            "domains": ["workflow"],
            "operations": [
                "orchestrate",
                "coordinate",
                "schedule",
                "dispatch",
                "route",
            ],
            "features": ["parallel_execution", "retry_orchestration", "saga_pattern"],
        },
    },
    "min_confidence": 0.4,
}


@pytest.mark.unit
class TestDeterministicClassifier:
    """Tests for deterministic classification."""

    def test_clear_effect_classification(self) -> None:
        """Entity with NodeEffect base and send/publish methods → effect."""
        classifier = DeterministicClassifier(CLASSIFY_CONFIG)
        result = classifier.classify(
            entity_name="NodePatternStorageEffect",
            bases=["NodeEffect"],
            methods=[
                {"name": "publish"},
                {"name": "send"},
                {"name": "persist"},
            ],
            docstring="Publishes patterns to Kafka and persists to database.",
        )
        assert result.node_type == "effect"
        assert result.confidence > 0.5

    def test_mixed_signals(self) -> None:
        """Entity with mixed signals returns top + alternatives."""
        classifier = DeterministicClassifier(CLASSIFY_CONFIG)
        result = classifier.classify(
            entity_name="DataPipelineOrchestrator",
            bases=["NodeOrchestrator"],
            methods=[
                {"name": "orchestrate"},
                {"name": "coordinate"},
                {"name": "dispatch"},
                {"name": "persist"},
            ],
            docstring="Orchestrates workflow pipeline with database persistence and scheduling.",
        )
        # Should classify as orchestrator, but with effect as an alternative
        assert result.node_type != "unclassified"
        assert len(result.alternatives) > 0

    def test_low_confidence_unclassified(self) -> None:
        """Entity with no strong signals → unclassified."""
        classifier = DeterministicClassifier(CLASSIFY_CONFIG)
        result = classifier.classify(
            entity_name="Foo",
            bases=[],
            methods=[{"name": "bar"}],
        )
        assert result.node_type == "unclassified"
        assert result.confidence < 0.4

    def test_classification_speed(self) -> None:
        """Classification completes in <1ms per entity."""
        import time

        classifier = DeterministicClassifier(CLASSIFY_CONFIG)
        start = time.perf_counter()
        for _ in range(1000):
            classifier.classify(
                entity_name="NodeDatabaseEffect",
                bases=["NodeEffect"],
                methods=[{"name": "persist"}, {"name": "fetch"}],
            )
        elapsed_ms = (time.perf_counter() - start) * 1000
        avg_ms = elapsed_ms / 1000
        assert avg_ms < 1.0, f"Avg classification took {avg_ms:.3f}ms (expected <1ms)"

    def test_config_driven_keywords(self) -> None:
        """Adding a keyword to config changes classification behavior."""
        # Without "foobar" keyword, entity gets low/no compute score
        classifier = DeterministicClassifier(CLASSIFY_CONFIG)
        result1 = classifier.classify(
            entity_name="FoobarProcessor",
            methods=[{"name": "do_foobar"}, {"name": "run_foobar"}],
            docstring="Processes foobar data using foobar algorithm.",
        )

        # Add "foobar" as a compute keyword
        modified_config = {**CLASSIFY_CONFIG}
        modified_config["classifications"] = {
            **CLASSIFY_CONFIG["classifications"],
            "compute": {
                **CLASSIFY_CONFIG["classifications"]["compute"],
                "keywords": [
                    *CLASSIFY_CONFIG["classifications"]["compute"]["keywords"],
                    "foobar",
                ],
            },
        }
        classifier2 = DeterministicClassifier(modified_config)
        result2 = classifier2.classify(
            entity_name="FoobarProcessor",
            methods=[{"name": "do_foobar"}, {"name": "run_foobar"}],
            docstring="Processes foobar data using foobar algorithm.",
        )

        # With foobar as compute keyword, overall confidence should increase
        # (proves config change affected classification behavior)
        assert result2.confidence > result1.confidence
