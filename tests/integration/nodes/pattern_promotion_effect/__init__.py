# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Integration tests for pattern_promotion_effect node.

These tests run against the real PostgreSQL database on 192.168.86.200:5436.
They verify that the promotion logic works correctly with actual database
operations, not just mocks.

Prerequisites:
    - PostgreSQL running on 192.168.86.200:5436
    - Database migrations applied (005_create_learned_patterns.sql)
    - POSTGRES_PASSWORD environment variable set

Run with:
    pytest tests/integration/nodes/pattern_promotion_effect -v -m integration
"""

__all__: list[str] = []
