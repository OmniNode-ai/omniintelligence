#!/usr/bin/env python3
"""
Shared test utilities for integration tests.

Provides reusable assertion helpers and base test classes
to reduce code duplication across handler integration tests.

Modules:
    - assertions: Common assertion patterns for response validation
    - base: Base test classes with shared test methods

Author: Archon Intelligence Team
Date: 2025-10-15
"""

from .assertions import (
    assert_correlation_id_preserved,
    assert_error_response,
    assert_response_structure,
    assert_routing_context,
    assert_topic_naming,
)
from .base import HandlerTestBase

__all__ = [
    "assert_response_structure",
    "assert_topic_naming",
    "assert_correlation_id_preserved",
    "assert_routing_context",
    "assert_error_response",
    "HandlerTestBase",
]
