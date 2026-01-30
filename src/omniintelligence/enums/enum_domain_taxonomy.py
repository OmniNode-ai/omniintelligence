"""Domain taxonomy enum for OmniIntelligence.

This module contains the canonical domain taxonomy enumeration for pattern classification.
Domains must come from this versioned enum, not derived dynamically, to ensure
domain coherence as a quality gate for pattern promotion.

ONEX Compliance:
    - Enum-based naming: Enum{Category}
    - String-based enum for JSON serialization
    - Integration with Pydantic models

Ticket: OMN-1666
"""

from enum import Enum


class EnumDomainTaxonomy(str, Enum):
    """v1.0 - Domain taxonomy for pattern classification.

    This enum defines the canonical domains for classifying patterns.
    Domains provide a stable, versioned classification that prevents
    "wobble" from dynamically-derived classifications.

    Used as a quality gate for pattern promotion - patterns must have
    coherent domain classification before being promoted.

    Attributes:
        CODE_GENERATION: Creating new code
        CODE_REVIEW: Reviewing existing code
        DEBUGGING: Finding and fixing bugs
        TESTING: Writing or running tests
        DOCUMENTATION: Writing docs or comments
        REFACTORING: Restructuring existing code
        ARCHITECTURE: System design decisions
        DEVOPS: CI/CD, deployment, infra
        DATA_ANALYSIS: Data processing and analysis
        GENERAL: General purpose tasks

    Example:
        >>> from omniintelligence.enums import EnumDomainTaxonomy
        >>> domain = EnumDomainTaxonomy.CODE_GENERATION
        >>> assert domain.value == "code_generation"

    See Also:
        - deployment/database/migrations/004_create_domain_taxonomy.sql
        - Manifest Injection Enhancement Plan for domain coherence requirements
    """

    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    DEBUGGING = "debugging"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    REFACTORING = "refactoring"
    ARCHITECTURE = "architecture"
    DEVOPS = "devops"
    DATA_ANALYSIS = "data_analysis"
    GENERAL = "general"


# Taxonomy version for validation
DOMAIN_TAXONOMY_VERSION = "1.0"


__all__ = ["DOMAIN_TAXONOMY_VERSION", "EnumDomainTaxonomy"]
