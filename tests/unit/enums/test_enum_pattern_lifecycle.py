"""Unit tests for EnumPatternLifecycleStatus.

This module validates that the Python enum matches the database CHECK constraint
defined in migration 005_create_learned_patterns.sql.

Ticket: OMN-1667
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omniintelligence.enums import EnumPatternLifecycleStatus


# =========================================================================
# Constants: Expected values from SQL migration CHECK constraint
# =========================================================================

# These must match the CHECK constraint in 005_create_learned_patterns.sql:
# CHECK (status IN ('candidate', 'provisional', 'validated', 'deprecated'))
EXPECTED_STATUSES = frozenset({
    "candidate",
    "provisional",
    "validated",
    "deprecated",
})

EXPECTED_COUNT = 4


# =========================================================================
# Tests: Enum matches DB CHECK constraint
# =========================================================================


@pytest.mark.unit
class TestEnumPatternLifecycleStatusMatchesDatabase:
    """Validate that Python enum matches SQL CHECK constraint."""

    def test_enum_count_matches_check_constraint(self) -> None:
        """Verify enum has exactly 4 values as defined in CHECK constraint."""
        enum_count = len(EnumPatternLifecycleStatus)
        assert enum_count == EXPECTED_COUNT, (
            f"Enum has {enum_count} values but CHECK constraint has {EXPECTED_COUNT}. "
            "Enum and migration are out of sync."
        )

    def test_all_enum_values_in_check_constraint(self) -> None:
        """Verify every enum value exists in the CHECK constraint."""
        for status in EnumPatternLifecycleStatus:
            assert status.value in EXPECTED_STATUSES, (
                f"Enum value '{status.value}' not found in CHECK constraint. "
                f"Valid statuses: {sorted(EXPECTED_STATUSES)}"
            )

    def test_all_check_constraint_values_in_enum(self) -> None:
        """Verify every CHECK constraint value has a corresponding enum member."""
        enum_values = {s.value for s in EnumPatternLifecycleStatus}
        for status in EXPECTED_STATUSES:
            assert status in enum_values, (
                f"CHECK constraint status '{status}' has no corresponding enum member. "
                f"Add {status.upper()} to EnumPatternLifecycleStatus."
            )

    @pytest.mark.parametrize(
        "status",
        sorted(EXPECTED_STATUSES),
    )
    def test_individual_status_exists(self, status: str) -> None:
        """Parametrized test for each expected status."""
        enum_values = {s.value for s in EnumPatternLifecycleStatus}
        assert status in enum_values

    def test_exact_values_match(self) -> None:
        """Verify exact bidirectional match between enum and CHECK constraint."""
        enum_values = {s.value for s in EnumPatternLifecycleStatus}
        assert enum_values == EXPECTED_STATUSES, (
            f"Mismatch between enum values and CHECK constraint. "
            f"Enum: {sorted(enum_values)}, "
            f"CHECK: {sorted(EXPECTED_STATUSES)}"
        )


# =========================================================================
# Tests: Enum properties
# =========================================================================


@pytest.mark.unit
class TestEnumPatternLifecycleStatusProperties:
    """Test enum behavior and properties."""

    def test_enum_is_str_based(self) -> None:
        """Verify enum values are strings (for JSON serialization)."""
        for status in EnumPatternLifecycleStatus:
            assert isinstance(status.value, str)

    def test_enum_inherits_from_str(self) -> None:
        """Verify enum inherits from str for direct string comparison."""
        assert issubclass(EnumPatternLifecycleStatus, str)

    def test_enum_values_are_lowercase(self) -> None:
        """Verify all enum values use lowercase (DB convention)."""
        for status in EnumPatternLifecycleStatus:
            assert status.value == status.value.lower(), (
                f"Enum value '{status.value}' should be lowercase"
            )

    def test_enum_names_are_uppercase(self) -> None:
        """Verify all enum names use SCREAMING_SNAKE_CASE."""
        for status in EnumPatternLifecycleStatus:
            assert status.name == status.name.upper(), (
                f"Enum name '{status.name}' should be SCREAMING_SNAKE_CASE"
            )

    def test_enum_can_be_constructed_from_string(self) -> None:
        """Verify enum can be constructed from string value."""
        status = EnumPatternLifecycleStatus("candidate")
        assert status == EnumPatternLifecycleStatus.CANDIDATE

    def test_all_enum_values_constructible_from_string(self) -> None:
        """Verify all enum values can be constructed from their string values."""
        for expected in EXPECTED_STATUSES:
            status = EnumPatternLifecycleStatus(expected)
            assert status.value == expected

    def test_enum_value_access(self) -> None:
        """Verify enum value can be accessed directly."""
        status = EnumPatternLifecycleStatus.CANDIDATE
        assert status.value == "candidate"
        # str(enum) returns full name, use .value for raw string
        assert status == "candidate"  # Works due to str inheritance

    def test_enum_comparison_with_string(self) -> None:
        """Verify enum can be compared directly with strings."""
        assert EnumPatternLifecycleStatus.CANDIDATE == "candidate"
        assert EnumPatternLifecycleStatus.PROVISIONAL == "provisional"
        assert EnumPatternLifecycleStatus.VALIDATED == "validated"
        assert EnumPatternLifecycleStatus.DEPRECATED == "deprecated"

    def test_enum_exports_from_package(self) -> None:
        """Verify enum is properly exported from enums package."""
        from omniintelligence.enums import EnumPatternLifecycleStatus as ExportedEnum

        assert ExportedEnum is EnumPatternLifecycleStatus


# =========================================================================
# Tests: Specific enum members
# =========================================================================


@pytest.mark.unit
class TestEnumPatternLifecycleStatusMembers:
    """Test specific enum member existence and values."""

    def test_candidate_member(self) -> None:
        """Verify CANDIDATE member exists with correct value."""
        assert hasattr(EnumPatternLifecycleStatus, "CANDIDATE")
        assert EnumPatternLifecycleStatus.CANDIDATE.value == "candidate"

    def test_provisional_member(self) -> None:
        """Verify PROVISIONAL member exists with correct value."""
        assert hasattr(EnumPatternLifecycleStatus, "PROVISIONAL")
        assert EnumPatternLifecycleStatus.PROVISIONAL.value == "provisional"

    def test_validated_member(self) -> None:
        """Verify VALIDATED member exists with correct value."""
        assert hasattr(EnumPatternLifecycleStatus, "VALIDATED")
        assert EnumPatternLifecycleStatus.VALIDATED.value == "validated"

    def test_deprecated_member(self) -> None:
        """Verify DEPRECATED member exists with correct value."""
        assert hasattr(EnumPatternLifecycleStatus, "DEPRECATED")
        assert EnumPatternLifecycleStatus.DEPRECATED.value == "deprecated"


# =========================================================================
# Tests: Migration file validation
# =========================================================================


@pytest.mark.unit
class TestLearnedPatternsMigrationFile:
    """Validate consistency with SQL migration file."""

    @pytest.fixture
    def migration_path(self, migrations_dir: Path) -> Path:
        """Path to the learned_patterns migration.

        Uses the migrations_dir fixture from conftest.py for robust path resolution.
        """
        return migrations_dir / "005_create_learned_patterns.sql"

    def test_migration_file_exists(self, migration_path: Path) -> None:
        """Verify the migration file exists."""
        assert migration_path.exists(), f"Migration file not found: {migration_path}"

    def test_migration_contains_check_constraint(self, migration_path: Path) -> None:
        """Verify migration contains the status CHECK constraint."""
        if not migration_path.exists():
            pytest.skip("Migration file not found")

        content = migration_path.read_text()

        # Verify CHECK constraint syntax exists
        assert "CHECK (status IN (" in content, (
            "CHECK constraint for status not found in migration"
        )

    def test_migration_contains_all_statuses(self, migration_path: Path) -> None:
        """Verify migration CHECK constraint contains all expected statuses."""
        if not migration_path.exists():
            pytest.skip("Migration file not found")

        content = migration_path.read_text()

        for status in EXPECTED_STATUSES:
            assert f"'{status}'" in content, (
                f"Status '{status}' not found in migration CHECK constraint"
            )

    def test_migration_default_is_candidate(self, migration_path: Path) -> None:
        """Verify migration sets 'candidate' as default status."""
        if not migration_path.exists():
            pytest.skip("Migration file not found")

        content = migration_path.read_text()

        assert "DEFAULT 'candidate'" in content, (
            "Default status should be 'candidate' in migration"
        )
