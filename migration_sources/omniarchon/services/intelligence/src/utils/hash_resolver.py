"""
Hash Resolver Service for Entity ID Generation

Provides centralized, deterministic hash-based entity ID generation using BLAKE3
algorithm by default (with BLAKE2b fallback). Ensures consistency across the
intelligence pipeline by standardizing entity_id format for FILE, Entity, and
Relationship nodes.

Key Features:
- BLAKE3 algorithm for fast, secure hashing (default)
- BLAKE2b fallback if BLAKE3 library not installed
- Deterministic entity IDs (same input → same output)
- Type-safe with comprehensive type hints
- Validates entity_id format compliance
- Supports multiple entity types (FILE, Entity, Relationship)

Usage:
    from utils.hash_resolver import HashResolver, EntityType

    resolver = HashResolver()

    # Generate file entity ID
    file_id = resolver.generate_file_entity_id(
        file_path="/services/intelligence/main.py",
        project_name="archon"
    )
    # Result: "file_a1b2c3d4e5f6" (12-character hash)

    # Validate entity ID format
    is_valid = resolver.validate_entity_id_format(
        entity_id="file_a1b2c3d4e5f6",
        entity_type=EntityType.FILE
    )
    # Result: True

Author: Archon Intelligence Team
Date: 2025-11-10
Version: 1.1.0
"""

import hashlib
import re
from enum import Enum
from typing import Optional, Tuple

from pydantic import BaseModel, Field, field_validator

# ============================================================================
# Entity Type Definitions
# ============================================================================


class EntityType(str, Enum):
    """Supported entity types for hash-based ID generation."""

    FILE = "FILE"
    ENTITY = "ENTITY"
    RELATIONSHIP = "RELATIONSHIP"
    DIRECTORY = "DIRECTORY"


class HashAlgorithm(str, Enum):
    """Supported hash algorithms."""

    BLAKE2B = "blake2b"  # Recommended: fast, secure, customizable
    BLAKE3 = "blake3"  # Alternative: faster, but requires external library


# ============================================================================
# Configuration Models
# ============================================================================


class HashConfig(BaseModel):
    """Configuration for hash generation."""

    algorithm: HashAlgorithm = Field(
        default=HashAlgorithm.BLAKE3,
        description="Hash algorithm to use for entity ID generation",
    )
    file_hash_length: int = Field(
        default=24,
        ge=8,
        le=32,
        description="Hash length for FILE entity IDs (hex characters)",
    )
    entity_hash_length: int = Field(
        default=16,
        ge=8,
        le=32,
        description="Hash length for ENTITY entity IDs (hex characters)",
    )
    relationship_hash_length: int = Field(
        default=16,
        ge=8,
        le=32,
        description="Hash length for RELATIONSHIP entity IDs (hex characters)",
    )

    @field_validator(
        "file_hash_length", "entity_hash_length", "relationship_hash_length"
    )
    @classmethod
    def validate_hash_length_even(cls, v: int) -> int:
        """Ensure hash length is even (BLAKE2b digest_size must be bytes)."""
        if v % 2 != 0:
            raise ValueError(f"Hash length must be even, got {v}")
        return v


# ============================================================================
# Hash Resolver Service
# ============================================================================


