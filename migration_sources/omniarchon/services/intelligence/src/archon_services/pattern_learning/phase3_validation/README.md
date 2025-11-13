# Phase 3: Quality Gate Orchestration

**Automated quality gate enforcement for code validation**

## Overview

The Phase 3 Validation Layer provides a comprehensive quality gate orchestration system that enforces code quality, security, performance, test coverage, and ONEX architectural compliance through automated validation gates.

### Key Features

- 5 comprehensive quality gates (ONEX Compliance, Test Coverage, Code Quality, Performance, Security)
- Parallel or sequential gate execution
- Fail-fast support for blocking failures
- Configurable thresholds and parameters
- Detailed reporting with actionable recommendations
- Performance target: <30 seconds for all gates

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│           Quality Gate Orchestrator (Orchestrator)          │
├─────────────────────────────────────────────────────────────┤
│  Coordinates 5 independent quality gates:                   │
│                                                              │
│  1. ONEX Compliance Gate  ── NodeOnexValidatorCompute      │
│  2. Test Coverage Gate    ── pytest-cov                     │
│  3. Code Quality Gate     ── pylint/static analysis        │
│  4. Performance Gate      ── Pattern detection             │
│  5. Security Gate         ── Security scanning             │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

```bash
# Required dependencies
pip install pydantic pytest pytest-cov pylint

# Optional for enhanced functionality
pip install pytest-asyncio coverage
```

### Import

```python
from src.services.pattern_learning.phase3_validation import (
    NodeQualityGateOrchestrator,
    ModelQualityGateInput,
    ModelGateConfig,
    EnumGateType,
)
```

## Quick Start

### Basic Usage

```python
import asyncio
from src.services.pattern_learning.phase3_validation import (
    NodeQualityGateOrchestrator,
    ModelQualityGateInput,
    ModelGateConfig,
    EnumGateType,
)

async def validate_code():
    # Initialize orchestrator
    orchestrator = NodeQualityGateOrchestrator()

    # Configure gates
    gate_configs = [
        ModelGateConfig(
            gate_type=EnumGateType.ONEX_COMPLIANCE,
            enabled=True,
            threshold=0.95,  # 95% compliance required
            blocking=True,   # Blocks on failure
        ),
        ModelGateConfig(
            gate_type=EnumGateType.TEST_COVERAGE,
            enabled=True,
            threshold=0.90,  # 90% coverage required
            blocking=True,
        ),
        ModelGateConfig(
            gate_type=EnumGateType.SECURITY,
            enabled=True,
            threshold=0.80,  # 80% security score
            blocking=True,
        ),
    ]

    # Execute validation
    input_state = ModelQualityGateInput(
        code_path="/path/to/code.py",
        gate_configs=gate_configs,
        parallel_execution=True,
        fail_fast=False,
    )

    result = await orchestrator.execute_orchestration(input_state)

    # Check results
    if result.overall_passed:
        print("✅ All quality gates passed!")
    else:
        print(f"❌ {len(result.blocking_failures)} blocking failures")
        for gate_result in result.gate_results:
            print(f"  {gate_result['gate_type']}: {gate_result['status']}")

# Run validation
asyncio.run(validate_code())
```

## Quality Gates

### 1. ONEX Compliance Gate

Validates code against ONEX architectural patterns and naming conventions.

**Checks:**
- File naming conventions (`node_*_<type>.py`, `model_*.py`, etc.)
- Class naming patterns (`Node<Name><Type>`, `Model<Name>`, etc.)
- Method signatures (`execute_effect`, `execute_compute`, etc.)
- Contract usage and structure
- Node type detection

**Configuration:**

```python
ModelGateConfig(
    gate_type=EnumGateType.ONEX_COMPLIANCE,
    enabled=True,
    threshold=0.95,  # Minimum compliance score
    blocking=True,
    parameters={
        "check_naming": True,
        "check_structure": True,
        "check_contracts": True,
        "check_methods": True,
    }
)
```

**Scoring:**
- Starts at 1.0 (100% compliant)
- Deducts based on severity:
  - CRITICAL: -0.20 per issue
  - HIGH: -0.10 per issue
  - MEDIUM: -0.05 per issue
  - LOW: -0.02 per issue

### 2. Test Coverage Gate

Ensures adequate test coverage using pytest-cov.

**Checks:**
- Statement coverage percentage
- Branch coverage (optional)
- Test execution results

**Configuration:**

```python
ModelGateConfig(
    gate_type=EnumGateType.TEST_COVERAGE,
    enabled=True,
    threshold=0.90,  # 90% coverage required
    blocking=True,
    timeout_seconds=120,
)
```

**Requirements:**
- pytest and pytest-cov must be installed
- Tests must exist (follows common patterns: `test_*.py`, `*_test.py`)

### 3. Code Quality Gate

Analyzes code quality using static analysis tools (pylint).

