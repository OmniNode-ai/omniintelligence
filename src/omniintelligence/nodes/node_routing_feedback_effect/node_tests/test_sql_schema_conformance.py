# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The routing-feedback upsert may only name columns the migrated table has.

Migration 018 dropped ``outcome`` from ``routing_feedback_scores``. The columns
here are replayed from the repository's own migration files (014 creates the
table, 018 adds and drops columns), so the check runs on every runner and does
not depend on a database.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from omniintelligence.nodes.node_routing_feedback_effect.handlers.handler_routing_feedback import (
    SQL_UPSERT_ROUTING_FEEDBACK,
)

_MIGRATIONS = (
    Path(__file__).resolve().parents[5] / "deployment" / "database" / "migrations"
)
_TABLE = "routing_feedback_scores"


def _strip_sql_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def _migrated_columns() -> set[str]:
    """Replay migrations 014 and 018 and return the final column set."""
    create = _strip_sql_comments(
        (_MIGRATIONS / "014_create_routing_feedback_scores.sql").read_text()
    )
    body = re.search(
        rf"CREATE TABLE IF NOT EXISTS {_TABLE}\s*\((.*?)\n\);", create, re.DOTALL
    )
    assert body is not None, "014 must create the table"
    columns: set[str] = set()
    for line in body.group(1).splitlines():
        match = re.match(r"\s*([a-z_]+)\s+[A-Z]", line)
        if match and match.group(1) not in {"constraint", "unique"}:
            columns.add(match.group(1))

    alter = _strip_sql_comments(
        (
            _MIGRATIONS / "018_migrate_routing_feedback_scores_outcome_raw.sql"
        ).read_text()
    )
    columns.update(re.findall(r"ADD COLUMN IF NOT EXISTS\s+([a-z_]+)", alter))
    columns.difference_update(re.findall(r"DROP COLUMN IF EXISTS\s+([a-z_]+)", alter))
    # DROP COLUMN IF EXISTS a, DROP COLUMN IF EXISTS b — the regex above takes each.
    return columns


def _upsert_columns() -> set[str]:
    insert = re.search(
        rf"INSERT INTO {_TABLE}\s*\((.*?)\)\s*VALUES",
        SQL_UPSERT_ROUTING_FEEDBACK,
        re.DOTALL,
    )
    assert insert is not None, "upsert must name its insert columns"
    named = {c.strip() for c in insert.group(1).split(",") if c.strip()}
    named.update(
        re.findall(r"^\s*([a-z_]+)\s*=\s*EXCLUDED\.", SQL_UPSERT_ROUTING_FEEDBACK, re.M)
    )
    return named


@pytest.mark.unit
def test_migration_replay_positive_control() -> None:
    """The replay sees the table as 018 leaves it, so a zero here is meaningful."""
    columns = _migrated_columns()
    assert {"id", "session_id", "processed_at", "agent_selected"} <= columns
    assert "outcome" not in columns, "018 drops outcome; replay must apply the drop"
    assert "correlation_id" not in columns


@pytest.mark.unit
def test_upsert_only_names_columns_the_migrated_table_has() -> None:
    unknown = _upsert_columns() - _migrated_columns()
    assert not unknown, f"upsert names columns absent from {_TABLE}: {sorted(unknown)}"
