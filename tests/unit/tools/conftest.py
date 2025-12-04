# SPDX-License-Identifier: Apache-2.0
"""
Shared fixtures for Contract Linter tests.

Provides fixtures for valid and invalid contract YAML content, as well as
file-based fixtures for testing the ContractLinter class.
"""

from pathlib import Path

import pytest

# =============================================================================
# Test Fixtures - Valid Contracts
# =============================================================================


@pytest.fixture
def valid_base_contract_yaml() -> str:
    """Minimal valid base contract YAML (compute type with required algorithm)."""
    return """
name: test_node
version:
  major: 1
  minor: 0
  patch: 0
description: A test node for validation
node_type: compute
input_model: ModelTestInput
output_model: ModelTestOutput
algorithm:
  algorithm_type: weighted_factor_algorithm
  factors:
    main_factor:
      weight: 1.0
      calculation_method: linear
performance:
  single_operation_max_ms: 1000
"""


@pytest.fixture
def valid_compute_contract_yaml() -> str:
    """Valid compute contract YAML with required algorithm field."""
    return """
name: test_compute_node
version:
  major: 1
  minor: 0
  patch: 0
description: A test compute node
node_type: compute
input_model: ModelComputeInput
output_model: ModelComputeOutput
algorithm:
  algorithm_type: weighted_factor_algorithm
  factors:
    compute_factor:
      weight: 1.0
      calculation_method: linear
performance:
  single_operation_max_ms: 1000
"""


@pytest.fixture
def valid_effect_contract_yaml() -> str:
    """Valid effect contract YAML with required io_operations field."""
    return """
name: test_effect_node
version:
  major: 1
  minor: 0
  patch: 0
description: A test effect node
node_type: effect
input_model: ModelEffectInput
output_model: ModelEffectOutput
io_operations:
  - operation_type: file_read
    atomic: true
"""


@pytest.fixture
def valid_contract_with_optional_fields_yaml() -> str:
    """Valid contract with optional fields populated."""
    return """
name: full_test_node
version:
  major: 2
  minor: 1
  patch: 3
description: A fully specified test node
node_type: compute
input_model: ModelFullInput
output_model: ModelFullOutput
algorithm:
  algorithm_type: weighted_factor_algorithm
  factors:
    full_factor:
      weight: 1.0
      calculation_method: linear
performance:
  single_operation_max_ms: 1000
author: test_author
documentation_url: https://docs.example.com/node
tags:
  - test
  - validation
  - compute
"""


# =============================================================================
# Test Fixtures - Invalid Contracts
# =============================================================================


@pytest.fixture
def invalid_missing_name_yaml() -> str:
    """Contract missing required 'name' field."""
    return """
version:
  major: 1
  minor: 0
  patch: 0
description: Missing name field
node_type: compute
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def invalid_missing_version_yaml() -> str:
    """Contract missing required 'version' field."""
    return """
name: test_node
description: Missing version field
node_type: compute
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def invalid_missing_description_yaml() -> str:
    """Contract missing required 'description' field."""
    return """
name: test_node
version:
  major: 1
  minor: 0
  patch: 0
node_type: compute
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def invalid_missing_node_type_yaml() -> str:
    """Contract missing required 'node_type' field."""
    return """
name: test_node
version:
  major: 1
  minor: 0
  patch: 0
description: Missing node_type
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def invalid_missing_input_model_yaml() -> str:
    """Contract missing required 'input_model' field."""
    return """
name: test_node
version:
  major: 1
  minor: 0
  patch: 0
description: Missing input_model
node_type: compute
output_model: ModelOutput
"""


@pytest.fixture
def invalid_missing_output_model_yaml() -> str:
    """Contract missing required 'output_model' field."""
    return """
name: test_node
version:
  major: 1
  minor: 0
  patch: 0
description: Missing output_model
node_type: compute
input_model: ModelInput
"""


@pytest.fixture
def invalid_node_type_yaml() -> str:
    """Contract with invalid node_type value."""
    return """
name: test_node
version:
  major: 1
  minor: 0
  patch: 0
description: Invalid node_type value
node_type: invalid_type
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def invalid_version_format_yaml() -> str:
    """Contract with malformed version structure."""
    return """
name: test_node
version: "1.0.0"
description: Invalid version format (should be object)
node_type: compute
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def invalid_compute_missing_algorithm_yaml() -> str:
    """Compute contract missing required 'algorithm' field."""
    return """
name: test_compute
version:
  major: 1
  minor: 0
  patch: 0
description: Compute node without algorithm
node_type: compute
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def invalid_effect_missing_io_operations_yaml() -> str:
    """Effect contract missing required 'io_operations' field."""
    return """
name: test_effect
version:
  major: 1
  minor: 0
  patch: 0