class HashResolver:
    """
    Centralized service for hash-based entity ID generation.

    Provides deterministic, collision-resistant entity IDs using BLAKE2b algorithm.
    All entity IDs follow the format: {type_prefix}_{hash}

    Examples:
        - FILE: "file_a1b2c3d4e5f6"
        - ENTITY: "entity-91f521860bc3a4d5"
        - RELATIONSHIP: "rel-7f3e4d5a6b8c9d0e"

    Attributes:
        config: Hash generation configuration
    """

    # Entity ID format patterns (regex)
    FILE_PATTERN = re.compile(r"^file_[a-f0-9]{24}$")
    ENTITY_PATTERN = re.compile(r"^entity-[a-f0-9]{16}$")
    RELATIONSHIP_PATTERN = re.compile(r"^rel-[a-f0-9]{16}$")
    DIRECTORY_PATTERN = re.compile(r"^dir_[a-f0-9]{12}$")

    # Deprecated patterns (for migration detection)
    DEPRECATED_PATH_BASED_PATTERN = re.compile(r"^file:[^:]+:.+$")
    DEPRECATED_MD5_PATTERN = re.compile(r"^entity_[a-f0-9]{8}_[a-f0-9]{8}$")

    def __init__(self, config: Optional[HashConfig] = None) -> None:
        """
        Initialize hash resolver with optional configuration.

        Args:
            config: Hash generation configuration. Uses defaults if not provided.
        """
        self.config = config or HashConfig()

    def _compute_blake3_hash(self, input_string: str, digest_size: int) -> str:
        """
        Compute BLAKE3 hash for input string.

        Args:
            input_string: String to hash
            digest_size: Number of bytes for digest (will be converted to hex chars)

        Returns:
            Hexadecimal hash string (digest_size * 2 characters)
        """
        try:
            import blake3

            hasher = blake3.blake3(input_string.encode("utf-8"))
            hash_bytes = hasher.digest()
            # Convert to hex and take first digest_size*2 characters
            return hash_bytes.hex()[: digest_size * 2]
        except ImportError:
            # Fallback to BLAKE2B if blake3 not available
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                "blake3 library not installed. Install with: pip install blake3. "
                "Falling back to BLAKE2B."
            )
            return self._compute_blake2b_hash(input_string, digest_size)

    def _compute_blake2b_hash(self, input_string: str, digest_size: int) -> str:
        """
        Compute BLAKE2b hash for input string.

        Args:
            input_string: String to hash
            digest_size: Digest size in bytes (hash_length // 2)

        Returns:
            Hexadecimal hash string

        Raises:
            ValueError: If digest_size is invalid
        """
        if digest_size <= 0 or digest_size > 64:
            raise ValueError(
                f"digest_size must be between 1 and 64 bytes, got {digest_size}"
            )

        hash_obj = hashlib.blake2b(
            input_string.encode("utf-8"), digest_size=digest_size
        )
        return hash_obj.hexdigest()

    def generate_file_entity_id(self, file_path: str, project_name: str) -> str:
        """
        Generate hash-based entity_id for a FILE node.

        Uses BLAKE3 algorithm with 24-character hex output for unique identification.
        Entity ID is deterministic: same file_path + project_name always produces
        same entity_id.

        Format: file_{blake3_hash[:24]}

        Args:
            file_path: Absolute or relative file path
            project_name: Project name for namespace isolation

        Returns:
            FILE entity_id (e.g., "file_a1b2c3d4e5f6")

        Raises:
            ValueError: If file_path or project_name is empty

        Examples:
            >>> resolver = HashResolver()
            >>> resolver.generate_file_entity_id(
            ...     "/services/intelligence/main.py",
            ...     "archon"
            ... )
            'file_8e3b9a1c7f2d5a4e6b9c1d3f'
        """
        if not file_path:
            raise ValueError("file_path cannot be empty")
        if not project_name:
            raise ValueError("project_name cannot be empty")

        # Combine file_path and project_name for hash input
        # Format: {project_name}:{file_path}
        hash_input = f"{project_name}:{file_path}"

        # Compute hash (digest_size in bytes = hash_length // 2)
        digest_size = self.config.file_hash_length // 2
        if self.config.algorithm == HashAlgorithm.BLAKE3:
            hash_hex = self._compute_blake3_hash(hash_input, digest_size)
        else:
            hash_hex = self._compute_blake2b_hash(hash_input, digest_size)

        return f"file_{hash_hex}"

    def generate_entity_id(
        self, entity_name: str, source_path: Optional[str] = None
    ) -> str:
        """
        Generate hash-based entity_id for an ENTITY node (class, function, etc.).

        Uses BLAKE2b algorithm with 16-character hex output. If source_path is
        provided, it's included in the hash to distinguish entities with same name
        across different files.

        Format: entity-{blake2b_hash[:16]}

        Args:
            entity_name: Name of the entity (e.g., class name, function name)
            source_path: Optional source file path for disambiguation

        Returns:
            ENTITY entity_id (e.g., "entity-91f521860bc3a4d5")

        Raises:
            ValueError: If entity_name is empty

        Examples:
            >>> resolver = HashResolver()
            >>> resolver.generate_entity_id("MyClass")
            'entity-91f521860bc3a4d5'
            >>> resolver.generate_entity_id("MyClass", "/app/models.py")
            'entity-7f3e4d5a6b8c9d0e'
        """
        if not entity_name:
            raise ValueError("entity_name cannot be empty")

        # Hash input: include source_path if provided for disambiguation
        hash_input = f"{entity_name}:{source_path}" if source_path else entity_name

        # Compute hash
        digest_size = self.config.entity_hash_length // 2
        if self.config.algorithm == HashAlgorithm.BLAKE3:
            hash_hex = self._compute_blake3_hash(hash_input, digest_size)
        else:
            hash_hex = self._compute_blake2b_hash(hash_input, digest_size)

        return f"entity-{hash_hex}"

    def generate_relationship_id(
        self, source_entity_id: str, target_entity_id: str
    ) -> str:
        """
        Generate hash-based relationship_id for a RELATIONSHIP edge.

        Uses BLAKE2b algorithm with 16-character hex output. Relationship ID is
        based on source and target entity IDs to ensure uniqueness.

        Format: rel-{blake2b_hash[:16]}

        Args:
            source_entity_id: Source entity's entity_id
            target_entity_id: Target entity's entity_id

        Returns:
            RELATIONSHIP relationship_id (e.g., "rel-7f3e4d5a6b8c9d0e")

        Raises:
            ValueError: If source_entity_id or target_entity_id is empty

        Examples:
            >>> resolver = HashResolver()
            >>> resolver.generate_relationship_id(
            ...     "file_a1b2c3d4e5f6",
            ...     "entity-91f521860bc3a4d5"
            ... )
            'rel-7f3e4d5a6b8c9d0e'
        """
        if not source_entity_id:
            raise ValueError("source_entity_id cannot be empty")
        if not target_entity_id:
            raise ValueError("target_entity_id cannot be empty")

        # Hash input: {source_id}_{target_id}
        hash_input = f"{source_entity_id}_{target_entity_id}"

        # Compute hash
        digest_size = self.config.relationship_hash_length // 2
        if self.config.algorithm == HashAlgorithm.BLAKE3:
            hash_hex = self._compute_blake3_hash(hash_input, digest_size)
        else:
            hash_hex = self._compute_blake2b_hash(hash_input, digest_size)

        return f"rel-{hash_hex}"

    def resolve_path_to_entity_id(self, file_path: str, project_name: str) -> str:
        """
        Resolve file path to its canonical hash-based entity_id.

        This is equivalent to generate_file_entity_id, but with a more explicit
        name for resolution use cases.

        Args:
            file_path: File path to resolve
            project_name: Project name

        Returns:
            FILE entity_id

        Examples:
            >>> resolver = HashResolver()
            >>> resolver.resolve_path_to_entity_id(
            ...     "/services/intelligence/main.py",
            ...     "archon"
            ... )
            'file_8e3b9a1c7f2d'
        """
        return self.generate_file_entity_id(file_path, project_name)

    def validate_entity_id_format(
        self, entity_id: str, entity_type: EntityType
    ) -> bool:
        """
        Validate entity_id matches expected format for given entity type.

        Checks format compliance with regex patterns. Does NOT verify existence
        in database.

        Args:
            entity_id: Entity ID to validate
            entity_type: Expected entity type

        Returns:
            True if entity_id format is valid, False otherwise

        Examples:
            >>> resolver = HashResolver()
            >>> resolver.validate_entity_id_format(
            ...     "file_a1b2c3d4e5f6",
            ...     EntityType.FILE
            ... )
            True
            >>> resolver.validate_entity_id_format(
            ...     "file:archon:/main.py",
            ...     EntityType.FILE
            ... )
            False  # Deprecated path-based format
        """
        if entity_type == EntityType.FILE:
            return bool(self.FILE_PATTERN.match(entity_id))
        elif entity_type == EntityType.ENTITY:
            return bool(self.ENTITY_PATTERN.match(entity_id))
        elif entity_type == EntityType.RELATIONSHIP:
            return bool(self.RELATIONSHIP_PATTERN.match(entity_id))
        elif entity_type == EntityType.DIRECTORY:
            return bool(self.DIRECTORY_PATTERN.match(entity_id))

        return False

    def detect_deprecated_format(self, entity_id: str) -> Tuple[bool, str]:
        """
        Detect if entity_id uses deprecated format.

        Helps identify entities that need migration to hash-based format.

        Args:
            entity_id: Entity ID to check

        Returns:
            Tuple of (is_deprecated, format_description)

        Examples:
            >>> resolver = HashResolver()
            >>> resolver.detect_deprecated_format("file:archon:/main.py")
            (True, "path-based format (deprecated)")
            >>> resolver.detect_deprecated_format("file_a1b2c3d4e5f6")
            (False, "current hash-based format")
        """
        if self.DEPRECATED_PATH_BASED_PATTERN.match(entity_id):
            return True, "path-based format (deprecated)"
        elif self.DEPRECATED_MD5_PATTERN.match(entity_id):
            return True, "MD5-based format (deprecated, use BLAKE2b)"
        elif (
            self.FILE_PATTERN.match(entity_id)
            or self.ENTITY_PATTERN.match(entity_id)
            or self.RELATIONSHIP_PATTERN.match(entity_id)
        ):
            return False, "current hash-based format"

        return False, "unknown format"

    def enforce_format(self, entity_id: str, entity_type: EntityType) -> None:
        """
        Enforce entity_id format compliance, raising exception if invalid.

        Use this for strict validation where format violations should prevent
        operation completion.

        Args:
            entity_id: Entity ID to validate
            entity_type: Expected entity type

        Raises:
            ValueError: If entity_id format is invalid

        Examples:
            >>> resolver = HashResolver()
            >>> resolver.enforce_format("file_a1b2c3d4e5f6", EntityType.FILE)
            # No exception - valid format
            >>> resolver.enforce_format("file:archon:/main.py", EntityType.FILE)
            ValueError: Invalid FILE entity_id format: 'file:archon:/main.py'...
        """
        if not self.validate_entity_id_format(entity_id, entity_type):
            # Check if deprecated format
            is_deprecated, format_desc = self.detect_deprecated_format(entity_id)

            if is_deprecated:
                raise ValueError(
                    f"Invalid {entity_type.value} entity_id format: '{entity_id}' "
                    f"uses {format_desc}. Please migrate to hash-based format."
                )
            else:
                raise ValueError(
                    f"Invalid {entity_type.value} entity_id format: '{entity_id}' "
                    f"does not match expected pattern. "
                    f"Expected format for {entity_type.value}: "
                    f"{self._get_expected_format(entity_type)}"
                )

    def _get_expected_format(self, entity_type: EntityType) -> str:
        """Get expected format description for entity type."""
        if entity_type == EntityType.FILE:
            return "file_{24_hex_chars}"
        elif entity_type == EntityType.ENTITY:
            return "entity-{16_hex_chars}"
        elif entity_type == EntityType.RELATIONSHIP:
            return "rel-{16_hex_chars}"
        elif entity_type == EntityType.DIRECTORY:
            return "dir_{12_hex_chars}"
        return "unknown"


# ============================================================================
# Convenience Functions
# ============================================================================


def generate_file_entity_id(file_path: str, project_name: str) -> str:
    """
    Convenience function for generating FILE entity IDs.

    Args:
        file_path: File path
        project_name: Project name

    Returns:
        FILE entity_id
    """
    resolver = HashResolver()
    return resolver.generate_file_entity_id(file_path, project_name)


def validate_entity_id_format(entity_id: str, entity_type: EntityType) -> bool:
    """
    Convenience function for validating entity_id format.

    Args:
        entity_id: Entity ID to validate
        entity_type: Expected entity type

    Returns:
        True if valid, False otherwise
    """
    resolver = HashResolver()
    return resolver.validate_entity_id_format(entity_id, entity_type)
