# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Canary tests for bus_local Kafka isolation (OMN-3477).

Verifies that pytest_configure/pytest_unconfigure hooks in conftest.py
correctly set KAFKA_BOOTSTRAP_SERVERS to bus_local (localhost:19092) for
all integration tests.
"""

from __future__ import annotations

import os

import pytest


@pytest.mark.integration
def test_kafka_integration_env_is_bus_local() -> None:
    """Guard: integration tests must always use bus_local (localhost:19092)."""
    assert os.environ.get("KAFKA_BOOTSTRAP_SERVERS") == "localhost:19092"
    assert "localhost:19092" in os.environ.get("KAFKA_BROKER_ALLOWLIST", "")