description: Effect node without io_operations
node_type: effect
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def malformed_yaml() -> str:
    """Malformed YAML that cannot be parsed."""
    return """
name: test_node
version:
  major: 1
  minor: 0
  this is not valid yaml
    - indentation error
  patch: [unclosed bracket
"""


@pytest.fixture
def empty_yaml() -> str:
    """Empty YAML content."""
    return ""


@pytest.fixture
def yaml_with_only_comments() -> str:
    """YAML with only comments, no content."""
    return """
# This is a comment
# Another comment
"""


# =============================================================================
# Test Fixtures - File-based
# =============================================================================


@pytest.fixture
def valid_contract_file(tmp_path: Path, valid_compute_contract_yaml: str) -> Path:
    """Create a valid contract file in temp directory."""
    contract_path = tmp_path / "valid_contract.yaml"
    contract_path.write_text(valid_compute_contract_yaml)
    return contract_path


@pytest.fixture
def invalid_contract_file(tmp_path: Path, invalid_missing_name_yaml: str) -> Path:
    """Create an invalid contract file in temp directory."""
    contract_path = tmp_path / "invalid_contract.yaml"
    contract_path.write_text(invalid_missing_name_yaml)
    return contract_path


@pytest.fixture
def malformed_yaml_file(tmp_path: Path, malformed_yaml: str) -> Path:
    """Create a malformed YAML file in temp directory."""
    contract_path = tmp_path / "malformed.yaml"
    contract_path.write_text(malformed_yaml)
    return contract_path


@pytest.fixture
def multiple_contract_files(
    tmp_path: Path,
    valid_compute_contract_yaml: str,
    valid_effect_contract_yaml: str,
    invalid_missing_name_yaml: str,
) -> list[Path]:
    """Create multiple contract files for batch testing."""
    files = []

    # Two valid contracts
    valid1 = tmp_path / "valid_compute.yaml"
    valid1.write_text(valid_compute_contract_yaml)
    files.append(valid1)

    valid2 = tmp_path / "valid_effect.yaml"
    valid2.write_text(valid_effect_contract_yaml)
    files.append(valid2)

    # One invalid contract
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(invalid_missing_name_yaml)
    files.append(invalid)

    return files


# =============================================================================
# Test Fixtures - FSM Subcontracts
# =============================================================================


@pytest.fixture
def valid_fsm_subcontract_yaml() -> str:
    """Valid FSM subcontract YAML."""
    return """
version:
  major: 1
  minor: 0
  patch: 0

state_machine_name: test_fsm
state_machine_version:
  major: 1
  minor: 0
  patch: 0

description: Test FSM for ingestion workflow

states:
  - version:
      major: 1
      minor: 0
      patch: 0
    state_name: RECEIVED
    state_type: operational
    description: Document received
    is_terminal: false

  - version:
      major: 1
      minor: 0
      patch: 0
    state_name: PROCESSING
    state_type: operational
    description: Document processing
    is_terminal: false

  - version:
      major: 1
      minor: 0
      patch: 0
    state_name: COMPLETED
    state_type: snapshot
    description: Processing complete
    is_terminal: true

initial_state: RECEIVED

transitions:
  - version:
      major: 1
      minor: 0
      patch: 0
    transition_name: start_processing
    from_state: RECEIVED
    to_state: PROCESSING
    trigger: START

  - version:
      major: 1
      minor: 0
      patch: 0
    transition_name: complete
    from_state: PROCESSING
    to_state: COMPLETED
    trigger: COMPLETE
"""


@pytest.fixture
def invalid_fsm_missing_state_machine_name_yaml() -> str:
    """FSM subcontract missing state_machine_name."""
    return """
version:
  major: 1
  minor: 0
  patch: 0

state_machine_version:
  major: 1
  minor: 0
  patch: 0

description: FSM missing state_machine_name

states:
  - version:
      major: 1
      minor: 0
      patch: 0
    state_name: RECEIVED
    state_type: operational
    description: Document received

initial_state: RECEIVED

transitions:
  - version:
      major: 1
      minor: 0
      patch: 0
    transition_name: self_loop
    from_state: RECEIVED
    to_state: RECEIVED
    trigger: LOOP
"""


@pytest.fixture
def invalid_fsm_missing_states_yaml() -> str:
    """FSM subcontract missing states."""
    return """
version:
  major: 1
  minor: 0
  patch: 0

state_machine_name: test_fsm
state_machine_version:
  major: 1
  minor: 0
  patch: 0

description: FSM missing states

initial_state: RECEIVED
"""


@pytest.fixture
def invalid_fsm_empty_states_yaml() -> str:
    """FSM subcontract with empty states list."""
    return """
version:
  major: 1
  minor: 0
  patch: 0

state_machine_name: test_fsm
state_machine_version:
  major: 1
  minor: 0
  patch: 0

description: FSM with empty states

states: []
initial_state: RECEIVED
"""
