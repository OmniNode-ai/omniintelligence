# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Review rubric file format, loader with token budget and check node (OMN-21186).

COMPUTE node: ``handle(ModelReviewRubricCheckRequest) -> ModelReviewRubricCheckResult``
reads a ``review_rubric.v1`` document, refuses a malformed one by name, refuses one over
the caller's token budget, and reports a pass or the named refusal. Part of the
review-learning plan (parent OMN-20976): the distiller writes these files, the
orchestrated review workflow reads them through the loader.
"""
