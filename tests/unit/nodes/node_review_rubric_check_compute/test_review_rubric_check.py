# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Review rubric file format, loader with token budget, and check node (OMN-21186).

AC1: the loader reads a rubric file in the defined format and refuses a malformed
one by name. AC2: a rubric over the token budget is refused with a typed refusal.
AC3: the check node reports a pass or a named refusal for a rubric file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import yaml

from omniintelligence.nodes.node_review_rubric_check_compute.handlers.handler_review_rubric_check import (
    handle,
)
from omniintelligence.nodes.node_review_rubric_check_compute.handlers.handler_review_rubric_loader import (
    compute_content_hash,
    load_review_rubric,
)
from omniintelligence.nodes.node_review_rubric_check_compute.models.enum_review_rubric_check_outcome import (
    EnumReviewRubricCheckOutcome,
)
from omniintelligence.nodes.node_review_rubric_check_compute.models.enum_review_rubric_refusal import (
    EnumReviewRubricRefusal,
)
from omniintelligence.nodes.node_review_rubric_check_compute.models.model_review_rubric_check_request import (
    ModelReviewRubricCheckRequest,
)

FIXTURES = Path(__file__).parent / "fixtures"
GENEROUS_BUDGET = 4000


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _sealed(mapping: dict[str, Any]) -> str:
    """Rubric text whose content_hash matches its content."""
    sealed = {**mapping, "content_hash": compute_content_hash(mapping)}
    return yaml.safe_dump(sealed, sort_keys=False)


def _valid_mapping() -> dict[str, Any]:
    return yaml.safe_load(_read("review_rubric.valid.v1.yaml"))


@pytest.mark.unit
class TestLoaderFormat:
    def test_valid_fixture_loads(self) -> None:
        loaded = load_review_rubric(
            _read("review_rubric.valid.v1.yaml"), token_budget=GENEROUS_BUDGET
        )
        assert loaded.refusal is None
        assert loaded.rubric is not None
        assert loaded.rubric.version == 2
        assert loaded.rubric.parent_version == 1
        assert [r.category for r in loaded.rubric.rules] == [
            "null-handling",
            "dead-code",
        ]
        assert loaded.rubric.rules[0].support.truth.real == 7
        assert loaded.rubric.rules[0].support.actionability.not_acted_on == 2
        assert loaded.rubric.rules[0].repositories == ("omniintelligence", "omnimarket")
        assert 0 < loaded.token_count <= GENEROUS_BUDGET

    def test_malformed_fixture_is_refused_by_name_and_field(self) -> None:
        loaded = load_review_rubric(
            _read("review_rubric.malformed.v1.yaml"), token_budget=GENEROUS_BUDGET
        )
        assert loaded.rubric is None
        assert loaded.refusal is not None
        assert loaded.refusal.code is EnumReviewRubricRefusal.MALFORMED
        assert "rules.0.instruction" in loaded.refusal.message

    def test_text_that_is_not_yaml_is_refused(self) -> None:
        loaded = load_review_rubric("rules: [unclosed", token_budget=GENEROUS_BUDGET)
        assert loaded.refusal is not None
        assert loaded.refusal.code is EnumReviewRubricRefusal.NOT_YAML

    def test_yaml_that_is_not_a_mapping_is_refused(self) -> None:
        loaded = load_review_rubric("- a\n- b\n", token_budget=GENEROUS_BUDGET)
        assert loaded.refusal is not None
        assert loaded.refusal.code is EnumReviewRubricRefusal.NOT_A_MAPPING

    def test_unknown_schema_version_is_refused(self) -> None:
        mapping = {**_valid_mapping(), "schema_version": "review_rubric.v9"}
        loaded = load_review_rubric(_sealed(mapping), token_budget=GENEROUS_BUDGET)
        assert loaded.refusal is not None
        assert loaded.refusal.code is EnumReviewRubricRefusal.UNSUPPORTED_SCHEMA_VERSION

    def test_unknown_key_is_refused_naming_it(self) -> None:
        mapping = {**_valid_mapping(), "severity": "high"}
        loaded = load_review_rubric(_sealed(mapping), token_budget=GENEROUS_BUDGET)
        assert loaded.refusal is not None
        assert loaded.refusal.code is EnumReviewRubricRefusal.MALFORMED
        assert "severity" in loaded.refusal.message

    def test_a_rule_without_repositories_is_refused(self) -> None:
        mapping = _valid_mapping()
        mapping["rules"][0]["repositories"] = []
        loaded = load_review_rubric(_sealed(mapping), token_budget=GENEROUS_BUDGET)
        assert loaded.refusal is not None
        assert loaded.refusal.code is EnumReviewRubricRefusal.MALFORMED
        assert "rules.0.repositories" in loaded.refusal.message

    def test_a_parent_version_not_below_the_version_is_refused(self) -> None:
        mapping = {**_valid_mapping(), "parent_version": 2}
        loaded = load_review_rubric(_sealed(mapping), token_budget=GENEROUS_BUDGET)
        assert loaded.refusal is not None
        assert loaded.refusal.code is EnumReviewRubricRefusal.MALFORMED
        assert "parent_version" in loaded.refusal.message

    def test_unquoted_false_key_is_refused_as_malformed(self) -> None:
        text = _read("review_rubric.valid.v1.yaml").replace("false_finding:", "false:")
        loaded = load_review_rubric(text, token_budget=GENEROUS_BUDGET)
        assert loaded.refusal is not None
        assert loaded.refusal.code is EnumReviewRubricRefusal.MALFORMED

    def test_negative_support_count_is_refused(self) -> None:
        mapping = _valid_mapping()
        mapping["rules"][1]["support"]["truth"]["false_finding"] = -1
        loaded = load_review_rubric(_sealed(mapping), token_budget=GENEROUS_BUDGET)
        assert loaded.refusal is not None
        assert loaded.refusal.code is EnumReviewRubricRefusal.MALFORMED
        assert "rules.1.support.truth.false_finding" in loaded.refusal.message


