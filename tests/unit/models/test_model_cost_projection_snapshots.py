# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for cost projection snapshot event models."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omniintelligence.models.events import (
    ModelCostByRepoSnapshot,
    ModelCostByRepoSnapshotRow,
    ModelCostSummarySnapshot,
    ModelCostTokenUsageSnapshot,
    ModelCostTokenUsageSnapshotRow,
)

SNAPSHOT_TS = datetime(2026, 4, 29, 12, 34, tzinfo=UTC)


def test_model_cost_summary_snapshot_contract() -> None:
    snapshot = ModelCostSummarySnapshot(
        window="24h",
        total_cost_usd=Decimal("1.250000"),
        total_savings_usd=Decimal("2.500000"),
        total_tokens=3000,
        session_count=2,
        snapshot_timestamp=SNAPSHOT_TS,
    )

    assert snapshot.window == "24h"
    assert snapshot.total_cost_usd == Decimal("1.250000")
    assert snapshot.total_savings_usd == Decimal("2.500000")
    assert snapshot.total_tokens == 3000
    assert snapshot.session_count == 2


def test_model_cost_by_repo_snapshot_contract() -> None:
    snapshot = ModelCostByRepoSnapshot(
        window="7d",
        rows=[
            ModelCostByRepoSnapshotRow(
                repo_name="omnibase_infra",
                cost_usd=Decimal("1.000000"),
                call_count=2,
            ),
            ModelCostByRepoSnapshotRow(
                repo_name=None,
                cost_usd=Decimal("0.500000"),
                call_count=1,
            ),
        ],
        snapshot_timestamp=SNAPSHOT_TS,
    )

    assert snapshot.rows[0].repo_name == "omnibase_infra"
    assert snapshot.rows[1].repo_name is None


def test_model_cost_token_usage_snapshot_contract() -> None:
    snapshot = ModelCostTokenUsageSnapshot(
        window="30d",
        rows=[
            ModelCostTokenUsageSnapshotRow(
                bucket_timestamp=SNAPSHOT_TS,
                model_id="gpt-4.1",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
            )
        ],
        snapshot_timestamp=SNAPSHOT_TS,
    )

    assert snapshot.rows[0].model_id == "gpt-4.1"
    assert snapshot.rows[0].total_tokens == 150


def test_snapshot_models_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ModelCostSummarySnapshot(
            window="24h",
            total_cost_usd=Decimal("1.000000"),
            total_savings_usd=Decimal("0.000000"),
            total_tokens=1,
            session_count=1,
            snapshot_timestamp=SNAPSHOT_TS,
            unexpected=True,
        )


def test_snapshot_models_reject_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        ModelCostByRepoSnapshot(
            window="24h",
            rows=[],
            snapshot_timestamp=datetime(2026, 4, 29, 12, 34),
        )


def test_token_usage_row_rejects_inconsistent_total() -> None:
    with pytest.raises(ValidationError, match="total_tokens must equal"):
        ModelCostTokenUsageSnapshotRow(
            bucket_timestamp=SNAPSHOT_TS,
            model_id="gpt-4.1",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=151,
        )
