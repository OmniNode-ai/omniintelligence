# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Re-export mock implementations from omniintelligence.testing.

This module re-exports the mock implementations for backward compatibility.
The canonical location is now omniintelligence.testing.mock_pattern_store.

Usage:
    # Preferred (works in both tests/ and node_tests/):
    from omniintelligence.testing import (
        MockPatternStore,
        MockPatternStateManager,
        create_valid_pattern_input,
    )

    # Legacy (still works in tests/ only):
    from tests.fixtures.mock_pattern_store import (
        MockPatternStore,
        MockPatternStateManager,
        create_valid_pattern_input,
    )

Reference:
    - OMN-1668: Pattern storage effect acceptance criteria
    - OMN-1780: Pattern storage repository contract
"""

from omniintelligence.testing.mock_pattern_store import (
    MockPatternStateManager,
    MockPatternStore,
    create_low_confidence_input_dict,
    create_valid_pattern_input,
)

__all__ = [
    "MockPatternStateManager",
    "MockPatternStore",
    "create_low_confidence_input_dict",
    "create_valid_pattern_input",
]
