"""
Unit Tests for Hash Resolver Service

Comprehensive test coverage for hash-based entity ID generation.
Tests include:
- Entity ID generation (FILE, ENTITY, RELATIONSHIP)
- Format validation
- Deprecated format detection
- Error handling
- Edge cases and boundary conditions

Author: Archon Intelligence Team
Date: 2025-11-09
"""

import hashlib
import re

import pytest
from src.utils.hash_resolver import (
    EntityType,
    HashConfig,
    HashResolver,
    generate_file_entity_id,
    validate_entity_id_format,
)


class TestHashResolverInitialization:
    """Test HashResolver initialization and configuration."""

    def test_default_initialization(self) -> None:
        """Test HashResolver initializes with default configuration."""
        resolver = HashResolver()

        assert resolver.config is not None
        assert resolver.config.file_hash_length == 24
        assert resolver.config.entity_hash_length == 16
        assert resolver.config.relationship_hash_length == 16

    def test_custom_configuration(self) -> None:
        """Test HashResolver accepts custom configuration."""
        custom_config = HashConfig(
            file_hash_length=16, entity_hash_length=20, relationship_hash_length=20
        )
        resolver = HashResolver(config=custom_config)

        assert resolver.config.file_hash_length == 16
        assert resolver.config.entity_hash_length == 20
        assert resolver.config.relationship_hash_length == 20

    def test_config_validation_odd_length(self) -> None:
        """Test configuration validation rejects odd hash lengths."""
        with pytest.raises(ValueError, match="Hash length must be even"):
            HashConfig(file_hash_length=13)


class TestFileEntityIDGeneration:
    """Test FILE entity ID generation."""

    def test_generate_file_entity_id_basic(self) -> None:
        """Test basic file entity ID generation."""
        resolver = HashResolver()

        entity_id = resolver.generate_file_entity_id(
            file_path="/services/intelligence/main.py", project_name="archon"
        )

        # Verify format: file_{24_hex_chars}
        assert entity_id.startswith("file_")
        assert len(entity_id) == 29  # "file_" (5) + 24 hex chars
        assert re.match(r"^file_[a-f0-9]{24}$", entity_id)

    def test_generate_file_entity_id_deterministic(self) -> None:
        """Test file entity ID generation is deterministic."""
        resolver = HashResolver()

        entity_id_1 = resolver.generate_file_entity_id(
            file_path="/services/intelligence/main.py", project_name="archon"
        )
        entity_id_2 = resolver.generate_file_entity_id(
            file_path="/services/intelligence/main.py", project_name="archon"
        )

        # Same input should produce same output
        assert entity_id_1 == entity_id_2

    def test_generate_file_entity_id_different_paths(self) -> None:
        """Test different file paths produce different entity IDs."""
        resolver = HashResolver()

        entity_id_1 = resolver.generate_file_entity_id(
            file_path="/services/intelligence/main.py", project_name="archon"
        )
        entity_id_2 = resolver.generate_file_entity_id(
            file_path="/services/bridge/app.py", project_name="archon"
        )

        # Different paths should produce different IDs
        assert entity_id_1 != entity_id_2

    def test_generate_file_entity_id_different_projects(self) -> None:
        """Test same path in different projects produces different entity IDs."""
        resolver = HashResolver()

        entity_id_1 = resolver.generate_file_entity_id(
            file_path="/services/main.py", project_name="archon"
        )
        entity_id_2 = resolver.generate_file_entity_id(
            file_path="/services/main.py", project_name="omninode"
        )

        # Same path, different project should produce different IDs
        assert entity_id_1 != entity_id_2

    def test_generate_file_entity_id_empty_path(self) -> None:
        """Test file entity ID generation rejects empty file path."""
        resolver = HashResolver()

        with pytest.raises(ValueError, match="file_path cannot be empty"):
            resolver.generate_file_entity_id(file_path="", project_name="archon")

    def test_generate_file_entity_id_empty_project(self) -> None:
        """Test file entity ID generation rejects empty project name."""
        resolver = HashResolver()

        with pytest.raises(ValueError, match="project_name cannot be empty"):
            resolver.generate_file_entity_id(
                file_path="/services/main.py", project_name=""
            )

    def test_resolve_path_to_entity_id(self) -> None:
        """Test resolve_path_to_entity_id is equivalent to generate_file_entity_id."""
        resolver = HashResolver()

        entity_id_generate = resolver.generate_file_entity_id(
            file_path="/services/main.py", project_name="archon"
        )
        entity_id_resolve = resolver.resolve_path_to_entity_id(
            file_path="/services/main.py", project_name="archon"
        )

        assert entity_id_generate == entity_id_resolve


