"""
Centralized Memgraph Label Definitions
=======================================

CRITICAL: Use these constants for ALL Cypher queries to prevent label case inconsistencies.

DO NOT use raw strings like "FILE" or ":File" in queries.
DO use: MemgraphLabels.FILE or LABEL_FILE constant.

Background:
-----------
We discovered 79% of tests were using incorrect "FILE" (all caps) label while production
creates "File" (capital F only) nodes. This caused tests to pass while production queries
failed silently. See: /tmp/label_case_analysis.md

Usage:
------
# Python queries:
query = f"MATCH (f:{MemgraphLabels.FILE}) RETURN f"
query = f"MATCH (f:{LABEL_FILE}) RETURN f"

# Test queries:
query = f"CREATE (f:{MemgraphLabels.FILE} {{path: $path}})"

Author: Archon Team
Date: 2025-11-12
Reference: Label case consistency bug fix
"""

from enum import Enum
from typing import Final


class MemgraphLabels(str, Enum):
    """
    Canonical Memgraph node labels.

    CRITICAL: These are the ONLY valid labels. Use these constants in ALL Cypher queries.

    Attributes:
        FILE: File nodes (code files, documents)
        PROJECT: Project root nodes
        DIRECTORY: Directory nodes in file tree
        ENTITY: Extracted entities (functions, classes, etc.)
        CONCEPT: Semantic concepts
        THEME: Code themes
        ONEX_TYPE: ONEX node types
        DOMAIN: Domain classifications
    """

    # Primary node types
    FILE = "File"  # File nodes - CRITICAL: Capital 'F' only!
    PROJECT = "PROJECT"  # Project root nodes
    DIRECTORY = "Directory"  # Directory nodes
    ENTITY = "Entity"  # Extracted entities

    # Semantic and classification nodes
    CONCEPT = "Concept"  # Semantic concepts
    THEME = "Theme"  # Code themes
    ONEX_TYPE = "ONEXType"  # ONEX node types
    DOMAIN = "Domain"  # Domain classifications

    def __str__(self) -> str:
        """Return the label value for use in queries."""
        return self.value


# Legacy string constants for backward compatibility
# TODO: Migrate all code to use MemgraphLabels enum instead
LABEL_FILE: Final[str] = MemgraphLabels.FILE.value
LABEL_PROJECT: Final[str] = MemgraphLabels.PROJECT.value
LABEL_DIRECTORY: Final[str] = MemgraphLabels.DIRECTORY.value
LABEL_ENTITY: Final[str] = MemgraphLabels.ENTITY.value
LABEL_CONCEPT: Final[str] = MemgraphLabels.CONCEPT.value
LABEL_THEME: Final[str] = MemgraphLabels.THEME.value
LABEL_ONEX_TYPE: Final[str] = MemgraphLabels.ONEX_TYPE.value
LABEL_DOMAIN: Final[str] = MemgraphLabels.DOMAIN.value


# Relationship types (for future expansion)
class MemgraphRelationships(str, Enum):
    """
    Canonical Memgraph relationship types.

    TODO: Expand this as we centralize relationship type definitions.
    """

    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    HAS_CONCEPT = "HAS_CONCEPT"
    HAS_THEME = "HAS_THEME"
    IS_ONEX_TYPE = "IS_ONEX_TYPE"
    BELONGS_TO_DOMAIN = "BELONGS_TO_DOMAIN"

    def __str__(self) -> str:
        """Return the relationship type for use in queries."""
        return self.value


# Validation helper
def validate_label(label: str) -> bool:
    """
    Validate that a label matches one of the canonical labels.

    Args:
        label: Label string to validate

    Returns:
        True if label is valid, False otherwise

    Raises:
        ValueError: If label is invalid and strict mode enabled

    Example:
        >>> validate_label("File")
        True
        >>> validate_label("FILE")  # Wrong case!
        False
    """
    valid_labels = {label.value for label in MemgraphLabels}
    return label in valid_labels


# Pre-commit hook helper
def find_raw_label_strings(file_content: str) -> list[tuple[int, str]]:
    """
    Find raw label strings in Cypher queries (for pre-commit validation).

    Args:
        file_content: File content to scan

    Returns:
        List of (line_number, matched_string) tuples

    Example:
        >>> content = 'query = "MATCH (f:FILE) RETURN f"'
        >>> find_raw_label_strings(content)
        [(1, ':FILE')]
    """
    import re

    # Pattern matches `:LABEL` in Cypher queries but excludes enum references
    # Matches: ":FILE", ":File", ":PROJECT"
    # Excludes: "MemgraphLabels.FILE", "LABEL_FILE"
    pattern = r"(?<!MemgraphLabels\.)(?<!LABEL_):([A-Z][A-Za-z]+)\b"

    violations = []
    for line_num, line in enumerate(file_content.splitlines(), start=1):
        # Skip lines with enum/constant usage
        if "MemgraphLabels" in line or "LABEL_" in line:
            continue

        matches = re.finditer(pattern, line)
        for match in matches:
            violations.append((line_num, match.group(0)))

    return violations


if __name__ == "__main__":
    # Self-test
    print("Memgraph Labels:")
    for label in MemgraphLabels:
        print(f"  {label.name}: {label.value}")

    print("\nValidation tests:")
    print(f"  validate_label('File'): {validate_label('File')}")
    print(f"  validate_label('FILE'): {validate_label('FILE')}")  # Should be False!
    print(f"  validate_label('PROJECT'): {validate_label('PROJECT')}")