**Checks:**
- Code style violations
- Potential bugs
- Code complexity
- Documentation quality

**Configuration:**

```python
ModelGateConfig(
    gate_type=EnumGateType.CODE_QUALITY,
    enabled=True,
    threshold=0.70,  # 70% quality score
    blocking=False,  # Non-blocking by default
)
```

**Note:** If pylint is not available, gate returns a warning rather than error.

### 4. Performance Gate

Detects common performance anti-patterns.

**Checks:**
- `range(len())` usage (suggest enumerate)
- List append in loops (suggest comprehensions)
- Potential optimization opportunities

**Configuration:**

```python
ModelGateConfig(
    gate_type=EnumGateType.PERFORMANCE,
    enabled=True,
    threshold=0.70,
    blocking=False,  # Non-blocking by default
)
```

### 5. Security Gate

Scans for common security vulnerabilities.

**Checks:**
- Hardcoded secrets (passwords, API keys)
- SQL injection patterns
- Use of `eval()` or similar dangerous functions
- Unsafe input handling

**Configuration:**

```python
ModelGateConfig(
    gate_type=EnumGateType.SECURITY,
    enabled=True,
    threshold=0.80,
    blocking=True,  # Should block on security issues
)
```

**Scoring:**
- CRITICAL vulnerabilities: -0.30 per issue
- HIGH vulnerabilities: -0.20 per issue
- Fails if ANY critical vulnerabilities found

## Configuration Guide

### Gate Configuration Options

```python
@dataclass
class ModelGateConfig:
    gate_type: EnumGateType        # Type of gate
    enabled: bool = True           # Whether gate is active
    threshold: float = 0.0         # Minimum passing score (0.0-1.0)
    blocking: bool = True          # Blocks pipeline on failure
    timeout_seconds: int = 60      # Maximum execution time
    parameters: Dict[str, Any] = {}  # Gate-specific parameters
```

### Orchestration Options

```python
@dataclass
class ModelQualityGateInput:
    code_path: str                 # Path to code/module to validate
    gate_configs: List[ModelGateConfig]  # Gates to execute
    correlation_id: str            # Tracking ID (auto-generated if not provided)
    fail_fast: bool = False        # Stop on first blocking failure
    parallel_execution: bool = True  # Run gates in parallel
    context: Dict[str, Any] = {}   # Additional context
```

### Example Configurations

#### Strict Configuration (All Gates Enabled)

```python
gate_configs = [
    ModelGateConfig(
        gate_type=EnumGateType.ONEX_COMPLIANCE,
        threshold=0.95,
        blocking=True,
    ),
    ModelGateConfig(
        gate_type=EnumGateType.TEST_COVERAGE,
        threshold=0.90,
        blocking=True,
    ),
    ModelGateConfig(
        gate_type=EnumGateType.CODE_QUALITY,
        threshold=0.70,
        blocking=True,
    ),
    ModelGateConfig(
        gate_type=EnumGateType.PERFORMANCE,
        threshold=0.70,
        blocking=True,
    ),
    ModelGateConfig(
        gate_type=EnumGateType.SECURITY,
        threshold=0.90,
        blocking=True,
    ),
]
```

#### Lenient Configuration (Non-Blocking)

```python
gate_configs = [
    ModelGateConfig(
        gate_type=EnumGateType.ONEX_COMPLIANCE,
        threshold=0.80,
        blocking=False,  # Warning only
    ),
    ModelGateConfig(
        gate_type=EnumGateType.SECURITY,
        threshold=0.70,
        blocking=True,   # Only security is blocking
    ),
]
```

#### Fast Fail Configuration

```python
input_state = ModelQualityGateInput(
    code_path="/path/to/code.py",
    gate_configs=gate_configs,
    fail_fast=True,        # Stop on first failure
    parallel_execution=False,  # Sequential for fail-fast
)
```

## Output Format

### Quality Gate Result

```python
{
    "overall_passed": bool,
    "total_gates": int,
    "gates_passed": int,
    "gates_failed": int,
    "blocking_failures": List[str],
    "gate_results": [
        {
            "gate_type": "onex_compliance",
            "status": "passed",  # passed/failed/warning/error
            "score": 0.95,
            "threshold": 0.90,
            "passed": true,
            "blocking": true,
            "duration_ms": 45.2,
            "issues": [
                {
                    "severity": "high",
                    "message": "Issue description",
                    "location": "file.py:line 42",
                    "suggestion": "How to fix it"
                }
            ],
            "metrics": {
                "total_issues": 1,
                "critical_issues": 0
            }
        }
    ],
    "total_duration_ms": 156.7,
    "metadata": {
        "performance_target_met": true,
        "parallel_execution": true
    }
}
```

## Integration Examples

### CI/CD Pipeline Integration

