# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pattern role matching against AST-extracted entities.

Given a pattern role definition (base_class signature) and a list of
extracted code entities, find entities whose bases match the role.
"""

from __future__ import annotations

from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entity import (
    ModelCodeEntity,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_pattern_definition import (
    ModelPatternRole,
)


def match_pattern_role(
    role: ModelPatternRole,
    entities: list[ModelCodeEntity],
) -> list[ModelCodeEntity]:
    """Find entities matching a pattern role by base class inheritance.

    Matches entities where any base class name (stripped of generic params)
    equals the role's base_class.

    Args:
        role: Pattern role to match against.
        entities: Extracted code entities to search.

    Returns:
        List of entities matching the role (may be empty).
    """
    matches: list[ModelCodeEntity] = []
    for entity in entities:
        if entity.entity_type != "class":
            continue
        for base in entity.bases:
            base_name = base.split("[")[0]
            if base_name == role.base_class:
                matches.append(entity)
                break
    return matches
