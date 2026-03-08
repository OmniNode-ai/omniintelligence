# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Hard validators for ONEX contract evaluation.

Three pure functions (no I/O, no LLM calls, no logging, no side effects).
All functions are synchronous and operate entirely on the provided arguments.
"""

from __future__ import annotations

from typing import Any

_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "node_type",
        "contract_id",
        "title",
        "description",
        "io",
        "environment_variables",
    }
)

_REQUIRED_TYPES: dict[str, type] = {
    "node_type": str,
    "contract_id": str,
    "title": str,
    "description": str,
    "io": dict,
    "environment_variables": (dict, list),  # type: ignore[dict-item]
}


def validate_schema(contract_dict: dict[str, Any]) -> bool:
    """Check that required keys are present and all values are correct types.

    Args:
        contract_dict: Raw contract dictionary to validate.

    Returns:
        True if all required keys are present with correct types, False otherwise.
    """
    if not isinstance(contract_dict, dict):
        return False

    for key in _REQUIRED_KEYS:
        if key not in contract_dict:
            return False
        expected = _REQUIRED_TYPES.get(key)
        if expected is not None and not isinstance(contract_dict[key], expected):
            return False

    return True


def validate_trace_coverage(
    contract_dict: dict[str, Any],
    ticket_requirements: list[str],
) -> float:
    """Compute ratio of ticket requirements matched in contract description/acceptance_criteria.

    Vacuously complete (1.0) when ticket_requirements is empty.

    Args:
        contract_dict: Raw contract dictionary to inspect.
        ticket_requirements: List of requirement strings to look for.

    Returns:
        Float in [0.0, 1.0] — ratio of requirements found in contract text.
    """
    if not ticket_requirements:
        return 1.0

    description: str = str(contract_dict.get("description", ""))
    acceptance_criteria: str = str(contract_dict.get("acceptance_criteria", ""))
    corpus = (description + " " + acceptance_criteria).lower()

    matched = sum(1 for req in ticket_requirements if req.lower() in corpus)
    return matched / len(ticket_requirements)


def validate_reference_integrity(contract_dict: dict[str, Any]) -> bool:
    """Check that all referenced paths/modules exist in contract_dict["io"].

    A reference is considered dangling when a key listed in
    ``contract_dict.get("references", [])`` is absent from the ``io`` mapping.
    Returns False when any referenced field is missing from ``io``.

    Args:
        contract_dict: Raw contract dictionary to validate.

    Returns:
        True when all references resolve within the io section, False otherwise.
    """
    if not isinstance(contract_dict, dict):
        return False

    io_section = contract_dict.get("io")
    if not isinstance(io_section, dict):
        # If there is no io section but also no references, we're trivially clean.
        references = contract_dict.get("references")
        if not references:
            return True
        return False

    references = contract_dict.get("references")
    if not references:
        return True

    if not isinstance(references, (list, tuple)):
        return False

    return all(ref in io_section for ref in references)
