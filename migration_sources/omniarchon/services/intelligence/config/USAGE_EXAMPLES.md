# Quality Gates Configuration - Usage Examples

This document provides practical examples for using the quality gates configuration system.

## Table of Contents

1. [Loading Configuration](#loading-configuration)
2. [Accessing Gate Settings](#accessing-gate-settings)
3. [Environment Detection](#environment-detection)
4. [Configuration Merging](#configuration-merging)
5. [Validation Integration](#validation-integration)
6. [CI/CD Integration](#cicd-integration)
7. [Custom Gate Implementation](#custom-gate-implementation)

---

## Loading Configuration

### Basic Configuration Loading

```python
# config_loader.py
from pathlib import Path
from typing import Dict, Any
import yaml

def load_quality_gates_config(environment: str = "production") -> Dict[str, Any]:
    """
    Load quality gates configuration for specified environment.

    Args:
        environment: "development", "staging", or "production"

    Returns:
        Merged configuration dictionary
    """
    config_dir = Path(__file__).parent

    # Load base configuration
    base_config_path = config_dir / "quality_gates.yaml"
    with open(base_config_path, 'r') as f:
        base_config = yaml.safe_load(f)

    # Load environment-specific configuration if exists
    env_config_path = config_dir / "environments" / f"{environment}.yaml"
    if env_config_path.exists():
        with open(env_config_path, 'r') as f:
            env_config = yaml.safe_load(f)

        # Merge configurations (env overrides base)
        return merge_configs(base_config, env_config)

    return base_config


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two configuration dictionaries.

    Args:
        base: Base configuration
        override: Override configuration (takes precedence)

    Returns:
        Merged configuration
    """
    import copy
    result = copy.deepcopy(base)

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value

    return result


# Usage
config = load_quality_gates_config(environment="production")
print(f"Loaded configuration version: {config['version']}")
```

---

## Accessing Gate Settings

### Example: Get ONEX Compliance Threshold

```python
from config_loader import load_quality_gates_config

# Load configuration
config = load_quality_gates_config(environment="production")

# Access ONEX compliance gate
onex_gate = config["quality_gates"]["onex_compliance"]

print(f"ONEX Compliance:")
print(f"  Enabled: {onex_gate['enabled']}")
print(f"  Blocking: {onex_gate['blocking']}")
print(f"  Threshold: {onex_gate['threshold']}")

# Check if gate is blocking
if onex_gate['blocking']:
    print(f"  ⚠️  This gate will block deployment on failure")
else:
    print(f"  ℹ️  This gate will only warn on failure")
```

### Example: Get All Gate Thresholds

```python
def get_gate_thresholds(environment: str = "production") -> Dict[str, float]:
    """Get all gate thresholds for environment."""
    config = load_quality_gates_config(environment)
    gates = config["quality_gates"]

    thresholds = {}

    # ONEX Compliance
    if "onex_compliance" in gates:
        thresholds["onex_compliance"] = gates["onex_compliance"].get("threshold", 0.95)

    # Test Coverage
    if "test_coverage" in gates:
        thresholds["test_coverage"] = gates["test_coverage"].get("threshold", 0.90)

    # Code Quality
    if "code_quality" in gates:
        thresholds["code_quality"] = gates["code_quality"].get("threshold", 0.70)

    # Multi-Model Consensus
    if "multi_model_consensus" in gates:
        thresholds["multi_model_consensus"] = gates["multi_model_consensus"].get("consensus_threshold", 0.67)

    return thresholds


# Usage
thresholds = get_gate_thresholds("production")
for gate, threshold in thresholds.items():
    print(f"{gate}: {threshold:.0%}")
```

---

## Environment Detection

### Automatic Environment Detection

```python
import os
from typing import Literal

EnvironmentType = Literal["development", "staging", "production"]

def detect_environment() -> EnvironmentType:
    """
    Detect environment from multiple sources.

    Priority:
    1. QUALITY_GATES_ENV environment variable
    2. CI/CD environment variables
    3. Default to production (fail-safe)
    """
    # Check explicit environment variable
    env = os.environ.get("QUALITY_GATES_ENV")
    if env in ["development", "staging", "production"]:
        return env

    # Check CI/CD environments
    if os.environ.get("CI") == "true":
        # GitHub Actions
        if os.environ.get("GITHUB_REF") == "refs/heads/main":
            return "production"
        elif os.environ.get("GITHUB_REF", "").startswith("refs/heads/release/"):
            return "staging"

        # GitLab CI
        if os.environ.get("CI_COMMIT_BRANCH") == "main":
            return "production"
        elif os.environ.get("CI_ENVIRONMENT_NAME") == "staging":
            return "staging"

    # Local development check
    if os.environ.get("DEVELOPMENT") == "true":
        return "development"

    # Default to production (safest)
    return "production"


# Usage
environment = detect_environment()
config = load_quality_gates_config(environment)
print(f"Running in {environment} environment")
```

---

## Configuration Merging

### Example: Merge Base + Environment Configs

```python
from typing import Dict, Any

def load_with_merge_example():
    """Example showing configuration merge behavior."""
    import yaml
    from pathlib import Path

    config_dir = Path(__file__).parent

    # Load base config
    base = yaml.safe_load(open(config_dir / "quality_gates.yaml"))

    # Load development config
    dev = yaml.safe_load(open(config_dir / "environments" / "development.yaml"))

    # Show base ONEX threshold
    base_onex = base["quality_gates"]["onex_compliance"]["threshold"]
    print(f"Base ONEX threshold: {base_onex}")  # 0.95

    # Show dev ONEX threshold
    dev_onex = dev["quality_gates"]["onex_compliance"]["threshold"]
    print(f"Development ONEX threshold: {dev_onex}")  # 0.75

    # Merge
    merged = merge_configs(base, dev)
    merged_onex = merged["quality_gates"]["onex_compliance"]["threshold"]
    print(f"Merged ONEX threshold: {merged_onex}")  # 0.75 (dev overrides)


load_with_merge_example()
```

---

## Validation Integration

### Example: Validate Before Running Gates

```python
import subprocess
import sys
from pathlib import Path

def validate_configuration(environment: str = None) -> bool:
    """
    Validate quality gates configuration before running.

    Args:
        environment: Specific environment to validate, or None for all

    Returns:
        True if validation passes, False otherwise
    """
    config_dir = Path(__file__).parent
    validator_script = config_dir / "validate_config.py"

    if not validator_script.exists():
        print("❌ Validator script not found")
        return False

    # Build command
    cmd = ["python", str(validator_script)]
    if environment:
        cmd.extend(["--env", environment])
    else:
        cmd.append("--all")

    # Run validation
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Print output
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result.returncode == 0


# Usage
if not validate_configuration(environment="production"):
    print("❌ Configuration validation failed")
    sys.exit(1)

print("✅ Configuration is valid")
```

---

## CI/CD Integration

### GitHub Actions Integration

```yaml
# .github/workflows/quality-gates.yml
name: Quality Gates

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  validate-config:
    name: Validate Configuration
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install pyyaml jsonschema

      - name: Validate Quality Gates Configuration
        run: |
          cd services/intelligence/config
          python validate_config.py --all

  run-quality-gates:
    name: Run Quality Gates
    needs: validate-config
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Detect Environment
        id: env
        run: |
          if [ "${{ github.ref }}" = "refs/heads/main" ]; then
            echo "environment=production" >> $GITHUB_OUTPUT
          elif [ "${{ github.ref }}" = "refs/heads/develop" ]; then
            echo "environment=staging" >> $GITHUB_OUTPUT
          else
            echo "environment=development" >> $GITHUB_OUTPUT
          fi

      - name: Run Quality Gates
        env:
          QUALITY_GATES_ENV: ${{ steps.env.outputs.environment }}
        run: |
          # TODO: Implement quality gates runner
          python -m intelligence.quality_gates.runner
```

### Pre-commit Hook Integration

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "🔍 Running quality gates pre-commit checks..."

# Check if quality gates config was modified
if git diff --cached --name-only | grep -q "quality_gates.yaml"; then
    echo "📝 Quality gates configuration modified, validating..."

    cd services/intelligence/config || exit 1

    # Validate configuration
    python validate_config.py

    if [ $? -ne 0 ]; then
        echo "❌ Quality gates configuration validation failed"
        echo "   Please fix errors before committing"
        exit 1
    fi

    echo "✅ Configuration validation passed"
fi

echo "✅ Pre-commit checks passed"
```

---

## Custom Gate Implementation

### Example: Implement ONEX Compliance Gate

```python
# quality_gates/gates/onex_compliance_gate.py
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
import re

@dataclass
class ONEXComplianceResult:
    """Result of ONEX compliance check."""
    passed: bool
    score: float
    violations: List[str]
    warnings: List[str]


class ONEXComplianceGate:
    """
    ONEX Compliance Quality Gate.

    Validates:
    - Naming conventions
    - Contract usage
    - Node type correctness
    - Architecture patterns
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize gate with configuration.

        Args:
            config: Gate configuration from quality_gates.yaml
        """
        self.config = config
        self.enabled = config.get("enabled", True)
        self.blocking = config.get("blocking", True)
        self.threshold = config.get("threshold", 0.95)
        self.rules = config.get("rules", {})

    def check_naming_conventions(self, file_path: str, content: str) -> Tuple[bool, List[str]]:
        """
        Check if file follows ONEX naming conventions.

        Args:
            file_path: Path to file being checked
            content: File content

        Returns:
            (passed, violations)
        """
        violations = []

        # Get naming patterns from config
        patterns = self.rules.get("naming_conventions", {}).get("patterns", {})

        # Check if it's a node file
        if "node_" in file_path:
            # Extract node type from filename
            if "_effect.py" in file_path:
                expected_pattern = patterns.get("files", {}).get("effect", "")
                class_pattern = patterns.get("classes", {}).get("effect", "")
            elif "_compute.py" in file_path:
                expected_pattern = patterns.get("files", {}).get("compute", "")
                class_pattern = patterns.get("classes", {}).get("compute", "")
            elif "_reducer.py" in file_path:
                expected_pattern = patterns.get("files", {}).get("reducer", "")
                class_pattern = patterns.get("classes", {}).get("reducer", "")
            elif "_orchestrator.py" in file_path:
                expected_pattern = patterns.get("files", {}).get("orchestrator", "")
                class_pattern = patterns.get("classes", {}).get("orchestrator", "")
            else:
                violations.append(f"File {file_path} doesn't match any node type pattern")
                return False, violations

            # Validate filename pattern
            if expected_pattern:
                filename = file_path.split("/")[-1]
                if not re.match(expected_pattern, filename):
                    violations.append(
                        f"Filename '{filename}' doesn't match pattern '{expected_pattern}'"
                    )

            # Validate class name pattern
            if class_pattern:
                # Find class definitions in content
                class_matches = re.findall(r'class\s+(\w+)', content)
                for class_name in class_matches:
                    if not re.match(class_pattern, class_name):
                        violations.append(
                            f"Class '{class_name}' doesn't match pattern '{class_pattern}'"
                        )

        return len(violations) == 0, violations

    def run(self, files: List[str]) -> ONEXComplianceResult:
        """
        Run ONEX compliance gate on files.

        Args:
            files: List of file paths to check

        Returns:
            ONEXComplianceResult with pass/fail and details
        """
        if not self.enabled:
            return ONEXComplianceResult(
                passed=True,
                score=1.0,
                violations=[],
                warnings=["ONEX compliance gate is disabled"]
            )

        all_violations = []
        all_warnings = []
        total_checks = 0
        passed_checks = 0

        for file_path in files:
            # Read file content
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
            except Exception as e:
                all_warnings.append(f"Could not read {file_path}: {e}")
                continue

            # Check naming conventions
            passed, violations = self.check_naming_conventions(file_path, content)
            total_checks += 1
            if passed:
                passed_checks += 1
            else:
                all_violations.extend(violations)

        # Calculate score
        score = passed_checks / total_checks if total_checks > 0 else 0.0

        # Determine pass/fail
        passed = score >= self.threshold

        return ONEXComplianceResult(
            passed=passed,
            score=score,
            violations=all_violations,
            warnings=all_warnings
        )


# Usage example
def main():
    from config_loader import load_quality_gates_config

    # Load configuration
    config = load_quality_gates_config(environment="production")
    onex_config = config["quality_gates"]["onex_compliance"]

    # Create gate
    gate = ONEXComplianceGate(onex_config)

    # Run on files
    files = [
        "src/nodes/node_database_writer_effect.py",
        "src/nodes/node_data_transformer_compute.py",
    ]

    result = gate.run(files)

    print(f"ONEX Compliance: {'✅ PASS' if result.passed else '❌ FAIL'}")
    print(f"Score: {result.score:.0%} (threshold: {gate.threshold:.0%})")

    if result.violations:
        print("\nViolations:")
        for violation in result.violations:
            print(f"  - {violation}")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning}")


if __name__ == "__main__":
    main()
```

---

## Complete Runner Example

### Quality Gates Runner

```python
# quality_gates/runner.py
import sys
from typing import Dict, Any, List
from pathlib import Path
from dataclasses import dataclass

from config_loader import load_quality_gates_config, detect_environment
from gates.onex_compliance_gate import ONEXComplianceGate


@dataclass
class GateResult:
    """Result from a single gate."""
    gate_name: str
    passed: bool
    blocking: bool
    score: float
    threshold: float
    violations: List[str]
    warnings: List[str]


class QualityGateRunner:
    """Run all quality gates for a codebase."""

    def __init__(self, environment: str = None):
        """
        Initialize runner.

        Args:
            environment: Environment to run in (auto-detect if None)
        """
        self.environment = environment or detect_environment()
        self.config = load_quality_gates_config(self.environment)
        self.results: List[GateResult] = []

    def run_all_gates(self, files: List[str]) -> bool:
        """
        Run all enabled quality gates.

        Args:
            files: List of files to check

        Returns:
            True if all blocking gates passed, False otherwise
        """
        print(f"🔍 Running quality gates in {self.environment} environment")
        print(f"{'=' * 70}")

        gates_config = self.config["quality_gates"]

        # ONEX Compliance Gate
        if gates_config.get("onex_compliance", {}).get("enabled"):
            self._run_onex_compliance_gate(files)

        # TODO: Add other gates
        # - Test Coverage Gate
        # - Code Quality Gate
        # - Performance Gate
        # - Security Gate
        # - Multi-Model Consensus Gate

        # Print results
        self._print_results()

        # Check if all blocking gates passed
        return all(
            result.passed or not result.blocking
            for result in self.results
        )

    def _run_onex_compliance_gate(self, files: List[str]):
        """Run ONEX compliance gate."""
        config = self.config["quality_gates"]["onex_compliance"]
        gate = ONEXComplianceGate(config)
        result = gate.run(files)

        self.results.append(GateResult(
            gate_name="ONEX Compliance",
            passed=result.passed,
            blocking=config.get("blocking", True),
            score=result.score,
            threshold=gate.threshold,
            violations=result.violations,
            warnings=result.warnings
        ))

    def _print_results(self):
        """Print all gate results."""
        print(f"\n{'=' * 70}")
        print("QUALITY GATES RESULTS")
        print(f"{'=' * 70}\n")

        for result in self.results:
            status = "✅ PASS" if result.passed else "❌ FAIL"
            blocking = " (BLOCKING)" if result.blocking else " (WARNING)"

            print(f"{result.gate_name}: {status}{blocking}")
            print(f"  Score: {result.score:.0%} (threshold: {result.threshold:.0%})")

            if result.violations:
                print(f"  Violations ({len(result.violations)}):")
                for violation in result.violations[:5]:  # Show first 5
                    print(f"    - {violation}")
                if len(result.violations) > 5:
                    print(f"    ... and {len(result.violations) - 5} more")

            if result.warnings:
                print(f"  Warnings ({len(result.warnings)}):")
                for warning in result.warnings[:3]:  # Show first 3
                    print(f"    - {warning}")

            print()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run quality gates")
    parser.add_argument("--env", choices=["development", "staging", "production"],
                       help="Environment to run in")
    parser.add_argument("files", nargs="*", help="Files to check (default: all)")

    args = parser.parse_args()

    # Get files to check
    if args.files:
        files = args.files
    else:
        # Default: find all Python files
        files = [str(p) for p in Path("src").rglob("*.py")]

    # Run quality gates
    runner = QualityGateRunner(environment=args.env)
    passed = runner.run_all_gates(files)

    # Exit with appropriate code
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
```

---

## Summary

These examples demonstrate:

1. **Configuration Loading**: How to load and merge configurations
2. **Environment Detection**: Automatic environment detection
3. **Gate Access**: Accessing gate settings from configuration
4. **Validation**: Validating configuration before use
5. **CI/CD Integration**: GitHub Actions and pre-commit hooks
6. **Custom Gates**: Implementing your own quality gates
7. **Runner**: Complete quality gates runner

For more information, see:
- `README.md` - Quick reference
- `QUALITY_GATES_DOCUMENTATION.md` - Complete documentation
- `quality_gates.yaml` - Configuration reference
