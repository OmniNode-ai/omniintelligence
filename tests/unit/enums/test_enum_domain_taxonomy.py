"""Unit tests for EnumDomainTaxonomy.

This module validates that the Python enum matches the database seed data
defined in migration 004_create_domain_taxonomy.sql.

Ticket: OMN-1666
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omniintelligence.enums import DOMAIN_TAXONOMY_VERSION, EnumDomainTaxonomy


# =========================================================================
# Constants: Expected seed data from SQL migration
# =========================================================================

# These must match the INSERT statement in 004_create_domain_taxonomy.sql
EXPECTED_DOMAINS = {
    "code_generation": "Creating new code",
    "code_review": "Reviewing existing code",
    "debugging": "Finding and fixing bugs",
    "testing": "Writing or running tests",
    "documentation": "Writing docs or comments",
    "refactoring": "Restructuring existing code",
    "architecture": "System design decisions",
    "devops": "CI/CD, deployment, infra",
    "data_analysis": "Data processing and analysis",
    "general": "General purpose tasks",
}

EXPECTED_VERSION = "1.0"


# =========================================================================
# Tests: Enum matches DB seed data
# =========================================================================


class TestEnumDomainTaxonomyMatchesDatabase:
    """Validate that Python enum matches SQL seed data."""

    def test_version_matches(self) -> None:
        """Verify DOMAIN_TAXONOMY_VERSION matches expected version."""
        assert DOMAIN_TAXONOMY_VERSION == EXPECTED_VERSION

    def test_enum_count_matches_seed_data(self) -> None:
        """Verify enum has exactly the same number of values as DB seed."""
        enum_count = len(EnumDomainTaxonomy)
        expected_count = len(EXPECTED_DOMAINS)
        assert enum_count == expected_count, (
            f"Enum has {enum_count} values but DB seed has {expected_count}. "
            "Enum and migration are out of sync."
        )

    def test_all_enum_values_in_seed_data(self) -> None:
        """Verify every enum value exists in the DB seed data."""
        for domain in EnumDomainTaxonomy:
            assert domain.value in EXPECTED_DOMAINS, (
                f"Enum value '{domain.value}' not found in DB seed data. "
                f"Valid domains: {list(EXPECTED_DOMAINS.keys())}"
            )

    def test_all_seed_data_in_enum(self) -> None:
        """Verify every DB seed value has a corresponding enum member."""
        enum_values = {d.value for d in EnumDomainTaxonomy}
        for domain_id in EXPECTED_DOMAINS:
            assert domain_id in enum_values, (
                f"DB seed domain '{domain_id}' has no corresponding enum member. "
                f"Add {domain_id.upper()} to EnumDomainTaxonomy."
            )

    @pytest.mark.parametrize(
        "domain_id",
        list(EXPECTED_DOMAINS.keys()),
    )
    def test_individual_domain_exists(self, domain_id: str) -> None:
        """Parametrized test for each expected domain."""
        enum_values = {d.value for d in EnumDomainTaxonomy}
        assert domain_id in enum_values


# =========================================================================
# Tests: Enum properties
# =========================================================================


class TestEnumDomainTaxonomyProperties:
    """Test enum behavior and properties."""

    def test_enum_is_str_based(self) -> None:
        """Verify enum values are strings (for JSON serialization)."""
        for domain in EnumDomainTaxonomy:
            assert isinstance(domain.value, str)

    def test_enum_values_are_lowercase(self) -> None:
        """Verify all enum values use lowercase (DB convention)."""
        for domain in EnumDomainTaxonomy:
            assert domain.value == domain.value.lower(), (
                f"Enum value '{domain.value}' should be lowercase"
            )

    def test_enum_names_are_uppercase(self) -> None:
        """Verify all enum names use SCREAMING_SNAKE_CASE."""
        for domain in EnumDomainTaxonomy:
            assert domain.name == domain.name.upper(), (
                f"Enum name '{domain.name}' should be SCREAMING_SNAKE_CASE"
            )

    def test_enum_can_be_constructed_from_string(self) -> None:
        """Verify enum can be constructed from string value."""
        domain = EnumDomainTaxonomy("code_generation")
        assert domain == EnumDomainTaxonomy.CODE_GENERATION

    def test_enum_value_access(self) -> None:
        """Verify enum value can be accessed directly."""
        domain = EnumDomainTaxonomy.CODE_GENERATION
        assert domain.value == "code_generation"
        # str(enum) returns full name, use .value for raw string
        assert domain == "code_generation"  # Works due to str inheritance

    def test_enum_exports_from_package(self) -> None:
        """Verify enum is properly exported from enums package."""
        from omniintelligence.enums import EnumDomainTaxonomy as ExportedEnum

        assert ExportedEnum is EnumDomainTaxonomy


# =========================================================================
# Tests: Migration file validation
# =========================================================================


class TestDomainTaxonomyMigrationFile:
    """Validate consistency with SQL migration file."""

    @pytest.fixture
    def migration_path(self, migrations_dir: Path) -> Path:
        """Path to the domain taxonomy migration.

        Uses the migrations_dir fixture from conftest.py for robust path resolution.
        """
        return migrations_dir / "004_create_domain_taxonomy.sql"

    def test_migration_file_exists(self, migration_path: Path) -> None:
        """Verify the migration file exists."""
        assert migration_path.exists(), f"Migration file not found: {migration_path}"

    def test_migration_contains_all_domains(self, migration_path: Path) -> None:
        """Verify migration INSERT statement contains all expected domains."""
        if not migration_path.exists():
            pytest.skip("Migration file not found")

        content = migration_path.read_text()

        for domain_id in EXPECTED_DOMAINS:
            assert f"'{domain_id}'" in content, (
                f"Domain '{domain_id}' not found in migration file"
            )
