# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for Contract Linter helper functions and utilities.

Tests for structured error output, linter configuration, and field identifier
pattern validation.
"""

import json
from pathlib import Path

import pytest

from omniintelligence.tools.contract_linter import (
    FIELD_IDENTIFIER_PATTERN,
    ContractLinter,
    ModelContractValidationResult,
)

# =============================================================================
# Test Class: Structured Error Output
# =============================================================================


@pytest.mark.unit
class TestStructuredErrorOutput:
    """Tests for structured error output with field paths."""

    def test_structured_error_output_with_field_paths(
        self, tmp_path: Path, invalid_missing_name_yaml: str
    ):
        """Test that errors include proper field paths."""
        contract_path = tmp_path / "invalid.yaml"
        contract_path.write_text(invalid_missing_name_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.is_valid is False
        assert len(result.validation_errors) >= 1

        # Each error should have field_path, error_message, and validation_error_type
        for error in result.validation_errors:
            assert hasattr(error, "field_path")
            assert hasattr(error, "error_message")
            assert hasattr(error, "validation_error_type")
            assert error.field_path is not None
            assert error.error_message is not None

    def test_nested_field_path_in_errors(self, tmp_path: Path):
        """Test that nested field paths are properly formatted.

        Uses FSM subcontract which validates via Pydantic and preserves nested paths.
        Node contracts use ProtocolContractValidator which doesn't preserve nested paths.

        NOTE: This test uses inline YAML instead of conftest fixtures because it requires
        a specific invalid nested field value (timeout_ms: not_a_number) to trigger
        nested field path error reporting. This scenario is unique to testing error
        path formatting and cannot be reused from standard valid/invalid fixtures.
        """
        # FSM subcontract with invalid nested field - timeout_ms must be int >= 1
        # but we provide a string that cannot be coerced to int
        yaml_content = """
state_machine_name: test_fsm
state_machine_version: "1.0.0"
description: Test FSM
initial_state: idle
states:
  - state_name: idle
    state_type: operational
    description: Idle state
    timeout_ms: not_a_number
transitions:
  - transition_name: start
    from_state: idle
    to_state: idle
    trigger: test
"""
        contract_path = tmp_path / "nested_error.yaml"
        contract_path.write_text(yaml_content)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.is_valid is False
        # Should have an error with nested path (e.g., "states.0.timeout_ms")
        assert any("states" in e.field_path for e in result.validation_errors)

    def test_multiple_errors_captured(self, tmp_path: Path):
        """Test that multiple validation errors are captured.

        NOTE: This test uses inline YAML instead of conftest fixtures because it requires
        a minimal contract with only version and node_type fields to trigger MULTIPLE
        validation errors simultaneously (missing: name, description, input_model,
        output_model, algorithm). The conftest invalid fixtures each test only a single
        missing field at a time, which doesn't cover this multiple-error scenario.
        """
        # Use a valid node_type but missing multiple required fields
        yaml_content = """
version:
  major: 1
  minor: 0
  patch: 0
