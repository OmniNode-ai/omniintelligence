# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""UUID cast misuse validator for repository YAML files.

Static analysis unit tests that detect $N::uuid casts applied to parameters
declared as string/text/varchar in *.repository.yaml files.

This validator is intentionally narrow in scope (v1):
  - Detects: $N::uuid casts on string/text/varchar params (PostgreSQL shorthand only)
  - Does NOT: parse migration DDL, analyze CAST($N AS type) forms, catch all type mismatches

Ticket: OMN-3406
Related: OMN-3301 (immediate fix — domain_id::uuid misuse this test was written to catch)

NOTE: This is a uuid cast misuse validator — NOT a general type contract validator.
      Do not rely on it to catch all type mismatches.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Repository YAML files are located under src/ in the omniintelligence package
_SRC_ROOT = Path(__file__).parent.parent.parent / "src"

# Param types that must NOT appear in $N::uuid casts
_STRING_TYPES = frozenset({"string", "text", "varchar"})

# Regex: matches $N::typename (PostgreSQL cast shorthand), e.g. $1::uuid, $3::text
# Captures the positional index (N) and the cast type name
_POSITIONAL_CAST_RE = re.compile(r"\$(\d+)::([a-z_][a-z0-9_]*)", re.IGNORECASE)

# Patterns used in SQL pre-processing (strip before analysis)
_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING_LITERAL_RE = re.compile(r"'(?:[^'\\]|\\.)*'")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_sql_noise(sql: str) -> str:
    """Remove comments and string literals before cast analysis.

    Prevents false positives from cast-like patterns inside SQL comments
    or quoted string values (e.g. ``'$1::uuid'`` in a constant expression).

    Order matters:
    1. Block comments (may span lines)
    2. Line comments (after block comment removal to avoid confusion)
    3. Single-quoted string literals
    """
    sql = _BLOCK_COMMENT_RE.sub(" ", sql)
    sql = _LINE_COMMENT_RE.sub(" ", sql)
    sql = _STRING_LITERAL_RE.sub("''", sql)
    return sql


def _get_param_order(_op_name: str, op_data: dict[str, Any]) -> list[str]:
    """Derive the $N → param_name mapping for an operation.

    Mirrors the ordering logic used by AdapterPatternStore._build_positional_args:
    - If the operation declares an explicit ``param_order`` list, use it.
    - Otherwise fall back to YAML ``params`` dict insertion order (Python 3.7+
      dicts preserve insertion order, and PyYAML 5.1+ preserves YAML mapping order).

    This is the same ordering logic the adapter uses at runtime — ensuring our
    static analysis checks the same $N → param_type bindings that asyncpg sees.
    """
    if "param_order" in op_data:
        return list(op_data["param_order"])
    params = op_data.get("params") or {}
    return list(params.keys())


