# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""E2E integration tests for the pattern learning pipeline.

This package contains end-to-end tests that verify the complete pattern
learning workflow:
    - Pattern learning compute (feature extraction, clustering, scoring)
    - Pattern storage to learned_patterns table (PostgreSQL)
    - Feedback loop updates (session outcomes, rolling metrics)

Test Strategy:
    - Real PostgreSQL: Data integrity verification
    - Real Kafka/Redpanda: Event emission and consumption verification

Reference:
    - OMN-1800: E2E integration tests for pattern learning pipeline
"""
