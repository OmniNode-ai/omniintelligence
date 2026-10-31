# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""OMN-21790: the slice names no model and no path; the overlay and fixtures supply them."""

from __future__ import annotations

from pathlib import Path

import pytest

from omniintelligence.models.llm_routing import (
    DEFAULT_MODEL_NAME,
    ModelLlmRoutingSettings,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models import (
    EnumReviewModel,
)

pytestmark = pytest.mark.unit

_REPOSITORY = Path(__file__).resolve().parents[3]
_SLICE_PATHS = (
    "src/omniintelligence/adapters/plan_reviewer_gemini_client.py",
    "src/omniintelligence/adapters/plan_reviewer_z_ai_client.py",
    "src/omniintelligence/code_projection/__main__.py",
    "src/omniintelligence/code_projection/context_serving/live.py",
    "src/omniintelligence/nodes/node_crawl_scheduler_effect/node_tests/test_governance_invariants.py",
    "src/omniintelligence/nodes/node_plan_reviewer_multi_compute/models/enum_review_model.py",
)


def test_plan_reviewer_models_default_to_the_placeholder() -> None:
    settings = ModelLlmRoutingSettings(_env_file=None)
    assert settings.plan_reviewer_gemini_model == DEFAULT_MODEL_NAME
    assert settings.plan_reviewer_z_ai_model == DEFAULT_MODEL_NAME


def test_plan_reviewer_models_come_from_the_overlay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OMNIINTELLIGENCE_PLAN_REVIEWER_GEMINI_MODEL", "gemini-slot")
    monkeypatch.setenv("OMNIINTELLIGENCE_PLAN_REVIEWER_Z_AI_MODEL", "z-ai-slot")
    settings = ModelLlmRoutingSettings(_env_file=None)
    assert settings.plan_reviewer_gemini_model == "gemini-slot"
    assert settings.plan_reviewer_z_ai_model == "z-ai-slot"


def test_review_slots_are_not_model_names() -> None:
    assert {member.value for member in EnumReviewModel} == {
        "code-drafter",
        "deep-reasoner",
        "fast-reviewer",
        "tiebreaker",
    }


def test_slice_paths_hold_no_literal_path_or_model_name() -> None:
    from omnibase_core.validation.validator_contracts_and_di import (
        ValidatorContractsAndDi,
    )

    paths = [_REPOSITORY / relative for relative in _SLICE_PATHS]
    assert all(path.is_file() for path in paths), "missing slice path"
    result = ValidatorContractsAndDi().validate(paths)
    assert result.metadata is not None
    assert result.metadata.files_processed == len(paths), "incomplete scan"
    findings = [
        i
        for i in result.issues
        if i.rule_name in {"literal_path", "literal_model_name", "unparseable_file"}
    ]
    assert not findings, findings
