"""Unit tests for ModelReviewPolicy Pydantic models.

Tests cover all acceptance criteria from OMN-2494:
- R1: Policy schema covers all required fields
- R2: Validator rejects invalid policies with actionable errors
- R3: Example policy file can be loaded
"""

from __future__ import annotations

import textwrap
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from omniintelligence.review_bot.schemas.model_review_policy import (
    ModelReviewExemption,
    ModelReviewPolicy,
    ModelReviewRule,
    ReviewSeverity,
)
from omniintelligence.review_bot.validators.validator_policy import (
    ValidatorPolicy,
)

# ---------------------------------------------------------------------------
# ReviewSeverity tests
# ---------------------------------------------------------------------------


class TestReviewSeverity:
    def test_blocker_value(self) -> None:
        assert ReviewSeverity.BLOCKER == "BLOCKER"

    def test_warning_value(self) -> None:
        assert ReviewSeverity.WARNING == "WARNING"

    def test_info_value(self) -> None:
        assert ReviewSeverity.INFO == "INFO"

    def test_all_three_severities_exist(self) -> None:
        values = {s.value for s in ReviewSeverity}
        assert values == {"BLOCKER", "WARNING", "INFO"}


# ---------------------------------------------------------------------------
# ModelReviewRule tests
# ---------------------------------------------------------------------------


class TestModelReviewRule:
    def test_valid_rule_creation(self) -> None:
        rule = ModelReviewRule(
            id="no-bare-except",
            severity=ReviewSeverity.BLOCKER,
            pattern="except:",
            message="Bare except is dangerous",
        )
        assert rule.id == "no-bare-except"
        assert rule.severity == ReviewSeverity.BLOCKER
        assert rule.pattern == "except:"
        assert rule.message == "Bare except is dangerous"
        assert rule.slow is False
        assert rule.enabled is True

    def test_rule_is_frozen(self) -> None:
        rule = ModelReviewRule(
            id="test",
            severity=ReviewSeverity.INFO,
            pattern=".",
            message="test",
        )
        with pytest.raises(ValidationError):
            rule.id = "modified"  # type: ignore[misc]

    def test_rule_extra_fields_ignored(self) -> None:
        """Forward-compat: unknown fields should be ignored."""
        rule = ModelReviewRule(
            id="test",
            severity=ReviewSeverity.WARNING,
            pattern=".",
            message="test",
            unknown_future_field="ignored",  # type: ignore[call-arg]
        )
        assert rule.id == "test"

    def test_rule_slow_flag(self) -> None:
        rule = ModelReviewRule(
            id="slow-rule",
            severity=ReviewSeverity.WARNING,
            pattern=".",
            message="slow",
            slow=True,
        )
        assert rule.slow is True

    def test_rule_disabled(self) -> None:
        rule = ModelReviewRule(
            id="disabled-rule",
            severity=ReviewSeverity.INFO,
            pattern=".",
            message="disabled",
            enabled=False,
        )
        assert rule.enabled is False

    def test_rule_requires_id(self) -> None:
        with pytest.raises(ValidationError, match="id"):
            ModelReviewRule(
                severity=ReviewSeverity.INFO,
                pattern=".",
                message="test",
            )

    def test_rule_requires_severity(self) -> None:
        with pytest.raises(ValidationError, match="severity"):
            ModelReviewRule(id="test", pattern=".", message="test")

    def test_rule_invalid_severity_enum(self) -> None:
        with pytest.raises(ValidationError):
            ModelReviewRule(
                id="test",
                severity="CRITICAL",  # type: ignore[arg-type]
                pattern=".",
                message="test",
            )


# ---------------------------------------------------------------------------
# ModelReviewExemption tests
# ---------------------------------------------------------------------------