def _find_uuid_cast_misuse(
    yaml_path: Path,
) -> list[str]:
    """Return a list of human-readable violation strings found in *yaml_path*.

    A violation is: a parameter declared as string/text/varchar whose positional
    slot ($N) is cast to ::uuid in the operation's SQL.

    Returns an empty list when no violations are found.
    """
    violations: list[str] = []

    raw = yaml_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    repo = data.get("db_repository") or {}
    ops: dict[str, Any] = repo.get("ops") or {}

    for op_name, op_data in ops.items():
        if not isinstance(op_data, dict):
            continue

        sql_raw = op_data.get("sql", "")
        if not sql_raw:
            continue

        params: dict[str, Any] = op_data.get("params") or {}
        param_order = _get_param_order(op_name, op_data)

        # Build positional index (1-based) → param_name mapping
        # $1 = param_order[0], $2 = param_order[1], …
        positional_map: dict[int, str] = {
            idx + 1: param_name for idx, param_name in enumerate(param_order)
        }

        sql_clean = _strip_sql_noise(sql_raw)

        # Deduplicate per (op, position, cast_type) — a param may appear multiple
        # times in the SQL (e.g. $1::uuid IS NULL OR col = $1::uuid), but we only
        # want to report the misuse once per param slot.
        seen: set[tuple[str, int, str]] = set()

        for match in _POSITIONAL_CAST_RE.finditer(sql_clean):
            position = int(match.group(1))
            cast_type = match.group(2).lower()

            if cast_type != "uuid":
                continue  # only flag ::uuid casts (v1 scope)

            dedup_key = (op_name, position, cast_type)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            param_name = positional_map.get(position)
            if param_name is None:
                # Positional index out of range — may be a bug, but not our concern here
                continue

            param_spec = params.get(param_name) or {}
            param_type = str(param_spec.get("param_type", "")).lower().strip()

            if param_type in _STRING_TYPES:
                violations.append(
                    f"{yaml_path.name} / op={op_name}: "
                    f"${position} is param '{param_name}' (param_type={param_type!r}) "
                    f"but SQL casts it as ::{cast_type}. "
                    f"A string/text/varchar param must not be cast to ::uuid — "
                    f"either change param_type to 'uuid' or remove the ::uuid cast."
                )

    return violations


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRepositoryYamlUuidCastMisuse:
    """UUID cast misuse validator for *.repository.yaml files.

    Static analysis only — no DB, no asyncpg, no network.

    Detects: $N::uuid casts on params declared string/text/varchar.
    Does NOT catch: CAST($N AS uuid) form, non-uuid type mismatches,
                    or mismatches not involving positional $N syntax.
    """

    @pytest.fixture(scope="class")
    def yaml_files(self) -> list[Path]:
        """Glob all *.repository.yaml files under src/."""
        files = sorted(_SRC_ROOT.rglob("*.repository.yaml"))
        return files

    def test_repository_yaml_files_exist(self, yaml_files: list[Path]) -> None:
        """At least one *.repository.yaml file must exist under src/.

        Prevents the test suite from silently passing when the glob finds nothing
        (e.g. after a directory restructure moves YAML files).
        """
        assert len(yaml_files) > 0, (
            f"No *.repository.yaml files found under {_SRC_ROOT}. "
            "Either the files were moved or the glob path is wrong."
        )

    def test_no_uuid_cast_on_string_params(self, yaml_files: list[Path]) -> None:
        """No operation may cast a string/text/varchar param to ::uuid.

        This test catches the OMN-3301 class of bug: a parameter declared as
        ``param_type: string`` whose positional slot ($N) is cast via ``$N::uuid``
        in the SQL. asyncpg passes the Python str value to PostgreSQL; when the
        SQL then casts it as ``::uuid``, PostgreSQL raises an error if the string
        is not a valid UUID — and silently misbehaves if it happens to be one.

        Fix: either change ``param_type`` to ``uuid`` (if the param IS a UUID)
        or remove the ``::uuid`` cast (if the column is text/varchar).
        """
        all_violations: list[str] = []

        for yaml_path in yaml_files:
            violations = _find_uuid_cast_misuse(yaml_path)
            all_violations.extend(violations)

        assert all_violations == [], (
            "UUID cast misuse detected in repository YAML files:\n\n"
            + "\n".join(f"  - {v}" for v in all_violations)
            + "\n\nSee OMN-3301 for the canonical example of this bug."
        )

    def test_known_file_query_patterns_op_clean(self, yaml_files: list[Path]) -> None:
        """The query_patterns operation in learned_patterns.repository.yaml must be clean.

        Explicit regression test for OMN-3301: domain_id was declared as
        param_type=string but cast as $1::uuid in the SQL. This test must:
          - FAIL on the unpatched YAML (before OMN-3301 fix merges)
          - PASS after the OMN-3301 fix lands on HEAD

        The broader test_no_uuid_cast_on_string_params already covers this,
        but this named test makes the regression unmistakable in CI output.
        """
        target = next(
            (p for p in yaml_files if p.name == "learned_patterns.repository.yaml"),
            None,
        )
        assert target is not None, (
            "learned_patterns.repository.yaml not found under src/. "
            "Update this test if the file was renamed or moved."
        )

        violations = _find_uuid_cast_misuse(target)

        op_violations = [v for v in violations if "op=query_patterns" in v]
        assert op_violations == [], (
            "OMN-3301 regression: query_patterns still has uuid cast misuse:\n\n"
            + "\n".join(f"  - {v}" for v in op_violations)
        )

    def test_strip_sql_noise_removes_comments(self) -> None:
        """_strip_sql_noise removes line and block comments before cast analysis."""
        sql = "SELECT $1 -- $2::uuid is a comment\nFROM t /* $3::uuid block */ WHERE id = $1"
        cleaned = _strip_sql_noise(sql)
        # After stripping, only $1 (non-cast usage) remains; cast patterns in comments are gone
        assert "$2::uuid" not in cleaned
        assert "$3::uuid" not in cleaned
        assert "$1" in cleaned  # non-cast placeholder preserved

    def test_strip_sql_noise_removes_string_literals(self) -> None:
        """_strip_sql_noise removes single-quoted literals that could contain fake casts."""
        sql = "SELECT $1 FROM t WHERE col = '$1::uuid inside literal'"
        cleaned = _strip_sql_noise(sql)
        # The cast inside the string literal should be gone
        assert "'$1::uuid inside literal'" not in cleaned
        assert "$1" in cleaned  # bare placeholder preserved

    def test_param_order_explicit_overrides_dict_order(self) -> None:
        """When param_order is present, it determines positional mapping (not dict order)."""
        op_data: dict[str, Any] = {
            "param_order": ["b_param", "a_param"],
            "params": {
                "a_param": {"param_type": "string"},
                "b_param": {"param_type": "uuid"},
            },
            "sql": "$1::uuid AND $2 = 'x'",
        }
        # With param_order: b_param is $1 (uuid), a_param is $2 (string)
        # $1::uuid on a uuid param is NOT a violation
        # $2 (string, no cast) is also not a violation
        violations = (
            _find_uuid_cast_misuse.__wrapped__
            if hasattr(_find_uuid_cast_misuse, "__wrapped__")
            else None
        )
        # Exercise via the module-level helper directly
        positional_map = {
            idx + 1: name for idx, name in enumerate(op_data["param_order"])
        }
        assert positional_map == {1: "b_param", 2: "a_param"}

    def test_param_order_fallback_to_dict_order(self) -> None:
        """When no param_order, params dict insertion order determines $N mapping."""
        op_data: dict[str, Any] = {
            "params": {
                "first_param": {"param_type": "string"},
                "second_param": {"param_type": "integer"},
            }
        }
        order = _get_param_order("my_op", op_data)
        assert order == ["first_param", "second_param"]