class TestEntityIDGeneration:
    """Test ENTITY entity ID generation."""

    def test_generate_entity_id_basic(self) -> None:
        """Test basic entity ID generation."""
        resolver = HashResolver()

        entity_id = resolver.generate_entity_id(entity_name="MyClass")

        # Verify format: entity-{16_hex_chars}
        assert entity_id.startswith("entity-")
        assert len(entity_id) == 23  # "entity-" (7) + 16 hex chars
        assert re.match(r"^entity-[a-f0-9]{16}$", entity_id)

    def test_generate_entity_id_deterministic(self) -> None:
        """Test entity ID generation is deterministic."""
        resolver = HashResolver()

        entity_id_1 = resolver.generate_entity_id(entity_name="MyClass")
        entity_id_2 = resolver.generate_entity_id(entity_name="MyClass")

        assert entity_id_1 == entity_id_2

    def test_generate_entity_id_with_source_path(self) -> None:
        """Test entity ID generation includes source path for disambiguation."""
        resolver = HashResolver()

        entity_id_1 = resolver.generate_entity_id(
            entity_name="MyClass", source_path="/app/models.py"
        )
        entity_id_2 = resolver.generate_entity_id(
            entity_name="MyClass", source_path="/app/views.py"
        )

        # Same entity name, different source paths should produce different IDs
        assert entity_id_1 != entity_id_2

    def test_generate_entity_id_without_and_with_source_path(self) -> None:
        """Test entity ID differs when source path is included."""
        resolver = HashResolver()

        entity_id_without_path = resolver.generate_entity_id(entity_name="MyClass")
        entity_id_with_path = resolver.generate_entity_id(
            entity_name="MyClass", source_path="/app/models.py"
        )

        # Should be different
        assert entity_id_without_path != entity_id_with_path

    def test_generate_entity_id_empty_name(self) -> None:
        """Test entity ID generation rejects empty entity name."""
        resolver = HashResolver()

        with pytest.raises(ValueError, match="entity_name cannot be empty"):
            resolver.generate_entity_id(entity_name="")


class TestRelationshipIDGeneration:
    """Test RELATIONSHIP relationship ID generation."""

    def test_generate_relationship_id_basic(self) -> None:
        """Test basic relationship ID generation."""
        resolver = HashResolver()

        relationship_id = resolver.generate_relationship_id(
            source_entity_id="file_a1b2c3d4e5f6",
            target_entity_id="entity-91f521860bc3a4d5",
        )

        # Verify format: rel-{16_hex_chars}
        assert relationship_id.startswith("rel-")
        assert len(relationship_id) == 20  # "rel-" (4) + 16 hex chars
        assert re.match(r"^rel-[a-f0-9]{16}$", relationship_id)

    def test_generate_relationship_id_deterministic(self) -> None:
        """Test relationship ID generation is deterministic."""
        resolver = HashResolver()

        relationship_id_1 = resolver.generate_relationship_id(
            source_entity_id="file_a1b2c3d4e5f6",
            target_entity_id="entity-91f521860bc3a4d5",
        )
        relationship_id_2 = resolver.generate_relationship_id(
            source_entity_id="file_a1b2c3d4e5f6",
            target_entity_id="entity-91f521860bc3a4d5",
        )

        assert relationship_id_1 == relationship_id_2

    def test_generate_relationship_id_different_entities(self) -> None:
        """Test different entity pairs produce different relationship IDs."""
        resolver = HashResolver()

        relationship_id_1 = resolver.generate_relationship_id(
            source_entity_id="file_a1b2c3d4e5f6",
            target_entity_id="entity-91f521860bc3a4d5",
        )
        relationship_id_2 = resolver.generate_relationship_id(
            source_entity_id="file_a1b2c3d4e5f6",
            target_entity_id="entity-7f3e4d5a6b8c9d0e",
        )

        assert relationship_id_1 != relationship_id_2

    def test_generate_relationship_id_empty_source(self) -> None:
        """Test relationship ID generation rejects empty source entity ID."""
        resolver = HashResolver()

        with pytest.raises(ValueError, match="source_entity_id cannot be empty"):
            resolver.generate_relationship_id(
                source_entity_id="", target_entity_id="entity-91f521860bc3a4d5"
            )

    def test_generate_relationship_id_empty_target(self) -> None:
        """Test relationship ID generation rejects empty target entity ID."""
        resolver = HashResolver()

        with pytest.raises(ValueError, match="target_entity_id cannot be empty"):
            resolver.generate_relationship_id(
                source_entity_id="file_a1b2c3d4e5f6", target_entity_id=""
            )