```python
#!/usr/bin/env python3
"""Pre-commit quality gate validation."""

import sys
import asyncio
from pathlib import Path

async def validate_changed_files():
    """Validate all changed Python files."""
    orchestrator = NodeQualityGateOrchestrator()

    # Get changed files from git
    changed_files = [
        f for f in Path("src").rglob("*.py")
        # Add git diff logic here
    ]

    all_passed = True

    for file_path in changed_files:
        result = await orchestrator.execute_orchestration(
            ModelQualityGateInput(
                code_path=str(file_path),
                gate_configs=[
                    ModelGateConfig(
                        gate_type=EnumGateType.ONEX_COMPLIANCE,
                        threshold=0.95,
                        blocking=True,
                    ),
                    ModelGateConfig(
                        gate_type=EnumGateType.SECURITY,
                        threshold=0.90,
                        blocking=True,
                    ),
                ],
            )
        )

        if not result.overall_passed:
            all_passed = False
            print(f"❌ {file_path}: FAILED")
            for failure in result.blocking_failures:
                print(f"   {failure}")
        else:
            print(f"✅ {file_path}: PASSED")

    return 0 if all_passed else 1

if __name__ == "__main__":
    exit_code = asyncio.run(validate_changed_files())
    sys.exit(exit_code)
```

### Testing Integration

```python
import pytest

@pytest.fixture
async def validated_code():
    """Fixture that validates code before tests run."""
    orchestrator = NodeQualityGateOrchestrator()

    result = await orchestrator.execute_orchestration(
        ModelQualityGateInput(
            code_path="src/my_module.py",
            gate_configs=[
                ModelGateConfig(
                    gate_type=EnumGateType.ONEX_COMPLIANCE,
                    threshold=0.90,
                ),
            ],
        )
    )

    assert result.overall_passed, "Code must be ONEX compliant"
    return result
```

## Performance

### Targets

- Single gate: <5 seconds
- All 5 gates (parallel): <30 seconds
- All 5 gates (sequential): <60 seconds

### Optimization Tips

1. **Use parallel execution** for independent gates
2. **Enable fail-fast** to stop early on critical failures
3. **Disable non-critical gates** in development
4. **Cache results** for unchanged files
5. **Run incrementally** on changed files only

## Error Handling

The orchestrator implements graceful error handling:

- **Invalid paths**: Returns error output with details
- **Gate execution failures**: Captured per-gate with ERROR status
- **Timeout**: Gates timeout individually after configured limit
- **Missing dependencies**: Non-critical gates return warnings

## Troubleshooting

### Issue: ONEX gate fails with naming errors

**Solution:** Ensure files follow ONEX naming conventions:
- Node files: `node_<name>_<type>.py`
- Classes: `Node<Name><Type>`
- Methods: `execute_<effect|compute|reduction|orchestration>`

### Issue: Test coverage gate fails to find tests

**Solution:** Ensure tests follow common patterns:
- `test_<name>.py`
- `<name>_test.py`
- Located in `tests/` directory

### Issue: Gates timeout

**Solution:** Increase timeout in gate config:
```python
ModelGateConfig(
    gate_type=EnumGateType.TEST_COVERAGE,
    timeout_seconds=300,  # 5 minutes
)
```

### Issue: Security gate reports false positives

**Solution:** Review and adjust threshold:
```python
ModelGateConfig(
    gate_type=EnumGateType.SECURITY,
    threshold=0.70,  # More lenient
    blocking=False,  # Make non-blocking
)
```

## Testing

### Run Unit Tests

```bash
# Run all tests
pytest tests/unit/pattern_learning/phase3_validation/ -v

# Run with coverage
pytest tests/unit/pattern_learning/phase3_validation/ --cov=src/services/pattern_learning/phase3_validation --cov-report=html

# Run specific test
pytest tests/unit/pattern_learning/phase3_validation/test_quality_gate_orchestrator.py::TestOnexValidator::test_onex_validator_compliant_code -v
```

### Coverage Target

- Overall: >85%
- Critical paths: >95%

## Contributing

### Adding New Gates

1. Create gate executor method in `node_quality_gate_orchestrator.py`:

```python
async def _execute_my_gate(
    self,
    code_path: str,
    gate_config: ModelGateConfig,
    correlation_id: str,
) -> ModelQualityGateResult:
    """Execute custom gate logic."""
    # Implement validation logic
    # Return ModelQualityGateResult
```

2. Add to `EnumGateType` in `model_contract_quality_gate.py`:

```python
class EnumGateType(str, Enum):
    # Existing gates...
    MY_CUSTOM_GATE = "my_custom_gate"
```

3. Update `_execute_single_gate` to route to your gate:

```python
elif gate_config.gate_type == EnumGateType.MY_CUSTOM_GATE:
    result = await self._execute_my_gate(code_path, gate_config, correlation_id)
```

4. Add tests in `test_quality_gate_orchestrator.py`

## License

Part of Archon Intelligence System - Internal Use

## Support

For issues or questions:
1. Check this README
2. Review test examples
3. Consult ONEX architecture documentation
