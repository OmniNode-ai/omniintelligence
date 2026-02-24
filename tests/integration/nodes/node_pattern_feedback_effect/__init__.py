# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Integration tests for node_pattern_feedback_effect.

These tests verify event consumption from Kafka topics.

PARTIAL BLOCK: Event consumption tests require OMN-1735 (session-outcome emitter).
Contract configuration tests can run now.

Prerequisites:
    - PostgreSQL (configure via POSTGRES_HOST/POSTGRES_PORT env vars)
    - Kafka/Redpanda (configure via KAFKA_BOOTSTRAP_SERVERS env var)
    - OMN-1735 merged and deployed (for event consumption tests)

Run with:
    pytest tests/integration/nodes/node_pattern_feedback_effect -v -m integration
"""

__all__: list[str] = []
