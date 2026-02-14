"""Unit tests for EnumInjectionContext and EnumCohort.

This module validates that the Python enums match the database CHECK constraints
defined in migration 007_create_pattern_injections.sql.

Ticket: OMN-1670
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit

from omniintelligence.enums import (
    COHORT_CONTROL_PERCENTAGE,
    COHORT_TREATMENT_PERCENTAGE,
    EnumCohort,
    EnumInjectionContext,
)

# =========================================================================
# Constants: Expected values from SQL migration CHECK constraints
# =========================================================================

# Must match: CHECK (injection_context IN ('SessionStart', 'UserPromptSubmit', 'PreToolUse', 'SubagentStart'))
EXPECTED_INJECTION_CONTEXTS = {
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "SubagentStart",
}

# Must match: CHECK (cohort IN ('control', 'treatment'))
EXPECTED_COHORTS = {
    "control",
    "treatment",
}


# =========================================================================
# Tests: EnumInjectionContext matches DB constraint
# =========================================================================


class TestEnumInjectionContextMatchesDatabase:
    """Validate that Python enum matches SQL CHECK constraint."""

    def test_enum_count_matches_constraint(self) -> None:
        """Verify enum has exactly the same number of values as DB constraint."""
        enum_count = len(EnumInjectionContext)
        expected_count = len(EXPECTED_INJECTION_CONTEXTS)
        assert enum_count == expected_count, (
            f"Enum has {enum_count} values but DB constraint has {expected_count}. "
            "Enum and migration are out of sync."
        )

    def test_all_enum_values_in_constraint(self) -> None:
        """Verify every enum value is in the DB CHECK constraint."""
        for context in EnumInjectionContext:
            assert context.value in EXPECTED_INJECTION_CONTEXTS, (
                f"Enum value '{context.value}' not in DB CHECK constraint. "
                f"Valid contexts: {EXPECTED_INJECTION_CONTEXTS}"
            )

    def test_all_constraint_values_in_enum(self) -> None:
        """Verify every DB constraint value has a corresponding enum member."""
        enum_values = {c.value for c in EnumInjectionContext}
        for context_value in EXPECTED_INJECTION_CONTEXTS:
            assert (
                context_value in enum_values
            ), f"DB constraint value '{context_value}' has no corresponding enum member."

    @pytest.mark.parametrize("context_value", list(EXPECTED_INJECTION_CONTEXTS))
    def test_individual_context_exists(self, context_value: str) -> None:
        """Parametrized test for each expected injection context."""
        enum_values = {c.value for c in EnumInjectionContext}
        assert context_value in enum_values


# =========================================================================
# Tests: EnumCohort matches DB constraint
# =========================================================================


class TestEnumCohortMatchesDatabase:
    """Validate that Python enum matches SQL CHECK constraint."""

    def test_enum_count_matches_constraint(self) -> None:
        """Verify enum has exactly the same number of values as DB constraint."""
        enum_count = len(EnumCohort)
        expected_count = len(EXPECTED_COHORTS)
        assert enum_count == expected_count, (
            f"Enum has {enum_count} values but DB constraint has {expected_count}. "
            "Enum and migration are out of sync."
        )

    def test_all_enum_values_in_constraint(self) -> None:
        """Verify every enum value is in the DB CHECK constraint."""
        for cohort in EnumCohort:
            assert cohort.value in EXPECTED_COHORTS, (
                f"Enum value '{cohort.value}' not in DB CHECK constraint. "
                f"Valid cohorts: {EXPECTED_COHORTS}"
            )

    def test_all_constraint_values_in_enum(self) -> None:
        """Verify every DB constraint value has a corresponding enum member."""
        enum_values = {c.value for c in EnumCohort}
        for cohort_value in EXPECTED_COHORTS:
            assert (
                cohort_value in enum_values
            ), f"DB constraint value '{cohort_value}' has no corresponding enum member."

    @pytest.mark.parametrize("cohort_value", list(EXPECTED_COHORTS))
    def test_individual_cohort_exists(self, cohort_value: str) -> None:
        """Parametrized test for each expected cohort."""
        enum_values = {c.value for c in EnumCohort}
        assert cohort_value in enum_values


# =========================================================================
# Tests: Enum properties
# =========================================================================


class TestEnumInjectionContextProperties:
    """Test EnumInjectionContext behavior and properties."""

    def test_enum_is_str_based(self) -> None:
        """Verify enum values are strings (for JSON serialization)."""
        for context in EnumInjectionContext:
            assert isinstance(context.value, str)

    def test_enum_values_are_pascal_case(self) -> None:
        """Verify values use PascalCase (matching hook event convention)."""
        for context in EnumInjectionContext:
            # PascalCase: first letter uppercase, no underscores
            assert context.value[
                0
            ].isupper(), f"'{context.value}' should start uppercase"
            assert (
                "_" not in context.value
            ), f"'{context.value}' should not contain underscores"

    def test_enum_can_be_constructed_from_string(self) -> None:
        """Verify enum can be constructed from string value."""
        context = EnumInjectionContext("SessionStart")
        assert context == EnumInjectionContext.SESSION_START

    def test_enum_exports_from_package(self) -> None:
        """Verify enum is properly exported from enums package."""
        from omniintelligence.enums import EnumInjectionContext as ExportedEnum

        assert ExportedEnum is EnumInjectionContext


class TestEnumCohortProperties:
    """Test EnumCohort behavior and properties."""

    def test_enum_is_str_based(self) -> None:
        """Verify enum values are strings (for JSON serialization)."""
        for cohort in EnumCohort:
            assert isinstance(cohort.value, str)

    def test_enum_values_are_lowercase(self) -> None:
        """Verify values use lowercase (DB convention)."""
        for cohort in EnumCohort:
            assert (
                cohort.value == cohort.value.lower()
            ), f"Enum value '{cohort.value}' should be lowercase"

    def test_enum_can_be_constructed_from_string(self) -> None:
        """Verify enum can be constructed from string value."""
        cohort = EnumCohort("treatment")
        assert cohort == EnumCohort.TREATMENT

    def test_enum_exports_from_package(self) -> None:
        """Verify enum is properly exported from enums package."""
        from omniintelligence.enums import EnumCohort as ExportedEnum

        assert ExportedEnum is EnumCohort


# =========================================================================
# Tests: Cohort percentage constants
# =========================================================================


class TestCohortPercentages:
    """Test cohort percentage constants are valid."""

    def test_percentages_sum_to_100(self) -> None:
        """Verify control + treatment = 100%."""
        total = COHORT_CONTROL_PERCENTAGE + COHORT_TREATMENT_PERCENTAGE
        assert total == 100, f"Cohort percentages sum to {total}, expected 100"

    def test_control_percentage_is_20(self) -> None:
        """Verify control cohort is 20% as per plan."""
        assert COHORT_CONTROL_PERCENTAGE == 20

    def test_treatment_percentage_is_80(self) -> None:
        """Verify treatment cohort is 80% as per plan."""
        assert COHORT_TREATMENT_PERCENTAGE == 80

    def test_percentages_exported_from_package(self) -> None:
        """Verify percentages are exported from enums package."""
        from omniintelligence.enums import (
            COHORT_CONTROL_PERCENTAGE as EXPORTED_CONTROL,
        )
        from omniintelligence.enums import (
            COHORT_TREATMENT_PERCENTAGE as EXPORTED_TREATMENT,
        )

        assert EXPORTED_CONTROL == 20
        assert EXPORTED_TREATMENT == 80


# =========================================================================
# Tests: Migration file validation
# =========================================================================


class TestInjectionMigrationFile:
    """Validate consistency with SQL migration file."""

    @pytest.fixture
    def migration_path(self, migrations_dir: Path) -> Path:
        """Path to the pattern_injections migration."""
        return migrations_dir / "007_create_pattern_injections.sql"

    def test_migration_file_exists(self, migration_path: Path) -> None:
        """Verify the migration file exists."""
        assert migration_path.exists(), f"Migration file not found: {migration_path}"

    def test_migration_contains_all_contexts(self, migration_path: Path) -> None:
        """Verify migration CHECK constraint contains all expected contexts."""
        if not migration_path.exists():
            pytest.skip("Migration file not found")

        content = migration_path.read_text()

        for context_value in EXPECTED_INJECTION_CONTEXTS:
            assert (
                f"'{context_value}'" in content
            ), f"Injection context '{context_value}' not found in migration file"

    def test_migration_contains_all_cohorts(self, migration_path: Path) -> None:
        """Verify migration CHECK constraint contains all expected cohorts."""
        if not migration_path.exists():
            pytest.skip("Migration file not found")

        content = migration_path.read_text()

        for cohort_value in EXPECTED_COHORTS:
            assert (
                f"'{cohort_value}'" in content
            ), f"Cohort '{cohort_value}' not found in migration file"
