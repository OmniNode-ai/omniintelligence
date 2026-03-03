# SPDX-License-Identifier: Apache-2.0
"""Unit tests for node_tcb_generation_compute."""

import pytest


@pytest.mark.unit
def test_normalize_intent_extracts_repos() -> None:
    """normalize_intent correctly maps keyword signals to repos."""
    from omniintelligence.nodes.node_tcb_generation_compute.handlers.handler_intent_normalizer import (
        normalize_intent,
    )

    result = normalize_intent(
        raw="Add FK validation to the routing model in omnibase_core",
        repo_manifest={
            "omnibase_core": ["routing", "registry", "models"],
            "omniintelligence": ["intent", "pattern", "scoring"],
        },
    )
    assert "omnibase_core" in result.repos
    assert "routing" in result.modules


@pytest.mark.unit
def test_normalize_intent_extracts_risk_tags() -> None:
    """normalize_intent detects migration risk tag from keywords."""
    from omniintelligence.nodes.node_tcb_generation_compute.handlers.handler_intent_normalizer import (
        normalize_intent,
    )

    result = normalize_intent(
        raw="Migrate auth schema to add user_role column",
        repo_manifest={},
    )
    assert "migration" in result.risk_tags


@pytest.mark.unit
def test_score_candidate_returns_float() -> None:
    """score_candidate returns a float between 0 and 1."""
    from omniintelligence.nodes.node_tcb_generation_compute.handlers.handler_candidate_scorer import (
        score_candidate,
    )

    score = score_candidate(
        candidate_path="src/omnibase_core/models/routing/model_route.py",
        intent_modules=["routing"],
        intent_repos=["omnibase_core"],
        days_since_last_commit=3,
    )
    assert 0.0 <= score <= 1.0


@pytest.mark.unit
def test_score_candidate_boosts_recent_changes() -> None:
    """score_candidate gives higher score to recently modified files."""
    from omniintelligence.nodes.node_tcb_generation_compute.handlers.handler_candidate_scorer import (
        score_candidate,
    )

    recent_score = score_candidate(
        candidate_path="src/omnibase_core/models/routing/model_route.py",
        intent_modules=["routing"],
        intent_repos=["omnibase_core"],
        days_since_last_commit=1,
    )
    old_score = score_candidate(
        candidate_path="src/omnibase_core/models/routing/model_route.py",
        intent_modules=["routing"],
        intent_repos=["omnibase_core"],
        days_since_last_commit=60,
    )
    assert recent_score > old_score