class TestModelReviewExemption:
    def _future_date(self, days: int = 365) -> str:
        return (date.today() + timedelta(days=days)).isoformat()

    def _past_date(self, days: int = 1) -> str:
        return (date.today() - timedelta(days=days)).isoformat()

    def test_valid_exemption(self) -> None:
        exemption = ModelReviewExemption(
            rule="no-bare-except",
            path="tests/legacy/",
            expires=self._future_date(),
            reason="Legacy code, tracked in OMN-9999",
        )
        assert exemption.rule == "no-bare-except"
        assert exemption.is_expired is False

    def test_exemption_is_frozen(self) -> None:
        exemption = ModelReviewExemption(
            rule="test",
            path="tests/",
            expires=self._future_date(),
            reason="test",
        )
        with pytest.raises(ValidationError):
            exemption.rule = "modified"  # type: ignore[misc]

    def test_exemption_extra_fields_ignored(self) -> None:
        exemption = ModelReviewExemption(
            rule="test",
            path="tests/",
            expires=self._future_date(),
            reason="test",
            unknown_field="ignored",  # type: ignore[call-arg]
        )
        assert exemption.rule == "test"

    def test_expired_exemption_detected(self) -> None:
        exemption = ModelReviewExemption(
            rule="no-bare-except",
            path="tests/",
            expires=self._past_date(365),
            reason="Old exemption",
        )
        assert exemption.is_expired is True

    def test_future_exemption_not_expired(self) -> None:
        exemption = ModelReviewExemption(
            rule="no-bare-except",
            path="tests/",
            expires=self._future_date(365),
            reason="Future exemption",
        )
        assert exemption.is_expired is False

    def test_invalid_expires_format(self) -> None:
        with pytest.raises(ValidationError, match="expires"):
            ModelReviewExemption(
                rule="test",
                path="tests/",
                expires="not-a-date",
                reason="test",
            )

    def test_invalid_expires_format_us_style(self) -> None:
        with pytest.raises(ValidationError, match="expires"):
            ModelReviewExemption(
                rule="test",
                path="tests/",
                expires="06/01/2026",  # US format not accepted
                reason="test",
            )


# ---------------------------------------------------------------------------
# ModelReviewPolicy tests
# ---------------------------------------------------------------------------


