# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Mock asyncpg.Record implementation for testing.

Provides a ``MockRecord`` class that emulates ``asyncpg.Record`` access
patterns so that tests exercising code paths that consume database rows
interact with a realistic stand-in rather than plain dicts.

``asyncpg.Record`` supports:
    - Dict-style access: ``record["column"]`` via ``__getitem__``
    - ``keys()`` method returning column names
    - Iteration over values (``for value in record: ...``)
    - ``len(record)`` returning column count
    - Attribute access for data fields raises ``AttributeError``

Usage:
    from omniintelligence.testing.mock_record import MockRecord

    row = MockRecord(id=uuid4(), status="candidate", confidence=0.85)
    assert row["status"] == "candidate"
    assert list(row.keys()) == ["id", "status", "confidence"]

Reference:
    - asyncpg Record: https://magicstack.github.io/asyncpg/current/api/
"""

from __future__ import annotations

from typing import Any


class MockRecord(dict[str, Any]):
    """Dict subclass that emulates ``asyncpg.Record`` access patterns.

    Extends ``dict[str, Any]`` so it satisfies ``Mapping[str, Any]`` as
    required by ``ProtocolPatternRepository``.  Supports dict-style key
    access (``record["column"]``), ``keys()``, ``len()``, and iteration
    over values -- all of which are inherited from ``dict``.

    Attribute-style access (``record.column``) raises ``AttributeError``
    for data fields, matching real ``asyncpg.Record`` behaviour.  This
    prevents test code from accidentally depending on attribute access
    that would fail against a real database connection.
    """

    def __getattr__(self, name: str) -> Any:
        """Raise AttributeError for data field access, matching asyncpg.Record.

        Real ``asyncpg.Record`` does not support attribute-style access for
        column values.  Accessing ``record.column_name`` raises
        ``AttributeError``.  This mock enforces the same contract so that
        production code is not written against a pattern that only works in
        tests.
        """
        raise AttributeError(
            f"MockRecord has no attribute {name!r}. "
            f"Use record[{name!r}] for column access (asyncpg.Record does "
            f"not support attribute access for data fields)."
        )


__all__ = ["MockRecord"]