class TestEntityIDFormatValidation:
    """Test entity ID format validation."""

    def test_validate_file_entity_id_valid(self) -> None:
        """Test validation accepts valid FILE entity IDs."""
        resolver = HashResolver()

        assert resolver.validate_entity_id_format("file_a1b2c3d4e5f6", EntityType.FILE)
        assert resolver.validate_entity_id_format("file_0123456789ab", EntityType.FILE)

    def test_validate_file_entity_id_invalid(self) -> None:
        """Test validation rejects invalid FILE entity IDs."""
        resolver = HashResolver()

        # Path-based format (deprecated)
        assert not resolver.validate_entity_id_format(
            "file:archon:/main.py", EntityType.FILE
        )

        # Wrong length
        assert not resolver.validate_entity_id_format("file_abc", EntityType.FILE)

        # Wrong prefix
        assert not resolver.validate_entity_id_format(
            "entity-a1b2c3d4e5f6", EntityType.FILE
        )

        # Uppercase hex (invalid)
        assert not resolver.validate_entity_id_format(
            "file_A1B2C3D4E5F6", EntityType.FILE
        )

    def test_validate_entity_id_valid(self) -> None:
        """Test validation accepts valid ENTITY entity IDs."""
        resolver = HashResolver()

        assert resolver.validate_entity_id_format(
            "entity-91f521860bc3a4d5", EntityType.ENTITY
        )
        assert resolver.validate_entity_id_format(
            "entity-0123456789abcdef", EntityType.ENTITY
        )

    def test_validate_entity_id_invalid(self) -> None:
        """Test validation rejects invalid ENTITY entity IDs."""
        resolver = HashResolver()

        # Wrong length
        assert not resolver.validate_entity_id_format("entity-abc", EntityType.ENTITY)

        # Wrong prefix
        assert not resolver.validate_entity_id_format(
            "file_91f521860bc3a4d5", EntityType.ENTITY
        )

        # MD5 format (deprecated)
        assert not resolver.validate_entity_id_format(
            "entity_91f52186_0bc3a4d5", EntityType.ENTITY
        )

    def test_validate_relationship_id_valid(self) -> None:
        """Test validation accepts valid RELATIONSHIP relationship IDs."""
        resolver = HashResolver()

        assert resolver.validate_entity_id_format(
            "rel-7f3e4d5a6b8c9d0e", EntityType.RELATIONSHIP
        )

    def test_validate_relationship_id_invalid(self) -> None:
        """Test validation rejects invalid RELATIONSHIP relationship IDs."""
        resolver = HashResolver()

        assert not resolver.validate_entity_id_format(
            "rel-abc", EntityType.RELATIONSHIP
        )
        assert not resolver.validate_entity_id_format(
            "file_7f3e4d5a6b8c9d0e", EntityType.RELATIONSHIP
        )


