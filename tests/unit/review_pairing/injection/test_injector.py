# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for Preemptive Pattern Injector.

Tests cover:
- Empty candidates → no injection
- Repo/language/file path prefix filtering
- Ranking by pattern_score descending
- Token budget enforcement (lowest-ranked dropped)
- Constraint block format ([PATTERN CONSTRAINTS] delimiters)
- Top-K limiting
- Reward signals: PREEMPTIVE_AVOIDANCE and REPEATED_VIOLATION
- Reward signal not emitted for patterns not in injected set
- Multiple reward signals in single session

Reference: OMN-2577
"""

from __future__ import annotations

import uuid
from uuid import UUID

import pytest

from omniintelligence.review_pairing.injection import (
    InjectionContext,
    PatternConstraintCandidate,
    PatternInjector,
    RewardSignalType,
)
from omniintelligence.review_pairing.injection.injector import (
    MAX_INJECTION_TOKENS,
    REWARD_AVOIDANCE,
    REWARD_REPEATED_VIOLATION,
    _estimate_tokens,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_candidate(
    *,
    rule_id: str = "ruff:E501",
    constraint: str = "Avoid rule ruff:E501. Lines must not exceed 88 characters.",
    score: float = 0.90,
    repo: str = "OmniNode-ai/omniintelligence",
    language: str = "python",
    file_path_prefix: str = "",
    state: str = "stable",
    pattern_id: UUID | None = None,
) -> PatternConstraintCandidate:
    return PatternConstraintCandidate(
        pattern_id=pattern_id or uuid.uuid4(),
        rule_id=rule_id,
        natural_language_constraint=constraint,
        pattern_score=score,
        repo=repo,
        language=language,
        file_path_prefix=file_path_prefix,
        state=state,
    )


def _make_context(
    *,
    repo: str = "OmniNode-ai/omniintelligence",
    language: str = "python",
    file_path: str = "src/foo/bar.py",
) -> InjectionContext:
    return InjectionContext(repo=repo, language=language, file_path=file_path)


# ---------------------------------------------------------------------------
# Empty candidates
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEmptyCandidates:
    def test_no_candidates_returns_no_injection(self) -> None:
        injector = PatternInjector()
        result = injector.build_injection([], _make_context())
        assert not result.injected
        assert result.constraint_block == ""

    def test_no_candidates_empty_injected_list(self) -> None:
        injector = PatternInjector()
        result = injector.build_injection([], _make_context())
        assert result.patterns_injected == []
        assert result.patterns_truncated == []


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFiltering:
    def test_filters_by_repo(self) -> None:
        injector = PatternInjector()
        candidate = _make_candidate(repo="other-org/other-repo")
        result = injector.build_injection(
            [candidate],
            _make_context(repo="OmniNode-ai/omniintelligence"),
        )
        assert not result.injected

    def test_matches_correct_repo(self) -> None:
        injector = PatternInjector()
        candidate = _make_candidate(repo="OmniNode-ai/omniintelligence")
        result = injector.build_injection(
            [candidate],
            _make_context(repo="OmniNode-ai/omniintelligence"),
        )
        assert result.injected

    def test_filters_by_language(self) -> None:
        injector = PatternInjector()
        candidate = _make_candidate(language="typescript")
        result = injector.build_injection(
            [candidate],
            _make_context(language="python"),
        )
        assert not result.injected

    def test_matches_correct_language(self) -> None:
        injector = PatternInjector()
        candidate = _make_candidate(language="python")
        result = injector.build_injection(
            [candidate],
            _make_context(language="python"),
        )
        assert result.injected

    def test_filters_by_file_path_prefix(self) -> None:
        injector = PatternInjector()
        candidate = _make_candidate(file_path_prefix="src/other/")
        result = injector.build_injection(
            [candidate],
            _make_context(file_path="src/foo/bar.py"),
        )
        assert not result.injected

    def test_matches_file_path_prefix(self) -> None:
        injector = PatternInjector()
        candidate = _make_candidate(file_path_prefix="src/foo/")
        result = injector.build_injection(
            [candidate],
            _make_context(file_path="src/foo/bar.py"),
        )
        assert result.injected

    def test_empty_file_path_prefix_matches_all(self) -> None:
        injector = PatternInjector()
        candidate = _make_candidate(file_path_prefix="")
        result = injector.build_injection(
            [candidate],
            _make_context(file_path="src/anything/bar.py"),
        )
        assert result.injected


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRanking:
    def test_candidates_ranked_by_score_descending(self) -> None:
        injector = PatternInjector()
        low = _make_candidate(
            rule_id="ruff:E501",
            constraint="CONSTRAINT_LOW: Avoid lines over 88 chars.",
            score=0.50,
        )
        high = _make_candidate(
            rule_id="mypy:return-value",
            constraint="CONSTRAINT_HIGH: All functions must have return type annotations.",
            score=0.95,
        )
        mid = _make_candidate(
            rule_id="eslint:no-unused-vars",
            constraint="CONSTRAINT_MID: Remove all unused variables.",
            score=0.75,
        )

        result = injector.build_injection([low, high, mid], _make_context())
        assert result.injected

        # High-score pattern should appear first in block
        block = result.constraint_block
        pos_high = block.find("CONSTRAINT_HIGH")
        pos_mid = block.find("CONSTRAINT_MID")
        pos_low = block.find("CONSTRAINT_LOW")
        assert pos_high < pos_mid < pos_low

    def test_top_k_limits_candidates(self) -> None:
        injector = PatternInjector()
        candidates = [
            _make_candidate(rule_id=f"ruff:E{i:03d}", score=float(i) / 10.0)
            for i in range(20)
        ]
        result = injector.build_injection(candidates, _make_context(), top_k=5)
        assert len(result.patterns_injected) <= 5


# ---------------------------------------------------------------------------
# Token budget
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTokenBudget:
    def test_constraint_block_respects_token_budget(self) -> None:
        injector = PatternInjector()
        # Create many candidates with long constraints
        candidates = [
            _make_candidate(
                rule_id=f"ruff:E{i:03d}",
                constraint="Avoid rule X. " + "This is a very long constraint. " * 10,
                score=float(i) / 10.0,
            )
            for i in range(20)
        ]
        result = injector.build_injection(
            candidates, _make_context(), max_tokens=MAX_INJECTION_TOKENS
        )
        assert result.token_count <= MAX_INJECTION_TOKENS

    def test_truncated_patterns_excluded_from_injected(self) -> None:
        injector = PatternInjector()
        # Very low token budget to force truncation
        candidates = [
            _make_candidate(rule_id=f"ruff:E{i:03d}", score=float(i) / 10.0)
            for i in range(10)
        ]
        result = injector.build_injection(candidates, _make_context(), max_tokens=50)

        # Injected and truncated are disjoint
        injected_set = set(result.patterns_injected)
        truncated_set = set(result.patterns_truncated)
        assert injected_set.isdisjoint(truncated_set)

    def test_lowest_ranked_dropped_first(self) -> None:
        injector = PatternInjector()
        high = _make_candidate(rule_id="mypy:return-value", score=0.95)
        low = _make_candidate(rule_id="ruff:E501", score=0.30)

        result = injector.build_injection([high, low], _make_context(), max_tokens=50)
        # If any is truncated, it should be the low-scored one
        if result.patterns_truncated:
            assert low.pattern_id in result.patterns_truncated

    def test_token_count_in_result_is_accurate(self) -> None:
        injector = PatternInjector()
        candidate = _make_candidate()
        result = injector.build_injection([candidate], _make_context())
        estimated = _estimate_tokens(result.constraint_block)
        assert result.token_count == estimated


# ---------------------------------------------------------------------------
# Constraint block format
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConstraintBlockFormat:
    def test_block_has_header_delimiter(self) -> None:
        injector = PatternInjector()
        result = injector.build_injection([_make_candidate()], _make_context())
        assert "[PATTERN CONSTRAINTS]" in result.constraint_block

    def test_block_has_footer_delimiter(self) -> None:
        injector = PatternInjector()
        result = injector.build_injection([_make_candidate()], _make_context())
        assert "[END PATTERN CONSTRAINTS]" in result.constraint_block

    def test_block_contains_constraint_text(self) -> None:
        injector = PatternInjector()
        constraint = "Avoid rule ruff:E501. Lines must not exceed 88 characters."
        candidate = _make_candidate(constraint=constraint)
        result = injector.build_injection([candidate], _make_context())
        assert constraint in result.constraint_block

    def test_block_numbers_constraints(self) -> None:
        injector = PatternInjector()
        candidates = [
            _make_candidate(rule_id="ruff:E501", score=0.90),
            _make_candidate(rule_id="mypy:return-value", score=0.80),
        ]
        result = injector.build_injection(candidates, _make_context())
        assert "1." in result.constraint_block
        assert "2." in result.constraint_block

    def test_injected_ids_match_patterns_in_block(self) -> None:
        injector = PatternInjector()
        pid = uuid.uuid4()
        candidate = _make_candidate(pattern_id=pid)
        result = injector.build_injection([candidate], _make_context())
        assert pid in result.patterns_injected


# ---------------------------------------------------------------------------
# Reward signals
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRewardSignals:
    def test_repeated_violation_signal_emitted(self) -> None:
        injector = PatternInjector()
        pid = uuid.uuid4()
        candidate = _make_candidate(rule_id="ruff:E501", pattern_id=pid)
        ctx = _make_context()
        session_id = ctx.generation_session_id
        injection_id = uuid.uuid4()

        signals = injector.compute_reward_signals(
            injected_patterns=[pid],
            violated_rule_ids={"ruff:E501"},
            avoided_rule_ids=set(),
            session_id=session_id,
            injection_id=injection_id,
            candidates=[candidate],
        )

        assert len(signals) == 1
        assert signals[0].signal_type == RewardSignalType.REPEATED_VIOLATION
        assert signals[0].reward_value == REWARD_REPEATED_VIOLATION

    def test_preemptive_avoidance_signal_emitted(self) -> None:
        injector = PatternInjector()
        pid = uuid.uuid4()
        candidate = _make_candidate(rule_id="mypy:return-value", pattern_id=pid)
        ctx = _make_context()

        signals = injector.compute_reward_signals(
            injected_patterns=[pid],
            violated_rule_ids=set(),
            avoided_rule_ids={"mypy:return-value"},
            session_id=ctx.generation_session_id,
            injection_id=uuid.uuid4(),
            candidates=[candidate],
        )

        assert len(signals) == 1
        assert signals[0].signal_type == RewardSignalType.PREEMPTIVE_AVOIDANCE
        assert signals[0].reward_value == REWARD_AVOIDANCE

    def test_no_signal_if_rule_neither_violated_nor_avoided(self) -> None:
        injector = PatternInjector()
        pid = uuid.uuid4()
        candidate = _make_candidate(rule_id="ruff:E501", pattern_id=pid)
        ctx = _make_context()

        signals = injector.compute_reward_signals(
            injected_patterns=[pid],
            violated_rule_ids=set(),  # rule neither violated nor historically avoided
            avoided_rule_ids=set(),
            session_id=ctx.generation_session_id,
            injection_id=uuid.uuid4(),
            candidates=[candidate],
        )

        assert signals == []

    def test_no_signal_for_pattern_not_in_injected_set(self) -> None:
        injector = PatternInjector()
        pid1 = uuid.uuid4()
        pid2 = uuid.uuid4()
        c1 = _make_candidate(rule_id="ruff:E501", pattern_id=pid1)
        c2 = _make_candidate(rule_id="mypy:return-value", pattern_id=pid2)

        signals = injector.compute_reward_signals(
            injected_patterns=[pid1],  # only pid1 was injected
            violated_rule_ids={
                "mypy:return-value"
            },  # pid2's rule violated, not injected
            avoided_rule_ids=set(),
            session_id=uuid.uuid4(),
            injection_id=uuid.uuid4(),
            candidates=[c1, c2],
        )

        assert signals == []

    def test_multiple_signals_in_one_session(self) -> None:
        injector = PatternInjector()
        pid1 = uuid.uuid4()
        pid2 = uuid.uuid4()
        c1 = _make_candidate(rule_id="ruff:E501", pattern_id=pid1)
        c2 = _make_candidate(rule_id="mypy:return-value", pattern_id=pid2)
        session_id = uuid.uuid4()
        injection_id = uuid.uuid4()

        signals = injector.compute_reward_signals(
            injected_patterns=[pid1, pid2],
            violated_rule_ids={"ruff:E501"},
            avoided_rule_ids={"mypy:return-value"},
            session_id=session_id,
            injection_id=injection_id,
            candidates=[c1, c2],
        )

        assert len(signals) == 2
        types = {s.signal_type for s in signals}
        assert RewardSignalType.REPEATED_VIOLATION in types
        assert RewardSignalType.PREEMPTIVE_AVOIDANCE in types

    def test_reward_signal_has_correct_ids(self) -> None:
        injector = PatternInjector()
        pid = uuid.uuid4()
        candidate = _make_candidate(rule_id="ruff:E501", pattern_id=pid)
        session_id = uuid.uuid4()
        injection_id = uuid.uuid4()

        signals = injector.compute_reward_signals(
            injected_patterns=[pid],
            violated_rule_ids={"ruff:E501"},
            avoided_rule_ids=set(),
            session_id=session_id,
            injection_id=injection_id,
            candidates=[candidate],
        )

        assert signals[0].generation_session_id == session_id
        assert signals[0].injection_id == injection_id
        assert signals[0].pattern_id == pid
        assert signals[0].rule_id == "ruff:E501"

    def test_empty_injected_patterns_no_signals(self) -> None:
        injector = PatternInjector()
        candidate = _make_candidate(rule_id="ruff:E501")

        signals = injector.compute_reward_signals(
            injected_patterns=[],
            violated_rule_ids={"ruff:E501"},
            avoided_rule_ids=set(),
            session_id=uuid.uuid4(),
            injection_id=uuid.uuid4(),
            candidates=[candidate],
        )

        assert signals == []
