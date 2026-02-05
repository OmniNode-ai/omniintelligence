# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures for success criteria matcher compute tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def simple_data() -> dict:
    """Simple flat data structure for testing."""
    return {"status": "success", "exit_code": 0, "message": "OK"}


@pytest.fixture
def nested_data() -> dict:
    """Nested data structure for testing."""
    return {
        "outputs": {
            "result": "completed",
            "metrics": {"count": 42, "rate": 0.95},
        },
        "metadata": {"version": "1.0"},
    }


@pytest.fixture
def list_data() -> dict:
    """Data structure with lists for testing."""
    return {
        "items": [
            {"name": "first", "value": 1},
            {"name": "second", "value": 2},
            {"name": "third", "value": 3},
        ],
        "tags": ["alpha", "beta", "gamma"],
    }


@pytest.fixture
def mixed_data() -> dict:
    """Complex data structure with mixed types."""
    return {
        "status": "success",
        "results": [
            {"id": "r1", "values": [10, 20, 30]},
            {"id": "r2", "values": [40, 50, 60]},
        ],
        "config": {
            "nested": {"deep": {"value": "found"}},
        },
        "null_value": None,
    }
