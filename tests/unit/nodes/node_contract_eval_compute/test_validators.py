# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for contract hard validators.

At least 2 test cases per validator (6 minimum total).
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_contract_eval_compute.handlers.validators import (
    validate_reference_integrity,
    validate_schema,
    validate_trace_coverage,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_CONTRACT: dict = {
    "node_type": "compute",
    "contract_id": "test-contract-001",
    "title": "Test Contract",
    "description": "A valid test contract for unit testing.",
    "io": {
        "input": "ModelFoo",
        "output": "ModelBar",
    },
    "environment_variables": {},
}


# ---------------------------------------------------------------------------
# validate_schema
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_validate_schema_empty_dict_returns_false() -> None:
    """validate_schema({}) must return False."""
    assert validate_schema({}) is False


@pytest.mark.unit
def test_validate_schema_valid_contract_returns_true() -> None:
    """A fully specified contract passes schema validation."""
    assert validate_schema(VALID_CONTRACT) is True


@pytest.mark.unit
def test_validate_schema_missing_required_key_returns_false() -> None:
    """Missing a required key causes validation to fail."""
    partial = {k: v for k, v in VALID_CONTRACT.items() if k != "io"}
    assert validate_schema(partial) is False


@pytest.mark.unit
def test_validate_schema_wrong_type_for_io_returns_false() -> None:
    """io must be a dict; a string value causes failure."""
    bad = {**VALID_CONTRACT, "io": "not-a-dict"}
    assert validate_schema(bad) is False


# ---------------------------------------------------------------------------
# validate_trace_coverage
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_validate_trace_coverage_empty_requirements_returns_one() -> None:
    """Vacuously complete: empty requirement list returns 1.0."""
    result = validate_trace_coverage(VALID_CONTRACT, [])
    assert result == 1.0


@pytest.mark.unit
def test_validate_trace_coverage_all_requirements_matched() -> None:
    """All requirements present in description returns 1.0."""
    contract = {**VALID_CONTRACT, "description": "alpha beta gamma"}
    result = validate_trace_coverage(contract, ["alpha", "beta", "gamma"])
    assert result == 1.0


@pytest.mark.unit
def test_validate_trace_coverage_partial_match_returns_fraction() -> None:
    """One of two requirements matched returns 0.5."""
    contract = {**VALID_CONTRACT, "description": "alpha"}
    result = validate_trace_coverage(contract, ["alpha", "delta"])
    assert result == pytest.approx(0.5)


@pytest.mark.unit
def test_validate_trace_coverage_no_match_returns_zero() -> None:
    """No requirements matched returns 0.0."""
    contract = {**VALID_CONTRACT, "description": "unrelated content"}
    result = validate_trace_coverage(contract, ["alpha", "beta"])
    assert result == 0.0


# ---------------------------------------------------------------------------
# validate_reference_integrity
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_validate_reference_integrity_no_references_returns_true() -> None:
    """Contract without a references key is trivially clean."""
    assert validate_reference_integrity(VALID_CONTRACT) is True


@pytest.mark.unit
def test_validate_reference_integrity_missing_referenced_field_returns_false() -> None:
    """A reference that is absent from io causes failure."""
    contract = {
        **VALID_CONTRACT,
        "io": {"input": "ModelFoo"},
        "references": ["output"],  # 'output' is not in io
    }
    assert validate_reference_integrity(contract) is False


@pytest.mark.unit
def test_validate_reference_integrity_all_references_present_returns_true() -> None:
    """All referenced fields exist in io."""
    contract = {
        **VALID_CONTRACT,
        "io": {"input": "ModelFoo", "output": "ModelBar"},
        "references": ["input", "output"],
    }
    assert validate_reference_integrity(contract) is True


@pytest.mark.unit
def test_validate_reference_integrity_no_io_section_with_references_returns_false() -> (
    None
):
    """Missing io section with non-empty references returns False."""
    contract = {
        "node_type": "compute",
        "contract_id": "x",
        "title": "x",
        "description": "x",
        "environment_variables": {},
        "references": ["some_field"],
    }
    assert validate_reference_integrity(contract) is False
