# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Hostile Reviewer voters from a contract overlay (OMN-20910).

COMPUTE node: ``handle(ModelReviewVotersOverlayRequest) -> ModelReviewVoterRoster``
validates a ``review_voters_overlay.v1`` document and resolves each voter's
endpoint against the lab delegation overlay. This package imports nothing but
the standard library, ``pydantic`` and ``yaml``, so the hostile-reviewer
workflows' pre-install preflight can import it from a bare source checkout.
"""