class TestModelReviewPolicy:
    def _make_rule(
        self,
        rule_id: str = "test-rule",
        severity: ReviewSeverity = ReviewSeverity.WARNING,
    ) -> ModelReviewRule:
        return ModelReviewRule(
            id=rule_id,
            severity=severity,
            pattern="test_pattern",
            message="Test message",
        )

    def _future_date(self) -> str:
        return (date.today() + timedelta(days=365)).isoformat()

    def test_valid_policy_minimal(self) -> None:
        policy = ModelReviewPolicy(
            version="1.0",
            rules=[self._make_rule()],
        )
        assert policy.version == "1.0"
        assert policy.enforcement_mode == "observe"
        assert len(policy.rules) == 1
        assert policy.exemptions == []

    def test_policy_all_severity_levels(self) -> None:
        """R3: Example covers all three severity levels."""
        policy = ModelReviewPolicy(
            version="1.0",
            rules=[
                self._make_rule("blocker-rule", ReviewSeverity.BLOCKER),
                self._make_rule("warning-rule", ReviewSeverity.WARNING),
                self._make_rule("info-rule", ReviewSeverity.INFO),
            ],
        )
        severities = {r.severity for r in policy.rules}
        assert severities == {
            ReviewSeverity.BLOCKER,
            ReviewSeverity.WARNING,
            ReviewSeverity.INFO,
        }

    def test_policy_is_frozen(self) -> None:
        policy = ModelReviewPolicy(version="1.0", rules=[])
        with pytest.raises(ValidationError):
            policy.version = "2.0"  # type: ignore[misc]

    def test_policy_extra_fields_ignored(self) -> None:
        policy = ModelReviewPolicy(
            version="1.0",
            rules=[],
            unknown_future_field="ignored",  # type: ignore[call-arg]
        )
        assert policy.version == "1.0"

    def test_policy_requires_version(self) -> None:
        with pytest.raises(ValidationError, match="version"):
            ModelReviewPolicy(rules=[])

    def test_invalid_version_format(self) -> None:
        with pytest.raises(ValidationError):
            ModelReviewPolicy(version="v1.0", rules=[])

    def test_valid_version_formats(self) -> None:
        for ver in ["1.0", "1.0.0", "2.1", "10.0.1"]:
            policy = ModelReviewPolicy(version=ver, rules=[])
            assert policy.version == ver

    def test_valid_enforcement_modes(self) -> None:
        for mode in ["observe", "warn", "block"]:
            policy = ModelReviewPolicy(version="1.0", enforcement_mode=mode, rules=[])
            assert policy.enforcement_mode == mode

    def test_invalid_enforcement_mode(self) -> None:
        with pytest.raises(ValidationError):
            ModelReviewPolicy(version="1.0", enforcement_mode="strict", rules=[])

    def test_default_enforcement_mode_is_observe(self) -> None:
        policy = ModelReviewPolicy(version="1.0", rules=[])
        assert policy.enforcement_mode == "observe"

    def test_duplicate_rule_ids_rejected(self) -> None:
        """R2: Duplicate rule IDs must raise an error."""
        with pytest.raises(ValidationError, match="Duplicate rule IDs"):
            ModelReviewPolicy(
                version="1.0",
                rules=[
                    self._make_rule("duplicate-id"),
                    self._make_rule("duplicate-id"),  # duplicate!
                ],
            )

    def test_exemption_references_unknown_rule(self) -> None:
        """Exemption referencing a non-existent rule should error."""
        with pytest.raises(ValidationError, match="unknown rule IDs"):
            ModelReviewPolicy(
                version="1.0",
                rules=[self._make_rule("real-rule")],
                exemptions=[
                    ModelReviewExemption(
                        rule="nonexistent-rule",
                        path="tests/",
                        expires=self._future_date(),
                        reason="test",
                    )
                ],
            )

    def test_valid_exemptions(self) -> None:
        policy = ModelReviewPolicy(
            version="1.0",
            rules=[self._make_rule("no-bare-except")],
            exemptions=[
                ModelReviewExemption(
                    rule="no-bare-except",
                    path="tests/legacy/",
                    expires=self._future_date(),
                    reason="Legacy test code",
                )
            ],
        )
        assert len(policy.exemptions) == 1

    def test_get_active_rules(self) -> None:
        policy = ModelReviewPolicy(
            version="1.0",
            rules=[
                ModelReviewRule(
                    id="enabled-rule",
                    severity=ReviewSeverity.WARNING,
                    pattern=".",
                    message="test",
                    enabled=True,
                ),
                ModelReviewRule(
                    id="disabled-rule",
                    severity=ReviewSeverity.WARNING,
                    pattern=".",
                    message="test",
                    enabled=False,
                ),
            ],
        )
        active = policy.get_active_rules()
        assert len(active) == 1
        assert active[0].id == "enabled-rule"

    def test_get_fast_rules(self) -> None:
        policy = ModelReviewPolicy(
            version="1.0",
            rules=[
                ModelReviewRule(
                    id="fast-rule",
                    severity=ReviewSeverity.WARNING,
                    pattern=".",
                    message="test",
                    slow=False,
                ),
                ModelReviewRule(
                    id="slow-rule",
                    severity=ReviewSeverity.WARNING,
                    pattern=".",
                    message="test",
                    slow=True,
                ),
            ],
        )
        fast = policy.get_fast_rules()
        assert len(fast) == 1
        assert fast[0].id == "fast-rule"


# ---------------------------------------------------------------------------
# ValidatorPolicy tests
# ---------------------------------------------------------------------------


