# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Testing utilities for omniintelligence.

This package provides mock implementations and test utilities that can be
imported from both the main test suite (tests/) and co-located node tests
(src/omniintelligence/nodes/*/node_tests/).

This solves the Python path issue where node_tests cannot import from
tests.fixtures when run from within the src directory.

Modules:
    mock_pattern_store: Mock implementations of pattern storage protocols
    mock_record: Mock asyncpg.Record for database row testing
"""

from omniintelligence.testing.mock_pattern_store import (
    MockPatternStateManager,
    MockPatternStore,
    create_low_confidence_input_dict,
    create_valid_pattern_input,
    make_discovered_event,
)
from omniintelligence.testing.mock_record import MockRecord

__all__ = [
    "MockPatternStateManager",
    "MockPatternStore",
    "MockRecord",
    "create_low_confidence_input_dict",
    "create_valid_pattern_input",
    "make_discovered_event",
]
