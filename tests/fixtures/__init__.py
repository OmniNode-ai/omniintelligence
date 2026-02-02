# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Shared test fixtures and constants for omniintelligence tests.

This package provides reusable fixtures and constants that can be imported
by both unit and integration tests, avoiding cross-layer dependencies.

Modules:
    mock_pattern_store: Mock implementations of pattern storage protocols
    topic_constants: Kafka topic naming constants
"""

# Import from canonical location (omniintelligence.testing)
from omniintelligence.testing import (
    MockPatternStateManager,
    MockPatternStore,
    create_low_confidence_input_dict,
    create_valid_pattern_input,
)
from tests.fixtures.topic_constants import (
    TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1,
    TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
)

__all__ = [
    # Mock protocol implementations
    "MockPatternStateManager",
    "MockPatternStore",
    "create_low_confidence_input_dict",
    "create_valid_pattern_input",
    # Topic constants
    "TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1",
    "TOPIC_SUFFIX_INTENT_CLASSIFIED_V1",
]
