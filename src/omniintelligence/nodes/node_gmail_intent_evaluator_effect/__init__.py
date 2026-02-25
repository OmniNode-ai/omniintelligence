# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Gmail Intent Evaluator Effect node.

Subscribes to gmail-intent-received.v1 events, fetches URL content,
queries omnimemory for duplicates, calls DeepSeek R1 for evaluation,
and posts to Slack if verdict is SURFACE.

Reference:
    - OMN-2787: Gmail Intent Evaluator — Email-to-Initial-Plan Pipeline
    - OMN-2788: Models
    - OMN-2791: Node shell + contract
    - OMN-2790: Handler
"""
