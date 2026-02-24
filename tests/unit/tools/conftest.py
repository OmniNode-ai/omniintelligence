# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""
Shared fixtures for Contract Linter tests.

Provides fixtures for valid and invalid contract YAML content, as well as
file-based fixtures for testing the ContractLinter class.
"""

import time
from pathlib import Path

import pytest

# =============================================================================
# Test Fixtures - Valid Contracts
# =============================================================================


@pytest.fixture
def valid_base_contract_yaml() -> str:
    """Minimal valid base contract YAML (compute type with algorithm included)."""
    return """
name: test_node
version:
  major: 1
  minor: 0
  patch: 0
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
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
    """Valid compute contract YAML with algorithm field included."""
    return """
name: test_compute_node
version:
  major: 1
  minor: 0
  patch: 0
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
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
    """Valid effect contract YAML with io_operations field included."""
    return """
name: test_effect_node
version:
  major: 1
  minor: 0
  patch: 0
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
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
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
  major: 1
  minor: 0
  patch: 0
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
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
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
    """Contract missing required 'contract_version' and 'node_version' fields.

    Note: The old 'version' field is no longer strictly required when
    contract_version and node_version are present. This fixture tests
    that contract_version is required for node contracts.
    """
    return """
name: test_node
version:
  major: 1
  minor: 0
  patch: 0
description: Missing contract_version field
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
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
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
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
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
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
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
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
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
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
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
    """Contract with malformed version structure.

    The contract_version field is a string instead of an object with
    major/minor/patch fields. The validator checks contract_version
    and node_version for proper structure.
    """
    return """
name: test_node
version:
  major: 1
  minor: 0
  patch: 0
contract_version: "1.0.0"
node_version:
  major: 1
  minor: 0
  patch: 0
description: Invalid version format (contract_version should be object)
node_type: compute
input_model: ModelInput
output_model: ModelOutput
"""


@pytest.fixture
def invalid_compute_missing_algorithm_yaml() -> str:
    """Compute contract without 'algorithm' field.

    Note: The 'algorithm' field is currently optional in the stub validator,
    so this contract may pass basic validation. This fixture is used for
    testing that the linter detects missing recommended fields for compute
    nodes when strict mode is enabled.
    """
    return """
name: test_compute
version:
  major: 1
  minor: 0
  patch: 0
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
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
    """Effect contract without 'io_operations' field.

    Note: The 'io_operations' field is currently optional in the stub validator,
    so this contract may pass basic validation. This fixture is used for
    testing that the linter detects missing recommended fields for effect
    nodes when strict mode is enabled.
    """
    return """
name: test_effect
version:
  major: 1
  minor: 0
  patch: 0
contract_version:
  major: 1
  minor: 0
  patch: 0
node_version:
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
    is_recoverable: false

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


# =============================================================================
# Test Fixtures - Watch Mode Mock Helpers
# =============================================================================

# Magic number explanation:
# WATCH_STAT_CALLS_BEFORE_CHANGE = 2
#   The watch loop calls stat() multiple times per iteration:
#   1. First call: capture initial mtime at loop start
#   2. Second call: check mtime in the file change detection
#   We simulate a file change after these initial stat() calls to trigger
#   the re-validation code path.
#
# WATCH_ITERATIONS_BEFORE_EXIT = 3
#   We allow the watch loop to run for 3 iterations before raising
#   KeyboardInterrupt to simulate Ctrl+C. This gives enough iterations to:
#   1. Capture initial mtimes
#   2. Detect a "change" (from mocked stat)
#   3. Re-validate and output results
#   Then exit cleanly.

WATCH_STAT_CALLS_BEFORE_CHANGE = 2
WATCH_ITERATIONS_BEFORE_EXIT = 3


def create_mock_stat_function(
    target_path: Path,
    initial_stat,
    initial_mtime: float,
    stat_call_counter: list[int],
):
    """
    Create a mock stat function that simulates file modification.

    This factory creates a stat() mock that returns the real stat for most calls,
    but returns a modified mtime after WATCH_STAT_CALLS_BEFORE_CHANGE calls
    to simulate a file being modified.

    Args:
        target_path: The Path object to simulate changes for.
        initial_stat: The original stat result to base mock on.
        initial_mtime: The original modification time.
        stat_call_counter: A list with single int element used as mutable counter.
            Using a list allows the closure to modify the count.

    Returns:
        A mock stat function compatible with Path.stat().
    """
    original_stat = Path.stat

    def mock_stat(self, *, follow_symlinks=True):
        """Mock stat to simulate mtime change deterministically."""
        result = original_stat(self, follow_symlinks=follow_symlinks)
        stat_call_counter[0] += 1

        # After initial mtime capture (first few calls), simulate a file change
        # by returning a stat with a newer mtime for the target path.
        if (
            stat_call_counter[0] > WATCH_STAT_CALLS_BEFORE_CHANGE
            and self == target_path
        ):

            class MockStat:
                """Mock stat result with incremented mtime to simulate file change."""

                st_mtime = initial_mtime + 1.0
                st_mode = initial_stat.st_mode
                st_size = initial_stat.st_size

            return MockStat()
        return result

    return mock_stat


def create_mock_sleep_function(iteration_counter: list[int]):
    """
    Create a mock sleep function that exits after a fixed number of iterations.

    This factory creates a sleep() mock that counts iterations and raises
    KeyboardInterrupt after WATCH_ITERATIONS_BEFORE_EXIT iterations to
    cleanly exit the watch loop.

    Args:
        iteration_counter: A list with single int element used as mutable counter.
            Using a list allows the closure to modify the count.

    Returns:
        A mock sleep function that raises KeyboardInterrupt after N iterations.
    """

    def mock_sleep(_seconds):
        """Mock sleep that exits watch loop after enough iterations."""
        iteration_counter[0] += 1
        if iteration_counter[0] >= WATCH_ITERATIONS_BEFORE_EXIT:
            raise KeyboardInterrupt
        # Use a minimal sleep to avoid test slowdown while still yielding
        time.sleep(0.01)

    return mock_sleep
