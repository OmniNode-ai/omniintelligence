# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Entity type enum for knowledge graph operations."""

from enum import Enum


class EnumEntityType(str, Enum):
    """Entity types for knowledge graph.

    These types categorize code and document entities for analysis,
    storage in vector databases, and graph relationships.
    """

    DOCUMENT = "DOCUMENT"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    MODULE = "MODULE"
    PACKAGE = "PACKAGE"
    VARIABLE = "VARIABLE"
    CONSTANT = "CONSTANT"
    INTERFACE = "INTERFACE"
    TYPE = "TYPE"
    PATTERN = "PATTERN"
    PROJECT = "PROJECT"
    FILE = "FILE"
    DEPENDENCY = "DEPENDENCY"
    TEST = "TEST"
    CONFIGURATION = "CONFIGURATION"


__all__ = ["EnumEntityType"]
