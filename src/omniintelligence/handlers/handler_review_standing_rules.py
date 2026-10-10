# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Standing-rules handler: validate a rules file and guard it against weakening.

Pure and definition-B shaped, ``handle(request) -> result``. The caller reads the
rules text (from the protected base branch) and the pull request's copy; this
handler does no I/O. Domain errors come back as data, never as exceptions.

Ticket: OMN-20784
"""

from __future__ import annotations

from typing import Literal

import yaml
from pydantic import ValidationError

from omniintelligence.models.review.model_review_standing_rules import (
    ModelReviewStandingRules,
)
from omniintelligence.models.review.model_standing_rule_weakening import (
    ModelStandingRuleWeakening,
)
from omniintelligence.models.review.model_standing_rules_request import (
    ModelStandingRulesRequest,
)
from omniintelligence.models.review.model_standing_rules_result import (
    ModelStandingRulesResult,
)


def _parse(text: str | None) -> tuple[ModelReviewStandingRules | None, tuple[str, ...]]:
    """Parse rules text into the typed schema, or say why it is unusable."""
    if text is None:
        return None, ("rules file does not exist",)
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return None, (f"rules file is not valid YAML: {exc}",)
    if not isinstance(raw, dict):
        return None, (
            "rules file must be a mapping with schema_version, version, rules",
        )
    try:
        return ModelReviewStandingRules.model_validate(raw), ()
    except ValidationError as exc:
        return None, tuple(
            f"{'.'.join(str(p) for p in err['loc']) or 'rules'}: {err['msg']}"
            for err in exc.errors()
        )


def _weakened(
    base: ModelReviewStandingRules, candidate: ModelReviewStandingRules | None
) -> tuple[ModelStandingRuleWeakening, ...]:
    """Mandatory base rules the candidate removes, demotes or rewords."""
    found: list[ModelStandingRuleWeakening] = []
    for rule in base.rules:
        if not rule.mandatory:
            continue
        kept = candidate.rule(rule.id) if candidate is not None else None
        reason: Literal["removed", "demoted", "reworded"]
        if kept is None:
            reason = "removed"
        elif not kept.mandatory:
            reason = "demoted"
        elif kept.text != rule.text:
            reason = "reworded"
        else:
            continue
        found.append(ModelStandingRuleWeakening(rule_id=rule.id, reason=reason))
    return tuple(found)


def handle(request: ModelStandingRulesRequest) -> ModelStandingRulesResult:
    """Validate the authoritative rules; when asked, compare the pull request's copy.

    A candidate that is present but invalid is reported in ``candidate_errors``
    and fails the result, and since an invalid file keeps none of the base's
    mandatory rules, each of them is also reported as removed.
    """
    rules, errors = _parse(request.rules_text)
    if rules is None:
        return ModelStandingRulesResult(ok=False, errors=errors)
    if not request.compare_candidate:
        return ModelStandingRulesResult(ok=True, rules=rules)

    candidate: ModelReviewStandingRules | None = None
    candidate_errors: tuple[str, ...] = ()
    if request.candidate_text is not None:
        candidate, candidate_errors = _parse(request.candidate_text)
    weakened = _weakened(rules, candidate)
    return ModelStandingRulesResult(
        ok=not weakened and not candidate_errors,
        rules=rules,
        weakened=weakened,
        candidate_errors=candidate_errors,
    )


__all__ = ["handle"]
