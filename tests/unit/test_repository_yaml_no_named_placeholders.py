# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Regression test: no :named SQL placeholders in repository YAML files.

asyncpg requires $N positional syntax. Any :named placeholders in SQL
operations will throw PostgresSyntaxError at runtime.

Ticket: OMN-3644 (bulk conversion)
Related: OMN-3592 (initial upsert_pattern fix)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

# Repository YAML files are located under src/ in the omniintelligence package
_SRC_ROOT = Path(__file__).parent.parent.parent / "src"

# Regex matching :named placeholders in SQL — e.g. :pattern_id, :limit, :domain_id
# Must start with : followed by a letter or underscore, then word characters.
# Excludes PostgreSQL type casts (::type) by requiring NO leading colon.
_NAMED_PLACEHOLDER_RE = re.compile(r"(?<!:):([a-zA-Z_]\w*)")

# Patterns that appear in SQL but are NOT named placeholders:
# - PostgreSQL type casts like ::text, ::float, ::uuid (double colon)
# - These are already excluded by the negative lookbehind (?<!:)


def _strip_sql_noise(sql: str) -> str:
    """Remove comments and string literals before placeholder analysis."""
    # Block comments
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    # Line comments
    sql = re.sub(r"--[^\n]*", " ", sql)
    # Single-quoted string literals
    sql = re.sub(r"'(?:[^'\\]|\\.)*'", "''", sql)
    return sql


def _find_named_placeholders(yaml_path: Path) -> list[str]:
    """Return violation strings for any :named placeholders found in SQL ops."""
    violations: list[str] = []

    raw = yaml_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    repo = data.get("db_repository") or {}
    ops: dict = repo.get("ops") or {}

    for op_name, op_data in ops.items():
        if not isinstance(op_data, dict):
            continue

        sql_raw = op_data.get("sql", "")
        if not sql_raw:
            continue

        sql_clean = _strip_sql_noise(sql_raw)

        # Find all :named placeholders
        matches = _NAMED_PLACEHOLDER_RE.findall(sql_clean)
        if matches:
            # Deduplicate while preserving order
            unique = list(dict.fromkeys(matches))
            violations.append(
                f"{yaml_path.name} / op={op_name}: "
                f"found :named placeholders {unique} — "
                f"asyncpg requires $N positional syntax"
            )

    return violations


@pytest.mark.unit
class TestNoNamedPlaceholders:
    """Verify all repository YAML SQL uses $N positional syntax, not :named.

    OMN-3644: asyncpg passes SQL directly to PostgreSQL via
    conn.fetchrow(sql, *args). Named placeholders like :pattern_id are not
    rewritten and will cause PostgresSyntaxError at runtime.
    """

    @pytest.fixture(scope="class")
    def yaml_files(self) -> list[Path]:
        """Glob all *.repository.yaml files under src/."""
        files = sorted(_SRC_ROOT.rglob("*.repository.yaml"))
        return files

    def test_repository_yaml_files_exist(self, yaml_files: list[Path]) -> None:
        """At least one *.repository.yaml file must exist under src/."""
        assert len(yaml_files) > 0, (
            f"No *.repository.yaml files found under {_SRC_ROOT}. "
            "Either the files were moved or the glob path is wrong."
        )

    def test_no_named_placeholders_in_sql(self, yaml_files: list[Path]) -> None:
        """No SQL operation may use :named placeholders.

        All SQL in repository YAML files must use asyncpg $N positional
        syntax. This test catches the OMN-3592 class of bug where :named
        placeholders are used instead of $1, $2, etc.
        """
        all_violations: list[str] = []

        for yaml_path in yaml_files:
            violations = _find_named_placeholders(yaml_path)
            all_violations.extend(violations)

        assert all_violations == [], (
            "Named SQL placeholders (:param) detected in repository YAML files.\n"
            "asyncpg requires $N positional syntax.\n\n"
            + "\n".join(f"  - {v}" for v in all_violations)
            + "\n\nSee OMN-3644 for the conversion pattern."
        )

    def test_learned_patterns_specifically(self, yaml_files: list[Path]) -> None:
        """Explicit regression test for learned_patterns.repository.yaml.

        This is the file that was the subject of OMN-3592 and OMN-3644.
        """
        target = next(
            (p for p in yaml_files if p.name == "learned_patterns.repository.yaml"),
            None,
        )
        assert target is not None, (
            "learned_patterns.repository.yaml not found under src/. "
            "Update this test if the file was renamed or moved."
        )

        violations = _find_named_placeholders(target)
        assert violations == [], (
            "OMN-3644 regression: learned_patterns.repository.yaml still has "
            ":named placeholders:\n\n" + "\n".join(f"  - {v}" for v in violations)
        )

    def test_all_ops_have_param_order(self, yaml_files: list[Path]) -> None:
        """Every operation with params should have an explicit param_order field.

        param_order makes the $N mapping explicit and prevents bugs from
        relying on YAML dict insertion order.
        """
        violations: list[str] = []

        for yaml_path in yaml_files:
            raw = yaml_path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)

            repo = data.get("db_repository") or {}
            ops: dict = repo.get("ops") or {}

            for op_name, op_data in ops.items():
                if not isinstance(op_data, dict):
                    continue

                params = op_data.get("params") or {}
                if not params:
                    continue  # No params = no positional mapping needed

                if "param_order" not in op_data:
                    violations.append(
                        f"{yaml_path.name} / op={op_name}: "
                        f"has {len(params)} params but no param_order field"
                    )

        assert violations == [], (
            "Operations with params must declare explicit param_order:\n\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
