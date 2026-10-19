# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Recorded dismissals of blocking Hostile Reviewer findings (OMN-20910).

COMPUTE node: ``handle(ModelReviewDismissalRequest) -> ModelReviewDismissalResult``.
A pull request author records a dismissal per finding key, for one head, with
evidence. Each dismissal with evidence, for the head under review, of a finding
that blocks there, is put to a second voter (a voter other than the one that
raised the finding). Confirmed dismissals stop blocking; every other dismissal
keeps blocking. Every dismissal yields one record, written to the pull request
and emitted as an event. The caller makes the voter calls; this node is pure.
"""