class TestValidatorPolicy:
    def setup_method(self) -> None:
        self.validator = ValidatorPolicy()

    def _future_date(self, days: int = 365) -> str:
        return (date.today() + timedelta(days=days)).isoformat()

    def _past_date(self, days: int = 1) -> str:
        return (date.today() - timedelta(days=days)).isoformat()

    def test_valid_policy_yaml(self) -> None:
        yaml_content = textwrap.dedent("""
            version: "1.0"
            rules:
              - id: no-bare-except
                severity: BLOCKER
                pattern: "except:"
                message: "Bare except"
        """)
        result = self.validator.validate_yaml_string(yaml_content)
        assert result.is_valid
        assert result.policy is not None
        assert result.policy.version == "1.0"
        assert len(result.errors) == 0

    def test_missing_version_field(self) -> None:
        """R2: Missing required field -> error with field name."""
        yaml_content = textwrap.dedent("""
            rules:
              - id: test
                severity: WARNING
                pattern: "."
                message: "test"
        """)
        result = self.validator.validate_yaml_string(yaml_content)
        assert not result.is_valid
        assert any("version" in e.field for e in result.errors)

    def test_missing_rules_field(self) -> None:
        """R2: Missing required field -> error with field name."""
        yaml_content = 'version: "1.0"'
        result = self.validator.validate_yaml_string(yaml_content)
        assert not result.is_valid
        assert any("rules" in e.field for e in result.errors)

    def test_invalid_severity_enum_error_message(self) -> None:
        """R2: Invalid severity enum -> error listing valid values."""
        yaml_content = textwrap.dedent("""
            version: "1.0"
            rules:
              - id: test
                severity: CRITICAL
                pattern: "."
                message: "test"
        """)
        result = self.validator.validate_yaml_string(yaml_content)
        assert not result.is_valid
        # Error should mention valid values
        error_messages = " ".join(e.message for e in result.errors)
        assert any(val in error_messages for val in ["BLOCKER", "WARNING", "INFO"]), (
            f"Expected valid severity values in error: {error_messages}"
        )

    def test_expired_exemption_is_warning_not_error(self) -> None:
        """R2: Expired exemption -> warning (not error), logs to stderr."""
        yaml_content = textwrap.dedent(f"""
            version: "1.0"
            rules:
              - id: no-bare-except
                severity: BLOCKER
                pattern: "except:"
                message: "Bare except"
            exemptions:
              - rule: no-bare-except
                path: tests/
                expires: "{self._past_date(365)}"
                reason: "Old exemption"
        """)
        result = self.validator.validate_yaml_string(yaml_content)
        # Should be valid (no errors) but have a warning
        assert result.is_valid
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert "expired" in result.warnings[0].message.lower()

    def test_duplicate_rule_ids_error(self) -> None:
        """R2: Duplicate rule IDs -> error."""
        yaml_content = textwrap.dedent("""
            version: "1.0"
            rules:
              - id: duplicate
                severity: WARNING
                pattern: "."
                message: "test1"
              - id: duplicate
                severity: INFO
                pattern: "."
                message: "test2"
        """)
        result = self.validator.validate_yaml_string(yaml_content)
        assert not result.is_valid
        assert any(
            "duplicate" in e.message.lower() or "Duplicate" in e.message
            for e in result.errors
        )

    def test_invalid_yaml_syntax(self) -> None:
        """Invalid YAML -> error with yaml field."""
        result = self.validator.validate_yaml_string("version: [\nunclosed bracket")
        assert not result.is_valid
        assert any(e.field == "yaml" for e in result.errors)

    def test_non_mapping_yaml(self) -> None:
        """YAML that is not a mapping -> error."""
        result = self.validator.validate_yaml_string("- just a list")
        assert not result.is_valid

    def test_valid_policy_with_all_features(self) -> None:
        """Full integration test with rules and exemptions."""
        yaml_content = textwrap.dedent(f"""
            version: "1.0"
            enforcement_mode: warn
            rules:
              - id: no-bare-except
                severity: BLOCKER
                pattern: "except:"
                message: "Bare except"
              - id: no-print
                severity: WARNING
                pattern: "print("
                message: "No print"
              - id: todo-without-ticket
                severity: INFO
                pattern: "TODO"
                message: "Add ticket"
            exemptions:
              - rule: no-print
                path: scripts/
                expires: "{self._future_date()}"
                reason: "CLI scripts need print"
        """)
        result = self.validator.validate_yaml_string(yaml_content)
        assert result.is_valid
        assert result.policy is not None
        assert result.policy.enforcement_mode == "warn"
        assert len(result.policy.rules) == 3
        assert len(result.policy.exemptions) == 1
        assert len(result.warnings) == 0

    def test_validate_file_missing(self) -> None:
        """File that doesn't exist -> error with file field."""
        result = self.validator.validate_file("/nonexistent/path/review_policy.yaml")
        assert not result.is_valid
        assert any(e.field == "file" for e in result.errors)

    def test_example_policy_file_loads(self) -> None:
        """R3: Example policy file must load successfully."""
        from pathlib import Path

        # Walk up from this file to find repo root (contains pyproject.toml)
        current = Path(__file__).resolve()
        repo_root = None
        for parent in current.parents:
            if (parent / "pyproject.toml").exists():
                repo_root = parent
                break

        if repo_root is None:
            pytest.skip("Could not find repo root (no pyproject.toml found in parents)")

        example_path = repo_root / "examples" / "review_policy.example.yaml"

        if not example_path.exists():
            pytest.skip(f"Example policy not found at {example_path}")

        result = self.validator.validate_file(str(example_path))
        # Example has expired exemption for scripts/ (set in past), so warnings expected
        # But it must be valid (no errors)
        assert result.is_valid, f"Example policy errors: {result.errors}"
