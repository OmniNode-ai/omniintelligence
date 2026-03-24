# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Tests for query_patterns_projection SQL operation and protocol method.

Reference: OMN-6341 (Kafka MessageSizeTooLarge fix)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.mark.unit
class TestQueryPatternsProjectionYAML:
    """Verify the repository YAML defines query_patterns_projection."""

    def test_repository_yaml_has_projection_query(self) -> None:
        """Repository YAML defines query_patterns_projection operation."""
        yaml_path = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "omniintelligence"
            / "repositories"
            / "learned_patterns.repository.yaml"
        )
        with open(yaml_path) as f:
            repo = yaml.safe_load(f)

        ops = repo["db_repository"]["ops"]
        assert "query_patterns_projection" in ops

        sql = ops["query_patterns_projection"]["sql"]
        # Must truncate pattern_signature, not select it raw
        assert "LEFT(" in sql
        assert "pattern_signature" in sql
        # Must select the lightweight fields
        assert "signature_hash" in sql
        assert "domain_id" in sql
        assert "confidence" in sql

    def test_projection_query_has_correct_params(self) -> None:
        """Projection query has min_confidence, limit, offset params."""
        yaml_path = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "omniintelligence"
            / "repositories"
            / "learned_patterns.repository.yaml"
        )
        with open(yaml_path) as f:
            repo = yaml.safe_load(f)

        op = repo["db_repository"]["ops"]["query_patterns_projection"]
        param_order = op["param_order"]
        assert param_order == ["min_confidence", "limit", "offset"]


@pytest.mark.unit
class TestQueryPatternsProjectionProtocol:
    """Verify the protocol declares query_patterns_projection."""

    def test_protocol_has_query_patterns_projection(self) -> None:
        """ProtocolPatternQueryStore declares query_patterns_projection."""
        from omniintelligence.protocols import ProtocolPatternQueryStore

        assert hasattr(ProtocolPatternQueryStore, "query_patterns_projection")
