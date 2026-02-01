"""Integration tests for node_pattern_feedback_effect.

These tests verify event consumption from Kafka topics.

PARTIAL BLOCK: Event consumption tests require OMN-1735 (session-outcome emitter).
Contract configuration tests can run now.

Prerequisites:
    - PostgreSQL running on 192.168.86.200:5436
    - Kafka/Redpanda running on 192.168.86.200:29092
    - OMN-1735 merged and deployed (for event consumption tests)

Run with:
    pytest tests/integration/nodes/node_pattern_feedback_effect -v -m integration
"""

__all__: list[str] = []
