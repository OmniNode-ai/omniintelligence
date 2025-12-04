# Contract Linter Tool

The contract linter is a CLI tool for validating ONEX node contract YAML files against the canonical Pydantic models defined in `omnibase_core`. It ensures that contract files adhere to the ONEX schema and catches errors early in the development cycle.

## Overview

The contract linter validates four types of ONEX contracts:

1. **Node Contracts** - Primary contracts for ONEX nodes (compute, effect, reducer, orchestrator)
2. **FSM Subcontracts** - Finite State Machine definitions
3. **Workflow Coordination Subcontracts** - Workflow orchestration contracts
4. **Generic Subcontracts** - Operation-based contracts without node types

## Installation

The tool is included in the OmniIntelligence package. Install dependencies:

```bash
uv sync --group dev --group core
```

## Usage

### Basic Usage

Validate a single contract file:

```bash
uv run python -m omniintelligence.tools.contract_linter path/to/contract.yaml
```

### Multiple Files

Validate multiple contract files in one command:

```bash
uv run python -m omniintelligence.tools.contract_linter file1.yaml file2.yaml file3.yaml
```

### Verbose Output

Show detailed error messages with field paths:

```bash
uv run python -m omniintelligence.tools.contract_linter contract.yaml --verbose
```

Example output:

```
[FAIL] src/omniintelligence/nodes/my_node/v1_0_0/contracts/compute_contract.yaml
  - version.major: Input should be a valid integer (invalid_type)
  - operations.0.name: Field required (missing_field)

Summary: 0/1 contracts passed
```

### JSON Output

Get structured JSON output for integration with CI/CD:

```bash
uv run python -m omniintelligence.tools.contract_linter contract.yaml --json
```

Example output:

```json
{
  "file_path": "src/omniintelligence/nodes/my_node/v1_0_0/contracts/compute_contract.yaml",
  "valid": false,
  "errors": [
    {
      "field": "version.major",
      "message": "Input should be a valid integer",
      "error_type": "invalid_type"
    },
    {
      "field": "operations.0.name",
      "message": "Field required",
      "error_type": "missing_field"
    }
  ],
  "contract_type": "compute"
}
```

### Strict Mode

Enable stricter validation rules:

```bash
uv run python -m omniintelligence.tools.contract_linter contract.yaml --strict
```

## Exit Codes

The tool uses standard exit codes for CI/CD integration:

- **0** - All contracts valid
- **1** - One or more validation errors found
- **2** - File not found or other file-level errors

Example in CI/CD scripts:

```bash
if uv run python -m omniintelligence.tools.contract_linter contract.yaml; then
  echo "Contract validation passed"
else
  echo "Contract validation failed"
  exit 1
fi
```

## Integration with Pre-commit

The contract linter is integrated into the pre-commit hooks. Install pre-commit:

```bash
pre-commit install
```

The linter automatically validates contracts on commit:

```yaml
- repo: local
  hooks:
    - id: contract-linter
      name: contract linter
      entry: uv run python -m omniintelligence.tools.contract_linter
      language: system
      files: ^src/omniintelligence/nodes/[^/]+/v[^/]+/contracts/(.*_contract\.yaml|fsm_.*\.yaml)$
      pass_filenames: true
```

This configuration validates:
- Main node contracts (`*_contract.yaml`)
- FSM files (`fsm_*.yaml`)

Excluded:
- Subcontracts in `subcontracts/` directories
- Workflows in `workflows/` directories

Run pre-commit manually:

```bash
# Check all files
pre-commit run --all-files

# Check specific hook
pre-commit run contract-linter --all-files
```

## Integration with CI/CD

The contract linter is integrated into the GitHub Actions CI pipeline. See `.github/workflows/ci.yaml`:

```yaml
contract-validation:
  name: Contract Validation
  runs-on: ubuntu-latest
  steps:
    - name: Find and validate contracts
      run: |
        CONTRACT_FILES=$(find src/omniintelligence/nodes -type f \( -name "*_contract.yaml" -o -name "fsm_*.yaml" \) \
          ! -path "*/subcontracts/*" \
          ! -path "*/workflows/*" \
          | sort)

        uv run python -m omniintelligence.tools.contract_linter --verbose $CONTRACT_FILES
```

This ensures all contract files are validated on every pull request and push to main.

## Contract Type Detection

The linter automatically detects contract types based on structure:

| Contract Type | Detection Criteria |
|---------------|-------------------|
| FSM Subcontract | Contains `state_machine_name` or `states` |
| Workflow | Contains `workflow_type` or `subcontract_name` with `max_concurrent_workflows` |
| Node Contract | Contains `node_type` (compute, effect, reducer, orchestrator) |
| Generic Subcontract | Contains `operations` but no `node_type` |

## Validation Features

### Pydantic Model Validation

The linter uses `omnibase_core` Pydantic models for validation:

- `ModelContractCompute` - Compute node contracts
- `ModelContractEffect` - Effect node contracts
- `ModelContractReducer` - Reducer node contracts
- `ModelContractOrchestrator` - Orchestrator node contracts
- `ModelFSMSubcontract` - FSM definitions
- `ModelWorkflowCoordinationSubcontract` - Workflow contracts

This ensures contracts match the exact schema expected by the ONEX runtime.

### Error Categories

The linter categorizes errors for easier debugging:

