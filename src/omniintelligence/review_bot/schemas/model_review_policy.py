"""Pydantic models for the Code Intelligence Review Bot policy schema.

The policy YAML schema defines rules, severities, patterns, and exemptions
for code review. This is the foundational contract all other review bot
components depend on.

Policy YAML structure::

    version: "1.0"
    enforcement_mode: observe  # observe | warn | block
    rules:
      - id: no-bare-except
        severity: BLOCKER
        pattern: "except:"
        message: "Bare except clause catches all exceptions including KeyboardInterrupt"
    exemptions:
      - rule: no-bare-except
        path: tests/
        expires: "2026-06-01"
        reason: "Legacy test code, tracked in OMN-9999"

OMN-2494: Implement policy YAML schema and validator.
"""

from __future__ import annotations

import re
from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class ReviewSeverity(str, Enum):
    """Severity levels for review findings.

    BLOCKER findings prevent merging in BLOCK enforcement mode.
    WARNING findings are visible but non-blocking.
    INFO findings are informational only.
    """

    BLOCKER = "BLOCKER"
    WARNING = "WARNING"
    INFO = "INFO"


class EnforcementMode(str, Enum):
    """How policy findings are enforced in CI.

    OBSERVE - silent; findings logged but CI always passes (default for new repos).
    WARN - findings posted as PR comments; CI always passes.
    BLOCK - BLOCKER findings cause CI to fail.
    """

    OBSERVE = "observe"
    WARN = "warn"
    BLOCK = "block"


class ModelReviewRule(BaseModel):
    """A single review rule definition in a policy file.

    Rules define what patterns to detect and how severe violations are.

    Attributes:
        id: Unique identifier for this rule (e.g., "no-bare-except").
        severity: How severe a violation is (BLOCKER/WARNING/INFO).
        pattern: Regex or string pattern to detect in code.
        message: Human-readable explanation of the violation.
        slow: If True, skip this rule in pre-commit fast-path checks.
        enabled: Whether this rule is active (default True).
    """

    id: str = Field(..., description="Unique rule identifier", min_length=1)
    severity: ReviewSeverity = Field(..., description="Severity level for violations")
    pattern: str = Field(
        ..., description="Regex pattern to detect violations", min_length=1
    )
    message: str = Field(
        ..., description="Human-readable violation explanation", min_length=1
    )
    slow: bool = Field(
        default=False, description="If True, skip in pre-commit fast-path"
    )
    enabled: bool = Field(default=True, description="Whether this rule is active")

    model_config = {"frozen": True, "extra": "ignore", "from_attributes": True}


class ModelReviewExemption(BaseModel):
    """A single exemption that suppresses a rule for a specific path.

    Exemptions require an expiry date to prevent permanent suppression
    of technical debt bypasses.

    Attributes:
        rule: The rule ID this exemption applies to.
        path: File path or glob pattern to exempt (e.g., "tests/" or "*.test.py").
        expires: ISO date string when this exemption expires (e.g., "2026-06-01").
        reason: Human-readable justification for the exemption.
    """

    rule: str = Field(
        ..., description="Rule ID this exemption applies to", min_length=1
    )
    path: str = Field(
        ..., description="File path or glob pattern to exempt", min_length=1
    )
    expires: str = Field(
        ..., description="ISO date string when exemption expires (YYYY-MM-DD)"
    )
    reason: str = Field(
        ..., description="Justification for this exemption", min_length=1
    )

    @field_validator("expires")
    @classmethod
    def validate_expires_format(cls, v: str) -> str:
        """Validate that expires is a valid ISO date string."""
        try:
            date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(
                f"expires must be a valid ISO date string (YYYY-MM-DD), got: {v!r}"
            ) from exc
        return v

    model_config = {"frozen": True, "extra": "ignore", "from_attributes": True}

    @property
    def is_expired(self) -> bool:
        """Return True if this exemption has passed its expiry date."""
        return date.fromisoformat(self.expires) < date.today()


class ModelReviewPolicy(BaseModel):
    """Top-level policy model for the Code Intelligence Review Bot.

    This model is the foundational contract that all other review bot
    components depend on. Policy files are loaded from ``review_policy.yaml``
    at the repository root.

    Attributes:
        version: Policy schema version (semver string, e.g., "1.0").
        enforcement_mode: How violations affect CI (observe/warn/block).
        rules: List of review rules to apply.
        exemptions: List of path-scoped rule exemptions.

    Example YAML::

        version: "1.0"
        enforcement_mode: observe
        rules:
          - id: no-bare-except
            severity: BLOCKER
            pattern: "except:"
            message: "Bare except clause is dangerous"
        exemptions:
          - rule: no-bare-except
            path: tests/legacy/
            expires: "2026-12-01"
            reason: "Legacy code being migrated, tracked in OMN-9999"
    """

    version: str = Field(
        ...,
        description="Policy schema version (semver string, e.g., '1.0')",
        min_length=1,
    )
    enforcement_mode: EnforcementMode = Field(
        default=EnforcementMode.OBSERVE,
        description="Enforcement mode: observe | warn | block",
    )
    rules: list[ModelReviewRule] = Field(
        default_factory=list,
        description="Review rules to apply",
    )
    exemptions: list[ModelReviewExemption] = Field(
        default_factory=list,
        description="Path-scoped rule exemptions",
    )

    @field_validator("version")
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        """Validate that version follows semver-ish format."""
        # Accept "1.0", "1.0.0", "2.1", etc.
        if not re.match(r"^\d+\.\d+(\.\d+)?$", v):
            raise ValueError(
                f"version must follow semver format (e.g., '1.0' or '1.0.0'), got: {v!r}"
            )
        return v

    @model_validator(mode="after")
    def validate_no_duplicate_rule_ids(self) -> ModelReviewPolicy:
        """Validate that all rule IDs are unique within the policy."""
        rule_ids = [rule.id for rule in self.rules]
        seen: set[str] = set()
        duplicates: list[str] = []
        for rule_id in rule_ids:
            if rule_id in seen:
                duplicates.append(rule_id)
            seen.add(rule_id)
        if duplicates:
            raise ValueError(
                f"Duplicate rule IDs found in policy: {sorted(set(duplicates))}. "
                "Each rule ID must be unique."
            )
        return self

    @model_validator(mode="after")
    def validate_exemption_rules_exist(self) -> ModelReviewPolicy:
        """Validate that all exemption rule references exist in the rules list."""
        rule_ids = {rule.id for rule in self.rules}
        unknown: list[str] = []
        for exemption in self.exemptions:
            if exemption.rule not in rule_ids:
                unknown.append(exemption.rule)
        if unknown:
            raise ValueError(
                f"Exemptions reference unknown rule IDs: {sorted(set(unknown))}. "
                "All exempted rule IDs must be defined in the rules list."
            )
        return self

    def get_active_rules(self) -> list[ModelReviewRule]:
        """Return only enabled rules."""
        return [r for r in self.rules if r.enabled]

    def get_fast_rules(self) -> list[ModelReviewRule]:
        """Return only enabled, fast (non-slow) rules for pre-commit use."""
        return [r for r in self.rules if r.enabled and not r.slow]

    model_config = {"frozen": True, "extra": "ignore", "from_attributes": True}


__all__ = [
    "EnforcementMode",
    "ModelReviewExemption",
    "ModelReviewPolicy",
    "ModelReviewRule",
    "ReviewSeverity",
]