node_type: compute
"""
        contract_path = tmp_path / "multiple_errors.yaml"
        contract_path.write_text(yaml_content)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        assert result.is_valid is False
        # Should have multiple errors for missing fields:
        # name, description, input_model, output_model, algorithm
        assert len(result.validation_errors) >= 2

    def test_error_output_as_json(self, tmp_path: Path, invalid_missing_name_yaml: str):
        """Test that errors can be serialized to JSON."""
        contract_path = tmp_path / "invalid.yaml"
        contract_path.write_text(invalid_missing_name_yaml)

        linter = ContractLinter()
        result = linter.validate(contract_path)

        result_dict = result.to_dict()
        json_output = json.dumps(result_dict)

        assert isinstance(json_output, str)
        parsed = json.loads(json_output)
        assert "is_valid" in parsed
        assert "validation_errors" in parsed
        assert isinstance(parsed["validation_errors"], list)


# =============================================================================
# Test Class: Linter Configuration
# =============================================================================


@pytest.mark.unit
class TestLinterConfiguration:
    """Tests for linter configuration options."""

    def test_linter_strict_mode(self, tmp_path: Path, valid_base_contract_yaml: str):
        """Test that strict mode raises NotImplementedError (not yet implemented)."""
        # Strict mode is reserved for future implementation
        with pytest.raises(NotImplementedError) as exc_info:
            ContractLinter(strict=True)

        assert "Strict mode is reserved for future implementation" in str(
            exc_info.value
        )

    def test_linter_lenient_mode(self, tmp_path: Path, valid_base_contract_yaml: str):
        """Test linter in lenient mode validates contracts successfully.

        Lenient mode (strict=False, the default) should pass for valid base contracts.
        This test verifies both that a result is returned AND that the contract is valid.
        """
        contract_path = tmp_path / "base.yaml"
        contract_path.write_text(valid_base_contract_yaml)

        linter = ContractLinter(strict=False)
        result = linter.validate(contract_path)

        # Lenient mode should pass for base contracts
        assert isinstance(result, ModelContractValidationResult)
        assert result.is_valid is True

    def test_linter_custom_schema_version(
        self, tmp_path: Path, valid_compute_contract_yaml: str
    ):
        """Test linter with specific schema version.

        Currently only schema_version="1.0.0" is supported. This test verifies:
        1. The linter accepts schema_version="1.0.0" without raising NotImplementedError
        2. A valid compute contract passes validation with the specified schema version

        When schema versioning is fully implemented, this test should be expanded
        to verify version-specific validation behavior.

        Uses valid_compute_contract_yaml fixture from conftest.py to avoid duplication.
        """
        contract_path = tmp_path / "contract.yaml"
        contract_path.write_text(valid_compute_contract_yaml)

        # schema_version="1.0.0" is the only currently supported version
        linter = ContractLinter(schema_version="1.0.0")
        result = linter.validate(contract_path)

        # Verify we get a proper result and the contract is valid
        assert isinstance(result, ModelContractValidationResult)
        assert result.is_valid is True


# =============================================================================
# Test Class: Field Identifier Pattern
# =============================================================================


@pytest.mark.unit
class TestFieldIdentifierPattern:
    """Tests for FIELD_IDENTIFIER_PATTERN regex.

    The FIELD_IDENTIFIER_PATTERN validates field names extracted from violation
    messages. It matches lowercase snake_case Python identifiers used in ONEX
    contracts (e.g., 'name', 'version', 'node_type', '_private', 'field123').
    """

    def test_valid_simple_field_names(self):
        """Test that simple lowercase field names match."""
        assert FIELD_IDENTIFIER_PATTERN.match("name") is not None
        assert FIELD_IDENTIFIER_PATTERN.match("version") is not None
        assert FIELD_IDENTIFIER_PATTERN.match("description") is not None
        assert FIELD_IDENTIFIER_PATTERN.match("contract") is not None

    def test_valid_snake_case_field_names(self):
        """Test that snake_case field names match."""
        assert FIELD_IDENTIFIER_PATTERN.match("node_type") is not None
        assert FIELD_IDENTIFIER_PATTERN.match("input_model") is not None
        assert FIELD_IDENTIFIER_PATTERN.match("output_model") is not None
        assert FIELD_IDENTIFIER_PATTERN.match("io_operations") is not None
        assert FIELD_IDENTIFIER_PATTERN.match("state_machine_name") is not None

    def test_valid_underscore_prefix(self):
        """Test that underscore-prefixed field names match."""
        assert FIELD_IDENTIFIER_PATTERN.match("_private") is not None
        assert FIELD_IDENTIFIER_PATTERN.match("_internal_field") is not None
        assert FIELD_IDENTIFIER_PATTERN.match("__dunder") is not None

    def test_valid_with_numbers(self):
        """Test that field names with numbers match."""
        assert FIELD_IDENTIFIER_PATTERN.match("field123") is not None
        assert FIELD_IDENTIFIER_PATTERN.match("v1_0_0") is not None
        assert FIELD_IDENTIFIER_PATTERN.match("step_1") is not None

    def test_invalid_uppercase_start(self):
        """Test that uppercase-starting names don't match (likely error messages)."""
        assert FIELD_IDENTIFIER_PATTERN.match("Name") is None
        assert FIELD_IDENTIFIER_PATTERN.match("Invalid") is None
        assert FIELD_IDENTIFIER_PATTERN.match("ValidationError") is None
        assert FIELD_IDENTIFIER_PATTERN.match("Missing required field") is None

    def test_invalid_with_spaces(self):
        """Test that names with spaces don't match."""
        assert FIELD_IDENTIFIER_PATTERN.match("field name") is None
        assert FIELD_IDENTIFIER_PATTERN.match("two words") is None
        assert FIELD_IDENTIFIER_PATTERN.match(" leading_space") is None

    def test_invalid_starts_with_number(self):
        """Test that names starting with numbers don't match."""
        assert FIELD_IDENTIFIER_PATTERN.match("123field") is None
        assert FIELD_IDENTIFIER_PATTERN.match("1_version") is None
        assert FIELD_IDENTIFIER_PATTERN.match("0name") is None

    def test_invalid_special_characters(self):
        """Test that names with special characters don't match."""
        assert FIELD_IDENTIFIER_PATTERN.match("field-name") is None
        assert FIELD_IDENTIFIER_PATTERN.match("field.name") is None
        assert FIELD_IDENTIFIER_PATTERN.match("field:name") is None
        assert FIELD_IDENTIFIER_PATTERN.match("field/name") is None

    def test_empty_string(self):
        """Test that empty string doesn't match."""
        assert FIELD_IDENTIFIER_PATTERN.match("") is None

    def test_real_violation_message_parsing(self):
        """Test pattern against real violation message prefixes.

        Violation messages from ProtocolContractValidator often have the format:
        'field_name: error message here'

        The pattern should match the field name portion but reject the error message.
        """
        # These are field name portions extracted before the colon
        assert FIELD_IDENTIFIER_PATTERN.match("node_type") is not None
        assert FIELD_IDENTIFIER_PATTERN.match("algorithm") is not None

        # These look like error messages, not field names
        assert FIELD_IDENTIFIER_PATTERN.match("Invalid node_type") is None
        assert FIELD_IDENTIFIER_PATTERN.match("Missing required") is None

    def test_violation_messages_with_embedded_colons(self):
        """Test that messages with colons in the value don't cause mis-parsing.

        When violation messages contain colons (e.g., "Invalid value: expected format X:Y"),
        we should NOT incorrectly parse "Invalid value" as a field name. The regex
        only matches lowercase snake_case identifiers, rejecting uppercase-starting text.
        """
        # Simulate parsing messages with embedded colons
        test_messages = [
            "Invalid value: expected format X:Y",
            "Error: failed to parse",
            "Validation failed: expected type int, got str",
            "Type mismatch: expected List[str]:Optional[int]",
        ]

        for message in test_messages:
            # This simulates the parsing logic in _validate_node_contract
            potential_field = message.split(":", 1)[0].strip()
            # All these should fail the pattern match because they start with uppercase
            assert FIELD_IDENTIFIER_PATTERN.match(potential_field) is None, (
                f"'{potential_field}' should not match FIELD_IDENTIFIER_PATTERN"
            )

    def test_valid_field_name_with_colon_message(self):
        """Test that valid field names followed by messages with colons are parsed correctly.

        Messages like "node_type: Invalid value: must be one of X:Y:Z" should extract
        'node_type' as the field name.
        """
        message = "node_type: Invalid value: must be one of compute:effect:reducer"
        potential_field = message.split(":", 1)[0].strip()

        # Should match because 'node_type' is a valid snake_case identifier
        assert FIELD_IDENTIFIER_PATTERN.match(potential_field) is not None
        assert potential_field == "node_type"
