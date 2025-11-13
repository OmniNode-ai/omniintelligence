# Phase 3 Validation Test Fixtures

Comprehensive test fixtures for validating Phase 3 quality gates and ONEX compliance.

## Overview

This fixture package provides everything needed to test Phase 3 validation logic:

- ✅ **ONEX Compliant Code**: Perfect examples of all node types
- ❌ **ONEX Non-Compliant Code**: Violations for testing detection
- 📊 **Quality Gate Scenarios**: Coverage, quality, performance issues
- 🤖 **Multi-Model Consensus**: Architectural decision scenarios
- 📋 **Expected Results**: Validation outputs for assertions
- ⚙️ **Quality Gate Configs**: Various gate configurations

## Directory Structure

```
phase3_validation/
├── compliant/                  # ONEX compliant code examples
│   ├── compliant_node_effect.py
│   ├── compliant_node_compute.py
│   ├── compliant_node_reducer.py
│   ├── compliant_node_orchestrator.py
│   └── compliant_contracts.py
├── non_compliant/              # ONEX non-compliant examples
│   ├── non_compliant_naming.py
│   ├── non_compliant_node_types.py
│   └── non_compliant_contracts.py
├── quality_gates/              # Quality gate test scenarios
│   ├── low_coverage_module.py
│   ├── poor_quality_code.py
│   └── slow_performance_code.py
├── consensus/                  # Multi-model consensus scenarios
│   ├── architectural_decision_scenarios.py
│   └── consensus_edge_cases.py
├── test_data/                  # Expected results and configs
│   ├── validation_results.py
│   └── quality_gate_configs.py
├── conftest.py                 # Pytest fixture definitions
└── README.md                   # This file
```

## Quick Start

### Using Fixtures in Tests

```python
import pytest

def test_onex_validation_compliant(compliant_effect_node):
    """Test validation with compliant Effect node."""
    validator = ONEXValidator()
    result = validator.validate(compliant_effect_node)

    assert result["compliant"] is True
    assert result["violations"] == []

def test_onex_validation_non_compliant(non_compliant_io_in_compute):
    """Test validation detects I/O in Compute node."""
    validator = ONEXValidator()
    result = validator.validate_code(non_compliant_io_in_compute)

    assert result["compliant"] is False
    assert "io_in_compute" in [v["type"] for v in result["violations"]]

def test_quality_gate_low_coverage(low_coverage_stats):
    """Test quality gate with low coverage."""
    gate = QualityGate(threshold=0.90)
    result = gate.evaluate(low_coverage_stats)

    assert result["passed"] is False
    assert result["coverage_percent"] < 0.90
```

### Available Fixtures

#### ONEX Compliant Code

- `compliant_effect_node` - Perfect Effect node class
- `compliant_effect_code` - Effect node as code string
- `compliant_compute_node` - Perfect Compute node class
- `compliant_compute_code` - Compute node as code string
- `compliant_reducer_node` - Perfect Reducer node class
- `compliant_reducer_code` - Reducer node as code string
- `compliant_orchestrator_node` - Perfect Orchestrator node class
- `compliant_orchestrator_code` - Orchestrator node as code string
- `compliant_contracts` - All contract factory functions

#### ONEX Non-Compliant Code

- `non_compliant_naming_violations` - Naming violations dictionary
- `non_compliant_io_in_compute` - Compute with I/O violations
- `non_compliant_state_in_compute` - Compute with state mutations
- `non_compliant_pure_in_effect` - Effect with only pure computation
- `non_compliant_node_type_violations` - All node type violations
- `non_compliant_contract_violations` - All contract violations

#### Quality Gates

- `low_coverage_stats` - Low test coverage statistics
- `coverage_report` - Simulated coverage report
- `missing_tests` - List of missing tests
- `quality_metrics` - Code quality metrics
- `performance_metrics` - Performance metrics
- `sla_violations` - Performance SLA violations

#### Consensus

- `architectural_decision_scenarios` - Decision scenarios
- `consensus_edge_cases` - Edge cases (splits, timeouts, etc.)
- `consensus_resolution_strategies` - Resolution strategies

#### Test Data

- `expected_validation_results` - All expected validation outputs
- `quality_gate_configs` - All gate configurations
- `default_quality_gate_config` - Default config
- `strict_quality_gate_config` - Strict production config
- `lenient_quality_gate_config` - Lenient dev config
- `onex_quality_gate_config` - ONEX-specific config

## Fixture Details

### 1. ONEX Compliant Code Fixtures

Perfect examples of each ONEX node type following all conventions:

