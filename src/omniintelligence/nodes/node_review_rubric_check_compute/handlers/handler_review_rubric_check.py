# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Check a review rubric file: a pass or a named refusal (OMN-21186)."""

from __future__ import annotations

from omniintelligence.nodes.node_review_rubric_check_compute.handlers.handler_review_rubric_loader import (
    load_review_rubric,
)
from omniintelligence.nodes.node_review_rubric_check_compute.models.enum_review_rubric_check_outcome import (
    EnumReviewRubricCheckOutcome,
)
from omniintelligence.nodes.node_review_rubric_check_compute.models.model_review_rubric_check_request import (
    ModelReviewRubricCheckRequest,
)
from omniintelligence.nodes.node_review_rubric_check_compute.models.model_review_rubric_check_result import (
    ModelReviewRubricCheckResult,
)


class HandlerReviewRubricCheck:
    """Validate a rubric through the runtime's typed handler interface."""

    def handle(
        self, request: ModelReviewRubricCheckRequest
    ) -> ModelReviewRubricCheckResult:
        """Load the rubric under the request's budget and report what happened."""
        loaded = load_review_rubric(
            request.rubric_yaml,
            token_budget=request.token_budget,
            source=request.rubric_source,
        )
        rubric = loaded.rubric
        return ModelReviewRubricCheckResult(
            rubric_source=request.rubric_source,
            outcome=(
                EnumReviewRubricCheckOutcome.ACCEPTED
                if rubric is not None
                else EnumReviewRubricCheckOutcome.REFUSED
            ),
            refusal=loaded.refusal,
            version=rubric.version if rubric is not None else None,
            content_hash=rubric.content_hash if rubric is not None else "",
            rule_count=len(rubric.rules) if rubric is not None else 0,
            token_count=loaded.token_count,
            token_budget=request.token_budget,
            correlation_id=request.correlation_id,
        )


def handle(request: ModelReviewRubricCheckRequest) -> ModelReviewRubricCheckResult:
    """The contract's routed entry point for checking a review rubric."""
    return HandlerReviewRubricCheck().handle(request)


__all__ = ["HandlerReviewRubricCheck", "handle"]
