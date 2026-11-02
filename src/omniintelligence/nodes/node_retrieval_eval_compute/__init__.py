# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Offline retrieval-quality eval harness for code-intelligence context packs (OMN-16522).

Runs entirely from the frozen replay fixtures: no live Postgres, Memgraph or
Qdrant, no network and no model calls, so CI and a laptop produce the same
bytes.
"""