**Effect Node**:
```python
class NodeDatabaseWriterEffect:
    async def execute_effect(self, contract: ModelContractEffect) -> ModelResult:
        async with self.transaction_manager.begin():
            result = await self._perform_database_write(contract)
            return ModelResult(success=True, data=result)
```

**Compute Node**:
```python
class NodeDataTransformerCompute:
    async def execute_compute(self, contract: ModelContractCompute) -> ModelResult:
        # Pure transformation - NO I/O
        transformed = await self._transform_data(contract.input_schema)
        return ModelResult(success=True, data=transformed)
```

**Reducer Node**:
```python
class NodeEventAggregatorReducer:
    async def execute_reduction(self, contract: ModelContractReducer) -> ModelResult:
        current_state = await self._load_state(contract.state_key)
        aggregated = await self._aggregate_events(current_state)
        await self._persist_state(contract.state_key, aggregated)
        return ModelResult(success=True, data=aggregated)
```

**Orchestrator Node**:
```python
class NodeWorkflowCoordinatorOrchestrator:
    async def execute_orchestration(self, contract: ModelContractOrchestrator) -> ModelResult:
        execution_plan = await self._build_execution_plan(contract.workflow_steps)
        results = await self._execute_workflow(execution_plan)
        return ModelResult(success=True, data=results)
```

### 2. ONEX Non-Compliant Code Fixtures

Examples of violations for testing detection:

**Naming Violations**:
- Missing suffix: `NodeDatabaseWriter` (should be `NodeDatabaseWriterEffect`)
- Wrong suffix: `NodeDataTransformerEffect` (should be `Compute` for pure transformation)
- Wrong case: `nodeDatabaseWriterEffect` (should be `NodeDatabaseWriterEffect`)
- Wrong method: `execute()` (should be `execute_effect()`)

**Node Type Violations**:
- I/O in Compute: Database queries, HTTP calls in Compute node
- State in Compute: Mutable instance variables in Compute node
- Pure in Effect: Effect node with only pure computation, no I/O
- Missing transactions: Effect node without transaction management

**Contract Violations**:
- Missing fields: Contract without name, version, description
- Wrong type: Effect node using Compute contract
- No base class: Contract not inheriting from ModelContractBase
- Invalid node_type: Contract with node_type='custom'

### 3. Quality Gate Fixtures

**Low Coverage Module** (~50% coverage):
- Tested: Basic happy paths
- Untested: Error paths, edge cases, validation failures
- Missing: 60% of test cases

**Poor Quality Code**:
- High complexity: Cyclomatic complexity 15 (threshold: 10)
- Code duplication: 75% duplicated code
- Long methods: 70-80 lines (threshold: 50)
- Deep nesting: 5 levels (threshold: 3)

**Slow Performance Code**:
- O(n²) algorithms where O(n) is possible
- N+1 query patterns (201 queries instead of 2)
- Memory leaks (unbounded growth)
- Blocking I/O (sequential instead of parallel)

### 4. Consensus Fixtures

**Architectural Decision Scenarios**:
1. Node type selection (Effect vs Compute vs Orchestrator)
2. Contract design (rich vs thin contracts)
3. Performance vs maintainability tradeoffs
4. Scaling strategies (horizontal vs vertical)

**Edge Cases**:
1. Split decisions (50/50 model split)
2. Model timeouts (degraded quorum)
3. Strong disagreements (high confidence, different recommendations)
4. Low confidence across all models
5. Ties with different reasoning

### 5. Test Data Fixtures

**Expected Validation Results**:
- ONEX compliant validation (pass)
- ONEX non-compliant validation (fail with violations)
- Quality gate pass (all gates passed)
- Quality gate fail (coverage/quality failures)
- Consensus achieved (>0.70 confidence)
- Consensus failed (<0.70 confidence)

**Quality Gate Configurations**:
- **Default**: Standard gates (90% coverage, complexity ≤10)
- **Strict**: Production gates (95% coverage, zero tolerance)
- **Lenient**: Development gates (70% coverage, warnings only)
- **Performance**: Performance-focused (60% weight on performance)
- **Security**: Security-focused (60% weight on security)
- **ONEX**: ONEX-specific (naming, contracts, architecture)

## Usage Examples

### Testing ONEX Compliance Validation

```python
def test_effect_node_validation(compliant_effect_node, compliant_effect_code):
    """Test Effect node validation."""
    # Using class
    validator = ONEXValidator()
    result = validator.validate_node(compliant_effect_node)
    assert result["compliant"] is True

    # Using code string
    result = validator.validate_code(compliant_effect_code)
    assert result["compliant"] is True
    assert result["checks"]["naming_convention"]["passed"] is True
    assert result["checks"]["method_signature"]["passed"] is True
```

