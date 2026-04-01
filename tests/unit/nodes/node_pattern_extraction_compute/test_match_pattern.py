# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Test pattern matching against AST extraction output."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_extract_ast import (
    extract_entities_from_source,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_match_pattern import (
    match_pattern_role,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_pattern_definition import (
    ModelPatternRole,
)


def _omni_home() -> Path:
    """Resolve omni_home root."""
    env = os.environ.get("OMNI_HOME")
    if env:
        return Path(env)
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "omnibase_core").is_dir() and (p / "omniintelligence").is_dir():
            return p
        p = p.parent
    raise RuntimeError("Cannot resolve omni_home root.")


OMNI_HOME = _omni_home()

COMPUTE_ROLE = ModelPatternRole(
    role_name="compute",
    base_class="NodeCompute",
    distinguishing_mixin="MixinHandlerRouting",
    required=True,
    description="Pure computation",
)

EFFECT_ROLE = ModelPatternRole(
    role_name="effect",
    base_class="NodeEffect",
    distinguishing_mixin="MixinEffectExecution",
    required=True,
    description="External I/O",
)


@pytest.mark.unit
class TestMatchPatternRole:
    """Match a pattern role against extracted entities."""

    def test_compute_node_matches_compute_role(self) -> None:
        """A real compute node file matches the compute role."""
        node_path = (
            OMNI_HOME
            / "omniintelligence"
            / "src"
            / "omniintelligence"
            / "nodes"
            / "node_quality_scoring_compute"
            / "node.py"
        )
        source = node_path.read_text()
        result = extract_entities_from_source(
            source,
            file_path="src/omniintelligence/nodes/node_quality_scoring_compute/node.py",
            source_repo="omniintelligence",
        )

        matches = match_pattern_role(COMPUTE_ROLE, result.entities)
        assert len(matches) >= 1
        assert matches[0].entity_name == "NodeQualityScoringCompute"

    def test_compute_node_does_not_match_effect_role(self) -> None:
        """A compute node does NOT match the effect role."""
        node_path = (
            OMNI_HOME
            / "omniintelligence"
            / "src"
            / "omniintelligence"
            / "nodes"
            / "node_quality_scoring_compute"
            / "node.py"
        )
        source = node_path.read_text()
        result = extract_entities_from_source(
            source,
            file_path="src/omniintelligence/nodes/node_quality_scoring_compute/node.py",
            source_repo="omniintelligence",
        )

        matches = match_pattern_role(EFFECT_ROLE, result.entities)
        assert len(matches) == 0

    def test_effect_node_matches_effect_role(self) -> None:
        """A real effect node file matches the effect role."""
        node_path = (
            OMNI_HOME
            / "omniintelligence"
            / "src"
            / "omniintelligence"
            / "nodes"
            / "node_pattern_storage_effect"
            / "node.py"
        )
        source = node_path.read_text()
        result = extract_entities_from_source(
            source,
            file_path="src/omniintelligence/nodes/node_pattern_storage_effect/node.py",
            source_repo="omniintelligence",
        )

        matches = match_pattern_role(EFFECT_ROLE, result.entities)
        assert len(matches) >= 1
