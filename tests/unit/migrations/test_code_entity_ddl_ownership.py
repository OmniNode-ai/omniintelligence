# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""`code_entities` DDL must not be re-authored in this repository (OMN-15276).

This directory (`deployment/database/migrations/`) feeds the `omniintelligence-migrate`
ECR image. It is **not** what the `.201` docker lanes apply — those mount
`omnibase_infra/docker/migrations/intelligence/` via the `intelligence-migration`
service (`MIGRATIONS_DIR: /migrations/intelligence`).

That mismatch is what made OMN-5765 a false-Done: two conflicting `code_entities`
migrations (`025_code_entities.sql`, `025_create_code_entities.sql`) sat here for four
months, neither ever applied on any lane, while `omniintelligence.schema_migrations`
held 27 identical rows on stability-test and prod ending at
`025_fix_llm_delegation_call_log_date_index`, and both tables were absent from 20/20
databases across both lanes (read-only probe 2026-07-27T23:46Z).

Both files were `CREATE TABLE IF NOT EXISTS`, so re-adding a second definition anywhere
does not fail loudly — the first to sort wins and the other's columns silently never
appear. This test is the loud failure that condition otherwise lacks.

Rationale and the retired-file inventory live in this docstring and in
``RETIRED_MIGRATIONS`` below. The former companion note
(``deployment/database/migrations/CODE_ENTITY_DDL_OWNERSHIP.md``) was removed by
OMN-16612; it only restated what is written here, and OMN-15276 is the durable
record of the decision.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

#: The repo + path that owns this DDL. Kept as a string, not a filesystem probe: this
#: test must fail on its own terms in CI, where the sibling repo is not checked out.
CANONICAL_LOCATION = (
    "omnibase_infra/docker/migrations/intelligence/026_create_code_entities.sql"
)

RETIRED_MIGRATIONS = (
    "deployment/database/migrations/025_code_entities.sql",
    "deployment/database/migrations/025_create_code_entities.sql",
    "deployment/database/migrations/026_create_code_relationships.sql",
    "deployment/database/migrations/027_code_entity_enrichment_part2.sql",
)


def _sql_files() -> list[Path]:
    return [
        path
        for path in REPO_ROOT.rglob("*.sql")
        if ".git" not in path.parts and ".venv" not in path.parts
    ]


@pytest.mark.parametrize("table", ["code_entities", "code_relationships"])
def test_no_sql_file_in_this_repo_creates_the_table(table: str) -> None:
    pattern = re.compile(
        rf"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{table}\b", re.IGNORECASE
    )
    offenders = sorted(
        str(path.relative_to(REPO_ROOT))
        for path in _sql_files()
        if pattern.search(path.read_text(encoding="utf-8"))
    )
    assert not offenders, (
        f"{table} DDL was re-added to this repo in {offenders}. This directory is not "
        f"applied by any .201 lane, so the DDL would read green and provision nothing. "
        f"The canonical definition is {CANONICAL_LOCATION} (OMN-15276)."
    )


def test_no_sql_file_in_this_repo_alters_code_entities() -> None:
    """An ALTER here targets a table this repo no longer creates.

    Under the runners' ``ON_ERROR_STOP=1`` that is a hard migration failure, and
    ``intelligence-api`` depends on the migration service with
    ``service_completed_successfully`` — so it takes the lane down rather than
    degrading quietly. New columns belong in the owning migration.
    """
    pattern = re.compile(r"ALTER\s+TABLE\s+code_entities\b", re.IGNORECASE)
    offenders = sorted(
        str(path.relative_to(REPO_ROOT))
        for path in _sql_files()
        if pattern.search(path.read_text(encoding="utf-8"))
    )
    assert not offenders, (
        f"ALTER TABLE code_entities found in {offenders}; add the column to "
        f"{CANONICAL_LOCATION} instead (OMN-15276)."
    )


@pytest.mark.parametrize("retired", RETIRED_MIGRATIONS)
def test_retired_migration_files_stay_deleted(retired: str) -> None:
    assert not (REPO_ROOT / retired).exists(), (
        f"{retired} was restored. It was retired by OMN-15276; the canonical "
        f"owner of this DDL is {CANONICAL_LOCATION}, and this module's "
        "docstring carries the rationale."
    )


def test_the_025_prefix_is_no_longer_multiply_claimed() -> None:
    migrations = REPO_ROOT / "deployment" / "database" / "migrations"
    claimants = sorted(path.name for path in migrations.glob("025_*.sql"))
    assert claimants == ["025_review_calibration_runs.sql"], (
        f"the 025 prefix is claimed by {claimants}. Sorted order is the apply order, so "
        "a duplicated prefix makes it ambiguous; take the next free number instead of "
        "renumbering an applied migration (the runners key on basename)."
    )
