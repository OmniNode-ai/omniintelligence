# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Cross-model agreement (quorum) aggregation for adversarial review.

``run_review`` runs each model independently and concatenates the results.
Before this module existed, every caller workflow turned that concatenation
into a verdict by SUMMING blocking findings across models, so one model's
rotating hallucination was sufficient to block a merge -- measured on
omniclaude as 24 blocked runs out of 40 on a finding no second sample
reproduced.

Here a finding blocks only when at least ``min_agreeing_models`` DISTINCT
successful models raise a matching finding. A finding raised by one model
is reported as a warning: never dropped, never blocking.

DISTINCT means distinct reviewers, not distinct registry keys (OMN-17492).
A key is a name; ``qwen3-review``, ``qwen3-review-b`` and ``deepseek-r1``
were three names for one endpoint serving one model, and two of them met
the quorum with that model agreeing with itself. Each result carries the
``reviewer_identity`` the CLI stamped on it (endpoint plus model, see
``reviewer_identity.py``), and both the quorum and every agreement count
are taken over identities. A result without one counts as ``key:<model>``.

Fingerprint -- which fields are stable across models, and which are not:

* ``file_path`` IS the location for LLM findings. ``adapter_ai_reviewer``
  writes the model's free-text ``location`` into it and hardcodes
  ``line_start = 1`` for every finding, so line-only bucketing would put
  every finding in one bucket. A trailing ``:<line>`` (and an optional
  ``:<column>``) is split off the path and used as the line; otherwise
  ``line_start`` is used.
* ``rule_id`` is NOT stable: the same adapter writes
  ``ai-reviewer:{model_key}:{category}``, which embeds the model key, so
  two models can never agree on a raw ``rule_id``. The tool and model
  segments are stripped and the trailing category is the agreement key.
  ``category`` is used directly when a non-LLM source populates it.
* ``severity`` is used as-is. Two models must agree on severity, not only
  on location: a warning from one model and an error from another are two
  different claims.
* ``normalized_message`` is deliberately NOT part of the fingerprint. Two
  models describing the same defect never phrase it identically, and
  substring or ratio matching would make agreement depend on prose.

Within a ``(path, rule, severity)`` group, findings cluster by line
proximity: a cluster is anchored on its lowest line and admits findings
within ``line_proximity_lines`` of that anchor. Fixed-width buckets were
rejected because they split adjacent lines across a boundary (lines 10 and
12 land in different buckets at width 7).

Reference: OMN-18479.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from omniintelligence.review_pairing.models import (
    EnumFindingSeverity,
    ModelReviewFindingObserved,
)
from omniintelligence.review_pairing.models_external_review import (
    EnumQuorumVerdict,
    ModelExternalReviewResult,
    ModelMultiReviewResult,
    ModelQuorumFinding,
    ModelReviewQuorumPolicy,
    ModelReviewQuorumSummary,
)

_AI_REVIEWER_RULE_PREFIX: str = "ai-reviewer:"
_LOCATION_WITH_LINE: re.Pattern[str] = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+)(?::\d+)?$"
)


def _normalise_rule(finding: ModelReviewFindingObserved) -> str:
    """Return a model-independent agreement key for a finding's rule.

    ``ai-reviewer:{model_key}:{category}`` collapses to its category; any
    other ``rule_id`` (ruff, mypy, eslint, github-checks) is already
    model-independent and is used whole.
    """
    if finding.category is not None:
        return f"category:{finding.category.value}"
    rule = finding.rule_id.strip().lower()
    if rule.startswith(_AI_REVIEWER_RULE_PREFIX):
        return f"category:{rule.rsplit(':', 1)[-1]}"
    return f"rule:{rule}"


def _normalise_location(finding: ModelReviewFindingObserved) -> tuple[str, int]:
    """Return ``(normalised path, resolved line)`` for a finding."""
    raw = finding.file_path.strip()
    match = _LOCATION_WITH_LINE.match(raw)
    if match is not None:
        path = match.group("path")
        line = int(match.group("line"))
    else:
        path = raw
        line = finding.line_start
    normalised = path.strip().lower().lstrip("./")
    return normalised, max(line, 1)


class _Cluster:
    """Mutable accumulator for one agreement cluster."""

    def __init__(
        self,
        *,
        path: str,
        rule: str,
        severity: EnumFindingSeverity,
        line: int,
        model: str,
        identity: str,
        finding: ModelReviewFindingObserved,
    ) -> None:
        self.path = path
        self.rule = rule
        self.severity = severity
        self.line = line
        self.message = finding.normalized_message
        self.models: list[str] = [model]
        self.identities: list[str] = [identity]
        self.finding_ids: list[str] = [str(finding.finding_id)]

    def admit(
        self, *, model: str, identity: str, finding: ModelReviewFindingObserved
    ) -> None:
        if model not in self.models:
            self.models.append(model)
        if identity not in self.identities:
            self.identities.append(identity)
        self.finding_ids.append(str(finding.finding_id))


