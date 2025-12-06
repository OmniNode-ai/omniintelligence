# Contract Validation Guide

Reference guide for creating and validating ONEX contracts using the contract linter.

## Overview

The contract linter validates YAML contracts against ONEX canonical Pydantic models from `omnibase_core`. This guide documents the required contract formats and common validation errors.

## Contract Types

| Type | File Pattern | Key Fields |
|------|--------------|------------|
| compute | `*_contract.yaml` | `name`, `version`, `node_type: compute`, `input_model`, `output_model` |
| effect | `*_contract.yaml` | `name`, `version`, `node_type: effect`, `io_operations` |
| reducer | `*_contract.yaml` | `name`, `version`, `node_type: reducer` |
| orchestrator | `*_contract.yaml` | `name`, `version`, `node_type: orchestrator` |
| fsm_subcontract | `fsm_*.yaml` | `state_machine_name`, `states`, `initial_state`, `transitions` |
| workflow | `workflow_*.yaml` | `workflow_type` or `subcontract_name` with `max_concurrent_workflows` |
| subcontract | `*_subcontract.yaml` | `name`, `version`, `operations` (no `node_type`) |

## Required Fields

### All Node Contracts

Every node contract requires these fields:

```yaml
name: my_node_name                # Node identifier (string)
version:                          # Semantic version object
  major: 1                        # Non-negative integer
  minor: 0                        # Non-negative integer
  patch: 0                        # Non-negative integer
node_type: compute                # One of: compute, effect, reducer, orchestrator
```

### Compute Contracts

Compute nodes additionally require:

```yaml
input_model: module.path.ModelInput    # Fully-qualified model class path
output_model: module.path.ModelOutput  # Fully-qualified model class path
```

### Effect Contracts

Effect nodes additionally require:

```yaml
io_operations:                    # List of I/O operation definitions
  - operation_type: api_call
    atomic: false
    timeout_seconds: 30
```

### FSM Subcontracts

FSM subcontracts require:

```yaml
state_machine_name: my_fsm        # FSM identifier
states:                           # List of state definitions
  - state_name: INITIAL
    state_type: operational
    is_terminal: false
initial_state: INITIAL            # Must match a state_name
transitions:                      # List of transition definitions
  - from_state: INITIAL
    to_state: PROCESSING
    trigger: START
```

## Version Format

The version field must be a structured object with integer components.

**Correct format:**

```yaml
version:
  major: 1
  minor: 0
  patch: 0
```

**Incorrect formats:**

```yaml
# String version - INVALID
version: "1.0.0"

# Missing components - INVALID
version:
  major: 1

# Non-integer values - INVALID
version:
  major: "1"
  minor: "0"
  patch: "0"
```

## Common Validation Errors

### 1. String Versions

**Before (invalid):**
```yaml
version: "1.0.0"
```

**After (valid):**
```yaml
version:
  major: 1
  minor: 0
  patch: 0
```

### 2. Missing node_type

**Before (invalid):**
```yaml
name: my_compute_node
version:
  major: 1
  minor: 0
  patch: 0
input_model: module.ModelInput
```

**After (valid):**
```yaml
name: my_compute_node
version:
  major: 1
  minor: 0
  patch: 0
node_type: compute              # Add explicit node_type
input_model: module.ModelInput
```

### 3. Invalid node_type Values

**Before (invalid):**
```yaml
node_type: processor            # Not a valid ONEX node type
```

**After (valid):**
```yaml
node_type: compute              # Must be: compute, effect, reducer, or orchestrator
```

### 4. Inline Models

**Before (may cause issues):**
```yaml
input_model: ModelInput
```

**After (recommended):**
```yaml
input_model: omniintelligence.nodes.my_node.v1_0_0.models.ModelInput
```

Use fully-qualified module paths for model references to ensure the runtime can locate them.

### 5. Missing Required Fields in States

**Before (invalid):**
```yaml
states:
  - state_name: PROCESSING
```

**After (valid):**
```yaml
states:
  - version:
      major: 1
      minor: 0
      patch: 0
    state_name: PROCESSING
    state_type: operational
    is_terminal: false
    is_recoverable: true
```

### 6. Missing io_operations in Effect Contracts

Effect nodes require at least one I/O operation:

**Before (invalid):**
```yaml
name: my_effect
node_type: effect
version:
  major: 1
  minor: 0
  patch: 0
```

**After (valid):**
```yaml
name: my_effect
node_type: effect
version:
  major: 1
  minor: 0
  patch: 0
io_operations:
  - operation_type: database_write
    atomic: true
    timeout_seconds: 30
```

## Running the Linter

### Validate Single Contract

```bash
python -m omniintelligence.tools.contract_linter path/to/contract.yaml
```

### Validate Multiple Contracts

```bash
python -m omniintelligence.tools.contract_linter contracts/*.yaml
```

### Verbose Output

Show detailed error messages with field paths:

```bash
python -m omniintelligence.tools.contract_linter path/to/contract.yaml --verbose
```

Example output:

```
[FAIL] src/nodes/my_node/v1_0_0/contracts/compute_contract.yaml
  - version.major: Input should be a valid integer (invalid_type)
  - node_type: Field required (missing_field)

Summary: 0/1 contracts passed
```

### JSON Output for CI/CD

```bash
python -m omniintelligence.tools.contract_linter path/to/contract.yaml --json
```

Example output:

```json
{
  "file_path": "path/to/contract.yaml",
  "valid": false,
  "errors": [
    {
      "field": "version.major",
      "message": "Input should be a valid integer",
      "error_type": "invalid_type"
    }
  ],
  "contract_type": null
}
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All contracts valid |
| `1` | Validation errors found |
| `2` | File errors (not found, unreadable, empty) |

### CI/CD Integration

```bash
# Exit with error if validation fails
python -m omniintelligence.tools.contract_linter contracts/*.yaml || exit 1

# Conditional handling
if python -m omniintelligence.tools.contract_linter contracts/*.yaml; then
  echo "All contracts valid"
else
  echo "Contract validation failed"
  exit 1
fi
```

## Validation Checklist

Use this checklist when creating or validating contracts:

- [ ] Use structured `major`/`minor`/`patch` format for version
- [ ] Include explicit `node_type` field
- [ ] Use fully-qualified model paths for `input_model` and `output_model`
- [ ] Include `io_operations` for effect nodes
- [ ] Include required state fields for FSM subcontracts
- [ ] Run linter in verbose mode to identify issues
- [ ] Verify contracts pass in CI/CD pipeline

## Pre-commit Integration

The contract linter is integrated with pre-commit hooks. Install:

```bash
pre-commit install
```

Contracts are automatically validated on commit. The hook validates:
- Main node contracts (`*_contract.yaml`)
- FSM files (`fsm_*.yaml`)

Files in `subcontracts/` and `workflows/` directories are excluded by default.

## Related Documentation

- [Contract Linter Tool README](../src/omniintelligence/tools/README.md) - Full tool documentation
- [CLAUDE.md](../CLAUDE.md) - Project development commands