class TestDeprecatedFormatDetection:
    """Test deprecated format detection."""

    def test_detect_path_based_format(self) -> None:
        """Test detection of deprecated path-based format."""
        resolver = HashResolver()

        is_deprecated, description = resolver.detect_deprecated_format(
            "file:archon:/services/main.py"
        )

        assert is_deprecated is True
        assert "path-based" in description.lower()

    def test_detect_md5_format(self) -> None:
        """Test detection of deprecated MD5-based format."""
        resolver = HashResolver()

        is_deprecated, description = resolver.detect_deprecated_format(
            "entity_91f52186_0bc3a4d5"
        )

        assert is_deprecated is True
        assert "md5" in description.lower()

    def test_detect_current_format(self) -> None:
        """Test current hash-based format is not flagged as deprecated."""
        resolver = HashResolver()

        # FILE format
        is_deprecated, description = resolver.detect_deprecated_format(
            "file_a1b2c3d4e5f6"
        )
        assert is_deprecated is False
        assert "current" in description.lower()

        # ENTITY format
        is_deprecated, description = resolver.detect_deprecated_format(
            "entity-91f521860bc3a4d5"
        )
        assert is_deprecated is False
        assert "current" in description.lower()


class TestEnforceFormat:
    """Test format enforcement."""

    def test_enforce_format_valid(self) -> None:
        """Test enforce_format accepts valid entity IDs."""
        resolver = HashResolver()

        # Should not raise exception
        resolver.enforce_format("file_a1b2c3d4e5f6", EntityType.FILE)
        resolver.enforce_format("entity-91f521860bc3a4d5", EntityType.ENTITY)
        resolver.enforce_format("rel-7f3e4d5a6b8c9d0e", EntityType.RELATIONSHIP)

    def test_enforce_format_invalid_raises_error(self) -> None:
        """Test enforce_format raises ValueError for invalid entity IDs."""
        resolver = HashResolver()

        with pytest.raises(ValueError, match="Invalid FILE entity_id format"):
            resolver.enforce_format("invalid_format", EntityType.FILE)

    def test_enforce_format_deprecated_raises_error(self) -> None:
        """Test enforce_format raises ValueError for deprecated formats."""
        resolver = HashResolver()

        with pytest.raises(
            ValueError, match="uses path-based format.*migrate to hash-based"
        ):
            resolver.enforce_format("file:archon:/main.py", EntityType.FILE)


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_generate_file_entity_id_function(self) -> None:
        """Test convenience function for file entity ID generation."""
        entity_id = generate_file_entity_id(
            file_path="/services/main.py", project_name="archon"
        )

        assert entity_id.startswith("file_")
        assert len(entity_id) == 17

    def test_validate_entity_id_format_function(self) -> None:
        """Test convenience function for format validation."""
        assert validate_entity_id_format("file_a1b2c3d4e5f6", EntityType.FILE)
        assert not validate_entity_id_format("invalid_format", EntityType.FILE)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_unicode_file_path(self) -> None:
        """Test handling of Unicode characters in file paths."""
        resolver = HashResolver()

        entity_id = resolver.generate_file_entity_id(
            file_path="/services/тест.py", project_name="archon"
        )

        # Should generate valid entity ID
        assert entity_id.startswith("file_")
        assert re.match(r"^file_[a-f0-9]{12}$", entity_id)

    def test_special_characters_in_entity_name(self) -> None:
        """Test handling of special characters in entity names."""
        resolver = HashResolver()

        entity_id = resolver.generate_entity_id(entity_name="My::Namespaced::Class")

        # Should generate valid entity ID
        assert entity_id.startswith("entity-")
        assert re.match(r"^entity-[a-f0-9]{16}$", entity_id)

    def test_very_long_file_path(self) -> None:
        """Test handling of very long file paths."""
        resolver = HashResolver()

        long_path = "/services/" + "a" * 1000 + "/main.py"
        entity_id = resolver.generate_file_entity_id(
            file_path=long_path, project_name="archon"
        )

        # Should still generate fixed-length entity ID
        assert len(entity_id) == 17

    def test_blake2b_hash_manual_verification(self) -> None:
        """Test BLAKE2b hash computation matches manual calculation."""
        resolver = HashResolver()

        # Manual BLAKE2b calculation
        hash_input = "archon:/services/main.py"
        manual_hash = hashlib.blake2b(
            hash_input.encode("utf-8"), digest_size=6
        ).hexdigest()
        manual_entity_id = f"file_{manual_hash}"

        # HashResolver calculation
        resolver_entity_id = resolver.generate_file_entity_id(
            file_path="/services/main.py", project_name="archon"
        )

        # Should match
        assert resolver_entity_id == manual_entity_id