### Testing Quality Gates

```python
def test_quality_gate_with_low_coverage(
    low_coverage_stats,
    default_quality_gate_config
):
    """Test quality gate fails with low coverage."""
    gate = QualityGate(config=default_quality_gate_config)
    result = gate.evaluate_coverage(low_coverage_stats)

    assert result["passed"] is False
    assert result["coverage_percent"] == 0.50
    assert result["threshold"] == 0.90
```

### Testing Consensus

```python
def test_consensus_split_decision(consensus_edge_cases):
    """Test consensus handles split decision."""
    split_case = consensus_edge_cases[0]  # EDGE_CASE_SPLIT_DECISION

    resolver = ConsensusResolver()
    result = resolver.resolve(split_case["model_responses"])

    assert result["consensus_reached"] is False
    assert result["recommended_action"] == "request_human_review"
```

### Testing with Expected Results

```python
def test_validation_matches_expected(
    compliant_effect_code,
    expected_validation_results
):
    """Test validation produces expected results."""
    validator = ONEXValidator()
    result = validator.validate_code(compliant_effect_code)

    expected = expected_validation_results["onex_compliant"]

    assert result["compliant"] == expected["result"]["compliant"]
    assert result["compliance_score"] == expected["result"]["compliance_score"]
```

## Fixture Coverage Matrix

| Category | Compliant | Non-Compliant | Total |
|----------|-----------|---------------|-------|
| Effect Nodes | 1 | 3 | 4 |
| Compute Nodes | 1 | 3 | 4 |
| Reducer Nodes | 1 | 2 | 3 |
| Orchestrator Nodes | 1 | 1 | 2 |
| Contracts | 4 | 6 | 10 |
| Quality Gates | - | 3 | 3 |
| Consensus | - | 9 | 9 |
| **Total** | **8** | **27** | **35** |

## Best Practices

### 1. Use Specific Fixtures

```python
# Good: Use specific fixture
def test_io_violation(non_compliant_io_in_compute):
    assert detect_io_in_compute(non_compliant_io_in_compute) is True

# Less specific: Use general fixture
def test_violations(all_non_compliant_code_strings):
    for code in all_non_compliant_code_strings.values():
        # Less targeted testing
        pass
```

### 2. Combine Fixtures

```python
def test_validation_with_config(
    compliant_effect_node,
    strict_quality_gate_config
):
    """Combine multiple fixtures for complex tests."""
    validator = ONEXValidator(config=strict_quality_gate_config)
    result = validator.validate(compliant_effect_node)
    assert result["passed"] is True
```

### 3. Parameterize with Fixtures

```python
@pytest.mark.parametrize("node_type", ["effect", "compute", "reducer", "orchestrator"])
def test_all_compliant_nodes(all_compliant_nodes, node_type):
    """Test all node types with parameterization."""
    node_class = all_compliant_nodes[node_type]
    validator = ONEXValidator()
    result = validator.validate_node(node_class)
    assert result["compliant"] is True
```

### 4. Assert Against Expected Results

```python
def test_matches_expected(
    compliant_effect_code,
    expected_validation_results
):
    """Always assert against expected results."""
    result = validate(compliant_effect_code)
    expected = expected_validation_results["onex_compliant"]

    assert result == expected["result"]
```

## Extending Fixtures

### Adding New Compliant Examples

1. Create new file in `compliant/`
2. Implement fully compliant node/contract
3. Add code string constant
4. Export in `conftest.py`

### Adding New Violations

1. Create new file in `non_compliant/`
2. Implement violation examples
3. Document violation type and severity
4. Add to violations dictionary
5. Export in `conftest.py`

### Adding New Quality Scenarios

1. Create new file in `quality_gates/`
2. Implement scenario with metrics
3. Document thresholds and violations
4. Export in `conftest.py`

## Fixture Maintenance

- **Version**: 1.0.0
- **Last Updated**: 2025-10-02
- **Coverage**: 35 fixtures across 5 categories
- **Documentation**: Complete with examples

## Related Documentation

- [ONEX Architecture Patterns](../../../../../docs/onex/archive/ONEX_ARCHITECTURE_PATTERNS_COMPLETE.md)
- [Testing Guide](../../QUICKSTART.md)

## Support

For questions or issues with fixtures:
1. Check fixture docstrings for usage details
2. Review examples in this README
3. Consult `conftest.py` for all available fixtures
4. See test files for real-world usage