@pytest.mark.unit
class TestContentHash:
    def test_valid_fixture_hash_matches_its_content(self) -> None:
        mapping = _valid_mapping()
        assert mapping["content_hash"] == compute_content_hash(mapping)

    def test_hash_ignores_the_stored_hash_and_key_order(self) -> None:
        mapping = _valid_mapping()
        reordered = dict(reversed(list(mapping.items())))
        assert compute_content_hash(reordered) == compute_content_hash(mapping)

    def test_hash_changes_with_the_content(self) -> None:
        mapping = _valid_mapping()
        changed = {**mapping, "hints": ["something else"]}
        assert compute_content_hash(changed) != compute_content_hash(mapping)

    def test_edited_content_with_a_stale_hash_is_refused(self) -> None:
        mapping = _valid_mapping()
        mapping["rules"][0]["instruction"] = "Edited after the hash was frozen."
        loaded = load_review_rubric(
            yaml.safe_dump(mapping, sort_keys=False), token_budget=GENEROUS_BUDGET
        )
        assert loaded.refusal is not None
        assert loaded.refusal.code is EnumReviewRubricRefusal.CONTENT_HASH_MISMATCH


@pytest.mark.unit
class TestTokenBudget:
    def test_rubric_over_budget_is_refused_with_typed_refusal(self) -> None:
        mapping = _valid_mapping()
        mapping["rules"][0]["instruction"] = "word " * 500
        text = _sealed(mapping)
        loaded = load_review_rubric(text, token_budget=GENEROUS_BUDGET)
        assert loaded.refusal is None
        budget = loaded.token_count - 1
        refused = load_review_rubric(text, token_budget=budget)
        assert refused.rubric is None
        assert refused.refusal is not None
        assert refused.refusal.code is EnumReviewRubricRefusal.OVER_BUDGET
        assert refused.token_count == loaded.token_count
        assert str(budget) in refused.refusal.message

    def test_rubric_exactly_at_budget_loads(self) -> None:
        text = _read("review_rubric.valid.v1.yaml")
        count = load_review_rubric(text, token_budget=GENEROUS_BUDGET).token_count
        at_budget = load_review_rubric(text, token_budget=count)
        assert at_budget.refusal is None
        assert at_budget.token_count == count

    def test_budget_counts_prompt_text_not_support_metadata(self) -> None:
        mapping = _valid_mapping()
        base = load_review_rubric(_sealed(mapping), token_budget=GENEROUS_BUDGET)
        mapping["rules"][0]["support"]["truth"]["real"] = 99999
        mapping["created_from"].append("label-event-9999")
        bumped = load_review_rubric(_sealed(mapping), token_budget=GENEROUS_BUDGET)
        assert bumped.token_count == base.token_count

    def test_non_positive_budget_is_rejected_by_the_request_model(self) -> None:
        with pytest.raises(ValueError):
            ModelReviewRubricCheckRequest(
                rubric_yaml="x", rubric_source="r.yaml", token_budget=0
            )


