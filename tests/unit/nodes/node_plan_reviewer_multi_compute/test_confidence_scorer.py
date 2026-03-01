# SPDX-FileCopyrightText: 2026 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for handler_confidence_scorer.

All DB interactions are mocked.  No real database connection is used.

Ticket: OMN-3291
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.handler_confidence_scorer import (
    ProtocolDBConnection,
    build_equal_weights,
    fetch_accuracy_weights,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_MODELS = list(EnumReviewModel)
_DEFAULT_WEIGHT = 0.5


def _make_row(model_id: str, score: float) -> MagicMock:
    """Build a fake asyncpg row mapping."""
    row = MagicMock()
    row.__getitem__ = MagicMock(
        side_effect=lambda key: model_id if key == "model_id" else score
    )
    return row


def _make_db_conn(rows: list[Any]) -> ProtocolDBConnection:
    """Return a mock DB connection whose fetch() returns *rows*."""
    conn = AsyncMock(spec=ProtocolDBConnection)
    conn.fetch = AsyncMock(return_value=rows)
    return conn  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# build_equal_weights
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildEqualWeights:
    """Tests for build_equal_weights() — no I/O."""

    def test_returns_all_models(self) -> None:
        """Every EnumReviewModel member has a weight entry."""
        weights = build_equal_weights()
        for model in EnumReviewModel:
            assert model in weights, f"Model {model} missing from build_equal_weights()"

    def test_all_weights_are_default(self) -> None:
        """All weights are exactly 0.5."""
        weights = build_equal_weights()
        for model, weight in weights.items():
            assert weight == pytest.approx(0.5), (
                f"Expected 0.5 for {model}, got {weight}"
            )

    def test_returns_exactly_four_entries(self) -> None:
        """Exactly four entries — one per EnumReviewModel."""
        weights = build_equal_weights()
        assert len(weights) == len(EnumReviewModel)

    def test_independent_calls_return_separate_dicts(self) -> None:
        """Two calls return separate dict instances."""
        w1 = build_equal_weights()
        w2 = build_equal_weights()
        assert w1 is not w2


# ---------------------------------------------------------------------------
# fetch_accuracy_weights — no DB connection
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_db_conn_returns_default_weights() -> None:
    """When db_conn=None, all models receive weight 0.5."""
    weights = await fetch_accuracy_weights(None)
    for model in EnumReviewModel:
        assert weights[model] == pytest.approx(0.5)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_db_conn_covers_all_models() -> None:
    """All EnumReviewModel members are present when db_conn=None."""
    weights = await fetch_accuracy_weights(None)
    assert set(weights.keys()) == set(EnumReviewModel)


# ---------------------------------------------------------------------------
# fetch_accuracy_weights — DB returns rows
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_db_rows_update_weights() -> None:
    """Rows returned by DB override the default weight of 0.5."""
    rows = [
        _make_row("qwen3-coder", 0.8),
        _make_row("deepseek-r1", 0.7),
    ]
    conn = _make_db_conn(rows)
    weights = await fetch_accuracy_weights(conn)

    assert weights[EnumReviewModel.QWEN3_CODER] == pytest.approx(0.8)
    assert weights[EnumReviewModel.DEEPSEEK_R1] == pytest.approx(0.7)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_db_rows_absent_models_keep_default() -> None:
    """Models not present in DB rows keep the default weight of 0.5."""
    rows = [
        _make_row("qwen3-coder", 0.9),
    ]
    conn = _make_db_conn(rows)
    weights = await fetch_accuracy_weights(conn)

    # gemini-flash and glm-4 are absent from rows — must stay 0.5.
    assert weights[EnumReviewModel.GEMINI_FLASH] == pytest.approx(0.5)
    assert weights[EnumReviewModel.GLM_4] == pytest.approx(0.5)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_all_models_in_db_updates_all_weights() -> None:
    """When all 4 models have rows, all weights are updated."""
    rows = [
        _make_row("qwen3-coder", 0.9),
        _make_row("deepseek-r1", 0.8),
        _make_row("gemini-flash", 0.7),
        _make_row("glm-4", 0.6),
    ]
    conn = _make_db_conn(rows)
    weights = await fetch_accuracy_weights(conn)

    assert weights[EnumReviewModel.QWEN3_CODER] == pytest.approx(0.9)
    assert weights[EnumReviewModel.DEEPSEEK_R1] == pytest.approx(0.8)
    assert weights[EnumReviewModel.GEMINI_FLASH] == pytest.approx(0.7)
    assert weights[EnumReviewModel.GLM_4] == pytest.approx(0.6)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_all_models_in_db_none_missing_from_result() -> None:
    """Result always contains all four EnumReviewModel members."""
    rows = [
        _make_row("qwen3-coder", 0.9),
        _make_row("deepseek-r1", 0.8),
        _make_row("gemini-flash", 0.7),
        _make_row("glm-4", 0.6),
    ]
    conn = _make_db_conn(rows)
    weights = await fetch_accuracy_weights(conn)

    assert set(weights.keys()) == set(EnumReviewModel)


# ---------------------------------------------------------------------------
# fetch_accuracy_weights — unknown model_id in DB row
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unknown_model_id_in_row_is_skipped() -> None:
    """An unknown model_id in a DB row must be ignored without raising."""
    bad_row = _make_row("unknown-model-xyz", 0.99)
    conn = _make_db_conn([bad_row])
    weights = await fetch_accuracy_weights(conn)

    # Known models should still be 0.5 (default).
    for model in EnumReviewModel:
        assert weights[model] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# fetch_accuracy_weights — DB exception handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_db_exception_falls_back_to_defaults() -> None:
    """When the DB query raises, all weights fall back to 0.5 (no exception propagated)."""
    conn = AsyncMock(spec=ProtocolDBConnection)
    conn.fetch = AsyncMock(side_effect=RuntimeError("connection refused"))

    weights = await fetch_accuracy_weights(conn)

    # Must not raise and must return full default dict.
    for model in EnumReviewModel:
        assert weights[model] == pytest.approx(0.5)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_db_exception_covers_all_models() -> None:
    """Exception path returns all EnumReviewModel members."""
    conn = AsyncMock(spec=ProtocolDBConnection)
    conn.fetch = AsyncMock(side_effect=OSError("db unreachable"))

    weights = await fetch_accuracy_weights(conn)

    assert set(weights.keys()) == set(EnumReviewModel)
