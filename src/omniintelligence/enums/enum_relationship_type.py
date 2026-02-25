# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Relationship type enum for knowledge graph operations."""

from enum import Enum


class EnumRelationshipType(str, Enum):
    """Relationship types for knowledge graph.

    These types define the edges between entities in the knowledge graph,
    enabling traversal and relationship-based queries.
    """

    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    DEPENDS_ON = "DEPENDS_ON"
    IMPLEMENTS = "IMPLEMENTS"
    EXTENDS = "EXTENDS"
    CALLS = "CALLS"
    REFERENCES = "REFERENCES"
    DEFINES = "DEFINES"
    USES = "USES"
    MATCHES_PATTERN = "MATCHES_PATTERN"
    SIMILAR_TO = "SIMILAR_TO"


__all__ = ["EnumRelationshipType"]
