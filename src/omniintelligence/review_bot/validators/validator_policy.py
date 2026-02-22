"""Policy validation logic for the Code Intelligence Review Bot.

Validates policy YAML files against the ModelReviewPolicy schema and
performs additional semantic checks. Produces actionable error messages
with field names and line hints.

OMN-2494: Implement policy YAML schema and validator.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

import yaml
from pydantic import ValidationError

from omniintelligence.review_bot.schemas.model_review_policy import ModelReviewPolicy


@dataclass
class PolicyValidationError:
    """A validation error with actionable context.

    Attributes:
        field: The field name or path that caused the error (e.g., "rules[0].severity").
        message: Human-readable error description with remediation hint.
        line_hint: Optional line number hint if available from YAML parsing.
        correlation_id: Optional correlation ID for end-to-end tracing.
    """

    field: str
    message: str
    line_hint: int | None = None
    correlation_id: str | None = None

    def __str__(self) -> str:
        location = f"line {self.line_hint}: " if self.line_hint else ""
        return f"{location}{self.field}: {self.message}"


@dataclass
class PolicyValidationWarning:
    """A validation warning that does not block policy loading.

    Attributes:
        field: The field name or path that triggered the warning.
        message: Human-readable warning description.
        correlation_id: Optional correlation ID for end-to-end tracing.
    """

    field: str
    message: str
    correlation_id: str | None = None

    def __str__(self) -> str:
        return f"{self.field}: {self.message}"


@dataclass
class PolicyValidationResult:
    """Result of validating a policy file.

    Attributes:
        policy: The parsed policy model (None if validation failed).
        errors: List of validation errors (empty if valid).
        warnings: List of validation warnings (non-blocking).
        is_valid: True if the policy can be used (no errors).
    """

    policy: ModelReviewPolicy | None
    errors: list[PolicyValidationError] = field(default_factory=list)
    warnings: list[PolicyValidationWarning] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return True if there are no blocking errors."""
        return len(self.errors) == 0 and self.policy is not None