@pytest.mark.unit
class TestCheckNode:
    def test_passing_fixture_reports_pass(self) -> None:
        correlation_id = uuid4()
        result = handle(
            ModelReviewRubricCheckRequest(
                rubric_yaml=_read("review_rubric.valid.v1.yaml"),
                rubric_source="fixtures/review_rubric.valid.v1.yaml",
                token_budget=GENEROUS_BUDGET,
                correlation_id=correlation_id,
            )
        )
        assert result.outcome is EnumReviewRubricCheckOutcome.ACCEPTED
        assert result.refusal is None
        assert result.version == 2
        assert result.rule_count == 2
        assert result.content_hash == _valid_mapping()["content_hash"]
        assert 0 < result.token_count <= result.token_budget == GENEROUS_BUDGET
        assert result.rubric_source == "fixtures/review_rubric.valid.v1.yaml"
        assert result.correlation_id == correlation_id

    def test_malformed_fixture_reports_a_named_refusal(self) -> None:
        result = handle(
            ModelReviewRubricCheckRequest(
                rubric_yaml=_read("review_rubric.malformed.v1.yaml"),
                rubric_source="fixtures/review_rubric.malformed.v1.yaml",
                token_budget=GENEROUS_BUDGET,
            )
        )
        assert result.outcome is EnumReviewRubricCheckOutcome.REFUSED
        assert result.refusal is not None
        assert result.refusal.code is EnumReviewRubricRefusal.MALFORMED
        assert "rules.0.instruction" in result.refusal.message
        assert result.version is None
        assert result.rule_count == 0

    def test_over_budget_fixture_reports_a_named_refusal(self) -> None:
        result = handle(
            ModelReviewRubricCheckRequest(
                rubric_yaml=_read("review_rubric.valid.v1.yaml"),
                rubric_source="fixtures/review_rubric.valid.v1.yaml",
                token_budget=5,
            )
        )
        assert result.outcome is EnumReviewRubricCheckOutcome.REFUSED
        assert result.refusal is not None
        assert result.refusal.code is EnumReviewRubricRefusal.OVER_BUDGET
        assert result.token_count > 5
        assert result.token_budget == 5

    def test_refusal_names_the_source(self) -> None:
        result = handle(
            ModelReviewRubricCheckRequest(
                rubric_yaml="- not\n- a mapping\n",
                rubric_source="rubrics/review_rubric.v3.yaml",
                token_budget=GENEROUS_BUDGET,
            )
        )
        assert result.refusal is not None
        assert "rubrics/review_rubric.v3.yaml" in result.refusal.message

    def test_handler_returns_refusal_data_and_never_raises(self) -> None:
        for text in ("", "null", "{", "rules: 7", "schema_version: review_rubric.v1"):
            result = handle(
                ModelReviewRubricCheckRequest(
                    rubric_yaml=text, rubric_source="r.yaml", token_budget=100
                )
            )
            assert result.outcome is EnumReviewRubricCheckOutcome.REFUSED
            assert result.refusal is not None
