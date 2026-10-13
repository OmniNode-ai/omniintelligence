# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Off-CI review receipts standing in for a lost voter (OMN-20947).

COMPUTE node: ``handle(ModelSubstituteVoteRequest) -> ModelSubstituteDecision``
decides which Hostile Reviewer voters that timed out or were unavailable may
count as voted, from
signed review receipts bound to the head commit. Pure: the reviews, the key
and the clock are inputs.
"""
