# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Typed review records, one per voter (OMN-20981).

COMPUTE node: ``handle(ModelReviewRecordRequest) -> ModelReviewRecordBatch``
turns a Hostile Reviewer run into one ``ModelReviewRecorded`` per voter and one
per substitute vote, so finding content survives the run. Pure: the run, the
clock and the invocation id are inputs.
"""