def _identity(model_result: ModelExternalReviewResult) -> str:
    """Distinct-reviewer identity of a result, falling back to its key."""
    return model_result.reviewer_identity or f"key:{model_result.model}"


def _cluster_findings(
    result: ModelMultiReviewResult,
    policy: ModelReviewQuorumPolicy,
) -> list[_Cluster]:
    """Group every successful model's findings into agreement clusters."""
    grouped: dict[tuple[str, str, EnumFindingSeverity], list[_Cluster]] = {}
    ordered_clusters: list[_Cluster] = []

    for model_result in result.results:
        if not model_result.success:
            continue
        model = model_result.model
        identity = _identity(model_result)
        for finding in model_result.findings:
            path, line = _normalise_location(finding)
            rule = _normalise_rule(finding)
            key = (path, rule, finding.severity)
            bucket = grouped.setdefault(key, [])
            for cluster in bucket:
                if abs(line - cluster.line) <= policy.line_proximity_lines:
                    cluster.admit(model=model, identity=identity, finding=finding)
                    break
            else:
                cluster = _Cluster(
                    path=path,
                    rule=rule,
                    severity=finding.severity,
                    line=line,
                    model=model,
                    identity=identity,
                    finding=finding,
                )
                bucket.append(cluster)
                ordered_clusters.append(cluster)

    return ordered_clusters


def evaluate_quorum(
    result: ModelMultiReviewResult,
    policy: ModelReviewQuorumPolicy,
) -> ModelReviewQuorumSummary:
    """Resolve a multi-model review into a quorum verdict.

    Args:
        result: Aggregated per-model review envelope.
        policy: Active quorum policy (contract-declared, caller may raise
            the threshold but never lower it).

    Returns:
        A ``ModelReviewQuorumSummary``. ``degraded_quorum`` and
        ``no_models`` are NOT passes: they say no verdict could be
        established, and callers fail closed on them.
    """
    succeeded: tuple[str, ...] = tuple(
        model_result.model for model_result in result.results if model_result.success
    )
    distinct: tuple[str, ...] = tuple(
        dict.fromkeys(
            _identity(model_result)
            for model_result in result.results
            if model_result.success
        )
    )
    quorum_met = len(distinct) >= policy.min_agreeing_models

    clusters = _cluster_findings(result, policy)

    blocking: list[ModelQuorumFinding] = []
    warnings: list[ModelQuorumFinding] = []
    for cluster in clusters:
        is_blocking = (
            quorum_met
            and cluster.severity in policy.blocking_severities
            and len(cluster.identities) >= policy.min_agreeing_models
        )
        entry = ModelQuorumFinding(
            file_path=cluster.path,
            line_start=cluster.line,
            severity=cluster.severity,
            rule=cluster.rule,
            message=cluster.message,
            agreeing_models=tuple(cluster.models),
            agreement_count=len(cluster.identities),
            blocking=is_blocking,
            finding_ids=tuple(cluster.finding_ids),
        )
        if is_blocking:
            blocking.append(entry)
        else:
            warnings.append(entry)

    if not succeeded:
        verdict = EnumQuorumVerdict.NO_MODELS
    elif not quorum_met:
        verdict = EnumQuorumVerdict.DEGRADED_QUORUM
    elif blocking:
        verdict = EnumQuorumVerdict.BLOCKED
    else:
        verdict = EnumQuorumVerdict.PASSED

    return ModelReviewQuorumSummary(
        verdict=verdict,
        quorum_threshold=policy.min_agreeing_models,
        models_succeeded=succeeded,
        distinct_reviewers_succeeded=distinct,
        quorum_met=quorum_met,
        blocking_count=len(blocking),
        warning_count=len(warnings),
        blocking_findings=tuple(blocking),
        warning_findings=tuple(warnings),
    )


def format_quorum_summary(summary: ModelReviewQuorumSummary) -> Sequence[str]:
    """Render the quorum verdict as human-readable stderr lines."""
    lines = [
        f"Quorum verdict: {summary.verdict.value} "
        f"(threshold={summary.quorum_threshold}, "
        f"models succeeded={len(summary.models_succeeded)}, "
        f"distinct reviewers={len(summary.distinct_reviewers_succeeded)})",
        f"Blocking (agreed by >={summary.quorum_threshold} models): "
        f"{summary.blocking_count}",
        f"Warnings (below quorum, reported only): {summary.warning_count}",
    ]
    for entry in summary.blocking_findings:
        lines.append(
            f"  [BLOCKING] {entry.file_path}:{entry.line_start} "
            f"{entry.severity.value} {entry.rule} "
            f"({', '.join(entry.agreeing_models)}): {entry.message[:160]}"
        )
    for entry in summary.warning_findings:
        lines.append(
            f"  [warning] {entry.file_path}:{entry.line_start} "
            f"{entry.severity.value} {entry.rule} "
            f"({', '.join(entry.agreeing_models)}): {entry.message[:160]}"
        )
    return lines


__all__ = [
    "evaluate_quorum",
    "format_quorum_summary",
]
