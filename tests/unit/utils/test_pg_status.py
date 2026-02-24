# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for omniintelligence.utils.pg_status."""

from __future__ import annotations

import pytest

from omniintelligence.utils.pg_status import parse_pg_status_count


@pytest.mark.unit
class TestParsePgStatusCount:
    """Tests for parse_pg_status_count shared utility."""

    def test_update_with_rows(self) -> None:
        assert parse_pg_status_count("UPDATE 1") == 1

    def test_update_zero(self) -> None:
        assert parse_pg_status_count("UPDATE 0") == 0

    def test_update_large(self) -> None:
        assert parse_pg_status_count("UPDATE 100") == 100

    def test_insert_with_oid(self) -> None:
        assert parse_pg_status_count("INSERT 0 1") == 1

    def test_insert_zero(self) -> None:
        assert parse_pg_status_count("INSERT 0 0") == 0

    def test_insert_multiple(self) -> None:
        assert parse_pg_status_count("INSERT 0 5") == 5

    def test_delete_with_rows(self) -> None:
        assert parse_pg_status_count("DELETE 5") == 5

    def test_delete_zero(self) -> None:
        assert parse_pg_status_count("DELETE 0") == 0

    def test_empty_string(self) -> None:
        assert parse_pg_status_count("") == 0

    def test_none(self) -> None:
        assert parse_pg_status_count(None) == 0

    def test_single_word(self) -> None:
        assert parse_pg_status_count("UPDATE") == 0
        assert parse_pg_status_count("error") == 0

    def test_non_numeric_count(self) -> None:
        assert parse_pg_status_count("UPDATE abc") == 0
        assert parse_pg_status_count("UPDATE foo bar") == 0