| Error Type | Description | Example |
|-----------|-------------|---------|
| `missing_field` | Required field not present | `version.major` field missing |
| `invalid_type` | Field has wrong data type | String provided where integer expected |
| `invalid_value` | Value outside valid range | Negative version number |
| `invalid_enum` | Value not in allowed enum set | Invalid `node_type` value |
| `validation_error` | General validation failure | Custom ONEX validation rules |
| `file_not_found` | Contract file doesn't exist | Path incorrect |
| `not_a_file` | Path is a directory | Directory provided instead of file |
| `file_read_error` | Cannot read file | Permission denied |
| `empty_file` | File has no content | Empty or comments-only file |
| `yaml_parse_error` | Invalid YAML syntax | Malformed YAML |
| `unknown_contract_type` | Cannot detect contract type | Missing required top-level fields |

## Common Validation Errors

### Example 1: Missing Required Field

**Error:**
```
[FAIL] compute_contract.yaml
  - name: Field required (missing_field)
```

**Fix:** Add the required `name` field to the contract.

### Example 2: Invalid Node Type

**Error:**
```
[FAIL] node_contract.yaml
  - node_type: Invalid node_type: 'processor'. Must be one of: compute, effect, orchestrator, reducer (invalid_enum)
```

**Fix:** Use a valid node type: `compute`, `effect`, `reducer`, or `orchestrator`.

### Example 3: Invalid Version Format

**Error:**
```
[FAIL] contract.yaml
  - version.major: Input should be a valid integer (invalid_type)
```

**Fix:** Ensure version fields are integers:

```yaml
version:
  major: 1
  minor: 0
  patch: 0
```

### Example 4: YAML Syntax Error

**Error:**
```
[FAIL] contract.yaml
  - yaml: Invalid YAML syntax: while scanning a simple key (yaml_parse_error)
```

**Fix:** Check YAML syntax for missing colons, incorrect indentation, or unmatched quotes.

## Architecture

### Contract Detection Flow

```
1. Load YAML file
2. Parse YAML content
3. Detect contract type:
   - Check for FSM markers (state_machine_name, states)
   - Check for workflow markers (workflow_type)
   - Check for node_type
   - Check for operations
4. Route to appropriate validator:
   - FSM → ModelFSMSubcontract
   - Workflow → ModelWorkflowCoordinationSubcontract
   - Node → ProtocolContractValidator (routes to specific node type model)
   - Subcontract → Basic structure validation
5. Validate with Pydantic
6. Convert errors to standardized format
7. Return result
```

### Integration with omnibase_core

The linter leverages the `omnibase_core` validation infrastructure:

- **ProtocolContractValidator** - Main validation protocol for node contracts
- **Pydantic Models** - Canonical schema definitions for all contract types
- **ModelOnexError** - Custom ONEX validation error handling

This ensures the linter validates against the same rules as the ONEX runtime.

## Development

### Running Tests

The contract linter has comprehensive unit tests:

```bash
# Run all tests
pytest tests/unit/tools/test_contract_linter.py -v

# Run specific test
pytest tests/unit/tools/test_contract_linter.py::test_validate_compute_contract -v

# Run with coverage
pytest tests/unit/tools/test_contract_linter.py --cov=src/omniintelligence/tools --cov-report=html
```

### Test Coverage

Tests cover:
- All contract types (node, FSM, workflow, subcontract)
- All error categories
- File-level errors (not found, empty, invalid YAML)
- Batch validation
- JSON and text output formatting
- Exit codes
- Edge cases (empty operations, missing node_type, etc.)

## Troubleshooting

### Issue: Module not found error

**Error:**
```
ModuleNotFoundError: No module named 'omniintelligence'
```

**Solution:** Use `uv run` to execute in the correct environment:
```bash
uv run python -m omniintelligence.tools.contract_linter contract.yaml
```

### Issue: Contract validation fails in CI but passes locally

**Cause:** Different versions of `omnibase_core` or Python environment.

**Solution:**
1. Check `omnibase_core` version matches between local and CI
2. Ensure `uv.lock` is committed and up-to-date
3. Run `uv sync` to sync dependencies

### Issue: Pre-commit hook runs on wrong files

**Cause:** The pre-commit regex pattern may be matching unintended files.

**Solution:** Check the `files` regex in `.pre-commit-config.yaml`:
```yaml
files: ^src/omniintelligence/nodes/[^/]+/v[^/]+/contracts/(.*_contract\.yaml|fsm_.*\.yaml)$
```

This pattern should only match main contracts and FSM files, excluding subcontracts and workflows.

## API Reference

### ContractLinter Class

```python
from omniintelligence.tools.contract_linter import ContractLinter

linter = ContractLinter(strict=False, schema_version="1.0.0")

# Validate single file
result = linter.validate("path/to/contract.yaml")

# Validate multiple files
results = linter.validate_batch(["file1.yaml", "file2.yaml"])

# Get summary statistics
summary = linter.get_summary(results)
```

### Standalone Functions

```python
from omniintelligence.tools.contract_linter import (
    validate_contract,
    validate_contracts_batch,
)

# Single file validation
result = validate_contract("contract.yaml")

# Batch validation
results = validate_contracts_batch(["file1.yaml", "file2.yaml"])
```

### ContractValidationResult

```python
@dataclass
class ContractValidationResult:
    file_path: Path
    valid: bool
    errors: list[ContractValidationError]
    contract_type: str | None

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for JSON serialization."""
```

### ContractValidationError

```python
@dataclass
class ContractValidationError:
    field: str
    message: str
    error_type: EnumContractErrorType

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for JSON serialization."""
```

## Related Documentation

- [CLAUDE.md](../../../CLAUDE.md) - Project development guide
- [omnibase_core validation](https://github.com/your-org/omnibase_core) - Core validation infrastructure
- [ONEX Architecture Specification](https://docs.example.com/onex) - ONEX architecture patterns
- [Node Development Guide](../../../docs/NODE_DEVELOPMENT.md) - How to develop ONEX nodes

## License

Apache 2.0 - See [LICENSE](../../../LICENSE) for details.
