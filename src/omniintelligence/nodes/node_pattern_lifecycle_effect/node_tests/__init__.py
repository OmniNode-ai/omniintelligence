# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for pattern_lifecycle_effect node.

This package contains comprehensive tests for the pattern lifecycle effect
node handlers, covering:
- Transition success scenarios
- Idempotency (duplicate detection)
- Status guard (optimistic locking)
- PROVISIONAL guard (legacy protection)
- Audit record insertion
- Kafka event emission

Reference:
    - OMN-1805: Pattern lifecycle effect node with atomic projections
"""
