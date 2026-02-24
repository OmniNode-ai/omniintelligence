# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Pattern Learning Effect node package.

Skeletal package providing the contract declaration for the pattern learning
effect node.  The dispatch handler that processes events for this node lives
in ``omniintelligence.runtime.dispatch_handler_pattern_learning`` and is
wired by the intelligence dispatch engine at startup.

This package subscribes to ``onex.cmd.omniintelligence.pattern-learning.v1``
and publishes ``onex.evt.omniintelligence.pattern-learned.v1``.

Reference:
    - OMN-2222: Wire intelligence pipeline end-to-end
"""

__all__: list[str] = []