class ValidatorPolicy:
    """Validates policy YAML files for the Code Intelligence Review Bot.

    This validator:
    - Parses YAML and validates against the Pydantic schema
    - Produces actionable error messages with field names
    - Warns about (but does not fail on) expired exemptions
    - Checks for duplicate rule IDs
    - Lists valid values for invalid enum fields

    Usage::

        validator = ValidatorPolicy()

        # From file path
        result = validator.validate_file("/path/to/review_policy.yaml")

        # From YAML string
        result = validator.validate_yaml_string(yaml_content)

        # From already-parsed dict
        result = validator.validate_dict(policy_data)

        if not result.is_valid:
            for error in result.errors:
                print(f"ERROR: {error}")
        for warning in result.warnings:
            print(f"WARNING: {warning}", file=sys.stderr)
    """

    def validate_file(
        self, path: str, correlation_id: str | None = None
    ) -> PolicyValidationResult:
        """Validate a policy YAML file at the given path.

        Args:
            path: Filesystem path to the policy YAML file.
            correlation_id: Optional correlation ID for end-to-end tracing.

        Returns:
            PolicyValidationResult with errors and warnings.
        """
        try:
            with open(path) as f:
                content = f.read()
        except OSError as exc:
            return PolicyValidationResult(
                policy=None,
                errors=[
                    PolicyValidationError(
                        field="file",
                        message=f"Cannot read policy file {path!r}: {exc}",
                        correlation_id=correlation_id,
                    )
                ],
            )
        return self.validate_yaml_string(content, correlation_id=correlation_id)

    def validate_yaml_string(
        self, yaml_content: str, correlation_id: str | None = None
    ) -> PolicyValidationResult:
        """Validate a policy from a YAML string.

        Args:
            yaml_content: YAML string to parse and validate.
            correlation_id: Optional correlation ID for end-to-end tracing.

        Returns:
            PolicyValidationResult with errors and warnings.
        """
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as exc:
            line_hint: int | None = None
            if hasattr(exc, "problem_mark") and exc.problem_mark is not None:
                line_hint = exc.problem_mark.line + 1
            return PolicyValidationResult(
                policy=None,
                errors=[
                    PolicyValidationError(
                        field="yaml",
                        message=f"Invalid YAML syntax: {exc}",
                        line_hint=line_hint,
                        correlation_id=correlation_id,
                    )
                ],
            )

        if not isinstance(data, dict):
            return PolicyValidationResult(
                policy=None,
                errors=[
                    PolicyValidationError(
                        field="root",
                        message=(
                            "Policy must be a YAML mapping (key: value pairs), "
                            f"got {type(data).__name__}"
                        ),
                        correlation_id=correlation_id,
                    )
                ],
            )

        return self.validate_dict(data, correlation_id=correlation_id)

    def validate_dict(
        self, data: dict[str, Any], correlation_id: str | None = None
    ) -> PolicyValidationResult:
        """Validate a policy from an already-parsed dictionary.

        Args:
            data: Policy data as a Python dictionary.
            correlation_id: Optional correlation ID for end-to-end tracing.

        Returns:
            PolicyValidationResult with errors and warnings.
        """
        errors: list[PolicyValidationError] = []
        warnings: list[PolicyValidationWarning] = []

        # Check required fields before Pydantic validation for better messages
        if "version" not in data:
            errors.append(
                PolicyValidationError(
                    field="version",
                    message="Required field 'version' is missing. Add: version: \"1.0\"",
                    correlation_id=correlation_id,
                )
            )

        if "rules" not in data:
            errors.append(
                PolicyValidationError(
                    field="rules",
                    message=(
                        "Required field 'rules' is missing. "
                        "Add a rules list with at least one rule."
                    ),
                    correlation_id=correlation_id,
                )
            )

        if errors:
            return PolicyValidationResult(policy=None, errors=errors, warnings=warnings)

        # Validate via Pydantic
        try:
            policy = ModelReviewPolicy.model_validate(data)
        except ValidationError as exc:
            for error in exc.errors():
                loc = error.get("loc", ())
                field_path = ".".join(str(part) for part in loc) if loc else "unknown"
                msg = error.get("msg", "Validation error")

                # Enhance enum error messages with valid values
                if "enum" in msg.lower() or error.get("type") == "enum":
                    from omniintelligence.review_bot.schemas.model_review_policy import (
                        ReviewSeverity,
                    )

                    if "severity" in field_path:
                        valid_vals = [s.value for s in ReviewSeverity]
                        msg = (
                            f"Invalid severity value. "
                            f"Valid values are: {valid_vals}. Got: {error.get('input')!r}"
                        )
                    elif "enforcement_mode" in field_path:
                        msg = (
                            "Invalid enforcement_mode. "
                            "Valid values are: ['observe', 'warn', 'block']. "
                            f"Got: {error.get('input')!r}"
                        )

                errors.append(
                    PolicyValidationError(
                        field=field_path, message=msg, correlation_id=correlation_id
                    )
                )

            return PolicyValidationResult(policy=None, errors=errors, warnings=warnings)

        # Post-parse warnings (non-blocking)
        for i, exemption in enumerate(policy.exemptions):
            if exemption.is_expired:
                warnings.append(
                    PolicyValidationWarning(
                        field=f"exemptions[{i}]",
                        message=(
                            f"Exemption for rule {exemption.rule!r} on path {exemption.path!r} "
                            f"expired on {exemption.expires}. "
                            "Remove or update the exemption to suppress this warning."
                        ),
                        correlation_id=correlation_id,
                    )
                )
                # Emit expired exemption warning to stderr
                corr_prefix = f"[{correlation_id}] " if correlation_id else ""
                print(
                    f"{corr_prefix}WARNING: exemptions[{i}]: Exemption for rule {exemption.rule!r} "
                    f"expired on {exemption.expires}",
                    file=sys.stderr,
                )

        return PolicyValidationResult(policy=policy, errors=[], warnings=warnings)


__all__ = [
    "PolicyValidationError",
    "PolicyValidationResult",
    "PolicyValidationWarning",
    "ValidatorPolicy",
]
