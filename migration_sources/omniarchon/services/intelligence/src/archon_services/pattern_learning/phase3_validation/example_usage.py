#!/usr/bin/env python3
"""
Example Usage: ONEX Compliance Validator

Demonstrates how to use the ONEX Compliance Validator to check code quality.

Author: Archon Intelligence Team
Date: 2025-10-02
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from src.archon_services.pattern_learning.phase3_validation.model_contract_validation import (
    IssueSeverity,
    ModelValidationInput,
)
from src.archon_services.pattern_learning.phase3_validation.node_onex_validator_compute import (
    NodeOnexValidatorCompute,
)

# ============================================================================
# Example Code Samples
# ============================================================================


VALID_COMPUTE_NODE = '''#!/usr/bin/env python3
"""
Valid ONEX Compute Node Example

This demonstrates a properly structured ONEX Compute node.
"""

from dataclasses import dataclass
from uuid import uuid4


@dataclass
class ModelExampleInput:
    """Input contract for example computation"""
    data: str
    correlation_id: str = ""


@dataclass
class ModelExampleOutput:
    """Output contract for computation results"""
    result: str
    processing_time_ms: float
    correlation_id: str


class NodeExampleCompute:
    """
    ONEX-Compliant Compute Node.

    Performs pure data transformations with no side effects.
    """

    async def execute_compute(
        self,
        input_state: ModelExampleInput
    ) -> ModelExampleOutput:
        """Execute computation"""
        import time
        start_time = time.time()

        try:
            # Pure transformation
            result = self._transform_data(input_state.data)

            processing_time = (time.time() - start_time) * 1000

            return ModelExampleOutput(
                result=result,
                processing_time_ms=processing_time,
                correlation_id=input_state.correlation_id
            )
        except Exception as e:
            return ModelExampleOutput(
                result="",
                processing_time_ms=0.0,
                correlation_id=input_state.correlation_id
            )

    def _transform_data(self, data: str) -> str:
        """Pure data transformation"""
        return data.upper()
'''


INVALID_COMPUTE_NODE = '''
class BadNode:
    """Missing ONEX patterns"""

    def process(self, data):
        # Missing async
        # Missing contracts
        # Missing correlation_id
        # Wrong method name
        with open("file.txt", "w") as f:
            f.write(data)  # I/O in Compute node!
        return data
'''


# ============================================================================
# Example Functions
# ============================================================================


async def example_basic_validation():
    """Example 1: Basic validation"""
    print("=" * 70)
    print("Example 1: Basic ONEX Compliance Validation")
    print("=" * 70)

    validator = NodeOnexValidatorCompute()

    # Validate good code
    input_state = ModelValidationInput(
        code_content=VALID_COMPUTE_NODE,
        file_path="node_example_compute.py",
    )

    output = await validator.execute_compute(input_state)

    print("\n✅ Valid Compute Node Results:")
    print(
        f"   Compliance Score: {output.result.compliance_score:.2f} ({output.result.compliance_score * 100:.0f}%)"
    )
    print(
        f"   Node Type: {output.result.node_type.value if output.result.node_type else 'Unknown'}"
    )
    print(f"   Has Contracts: {output.result.has_contracts}")
    print(
        f"   Checks Passed: {output.result.passed_checks}/{output.result.total_checks}"
    )
    print(f"   Issues Found: {len(output.result.issues)}")
    print(f"   Processing Time: {output.processing_time_ms:.1f}ms")

    if output.result.issues:
        print("\n   Issues:")
        for issue in output.result.issues[:3]:  # Show first 3
            print(f"   • [{issue.severity.value.upper()}] {issue.message}")

    print("\n   Recommendations:")
    for rec in output.result.recommendations[:3]:
        print(f"   • {rec}")


async def example_invalid_code_validation():
    """Example 2: Validation with issues"""
    print("\n" + "=" * 70)
    print("Example 2: Validation with ONEX Violations")
    print("=" * 70)

    validator = NodeOnexValidatorCompute()

    # Validate bad code
    input_state = ModelValidationInput(
        code_content=INVALID_COMPUTE_NODE,
        file_path="bad_node.py",  # Wrong filename
    )

    output = await validator.execute_compute(input_state)

    print("\n❌ Invalid Code Results:")
    print(
        f"   Compliance Score: {output.result.compliance_score:.2f} ({output.result.compliance_score * 100:.0f}%)"
    )
    print(
        f"   Checks Passed: {output.result.passed_checks}/{output.result.total_checks}"
    )
    print(f"   Issues Found: {len(output.result.issues)}")

    # Group issues by severity
    summary = output.result.to_dict()["summary"]
    print("\n   Issue Summary:")
    print(f"   • Critical: {summary['critical']}")
    print(f"   • High: {summary['high']}")
    print(f"   • Medium: {summary['medium']}")
    print(f"   • Low: {summary['low']}")

    print("\n   Top Issues:")
    for issue in sorted(output.result.issues, key=lambda i: i.severity.value)[:5]:
        print(f"   • [{issue.severity.value.upper()}] {issue.category.value}")
        print(f"     {issue.message}")
        print(f"     Fix: {issue.recommendation}")


async def example_selective_validation():
    """Example 3: Selective validation checks"""
    print("\n" + "=" * 70)
    print("Example 3: Selective Validation (Naming Only)")
    print("=" * 70)

    validator = NodeOnexValidatorCompute()

    # Only check naming conventions
    input_state = ModelValidationInput(
        code_content=INVALID_COMPUTE_NODE,
        file_path="bad_node.py",
        check_naming=True,
        check_contracts=False,
        check_node_type=False,
        check_architecture=False,
    )

    output = await validator.execute_compute(input_state)

    print("\n   Naming Convention Check Results:")
    print(f"   Compliance Score: {output.result.compliance_score:.2f}")
    print(f"   Issues Found: {len(output.result.issues)}")

    for issue in output.result.issues:
        print(f"   • {issue.message}")
        print(f"     Fix: {issue.recommendation}")


async def example_batch_validation():
    """Example 4: Batch validation of multiple files"""
    print("\n" + "=" * 70)
    print("Example 4: Batch Validation")
    print("=" * 70)

    validator = NodeOnexValidatorCompute()

    # Sample files to validate
    files_to_validate = [
        ("node_good_compute.py", VALID_COMPUTE_NODE),
        ("bad_node.py", INVALID_COMPUTE_NODE),
    ]

    results = []

    for filename, code in files_to_validate:
        input_state = ModelValidationInput(
            code_content=code,
            file_path=filename,
        )

        output = await validator.execute_compute(input_state)

        results.append(
            {
                "file": filename,
                "score": output.result.compliance_score,
                "issues": len(output.result.issues),
                "type": (
                    output.result.node_type.value
                    if output.result.node_type
                    else "unknown"
                ),
            }
        )

    # Display results
    print("\n   Validation Results:")
    print(f"   {'File':<30} {'Score':>8} {'Issues':>8} {'Type':>12}")
    print(f"   {'-' * 62}")

    for result in sorted(results, key=lambda x: x["score"], reverse=True):
        score_str = f"{result['score']:.2f}"
        emoji = (
            "✅" if result["score"] >= 0.8 else "⚠️" if result["score"] >= 0.6 else "❌"
        )
        print(
            f"   {emoji} {result['file']:<28} {score_str:>6} {result['issues']:>8} {result['type']:>12}"
        )

    # Statistics
    stats = validator.get_statistics()
    print("\n   Validation Statistics:")
    print(f"   • Files Validated: {stats['validation_count']}")
    print(f"   • Avg Processing Time: {stats['avg_processing_time_ms']:.1f}ms")
    print(f"   • Total Processing Time: {stats['total_processing_time_ms']:.1f}ms")


async def example_ci_cd_integration():
    """Example 5: CI/CD integration pattern"""
    print("\n" + "=" * 70)
    print("Example 5: CI/CD Integration Pattern")
    print("=" * 70)

    validator = NodeOnexValidatorCompute()
    min_score = 0.8  # Minimum compliance score for CI/CD

    # Validate code
    input_state = ModelValidationInput(
        code_content=VALID_COMPUTE_NODE,
        file_path="node_example_compute.py",
        strict_mode=True,
    )

    output = await validator.execute_compute(input_state)

    # Check if passes CI/CD requirements
    passes_ci = output.result.compliance_score >= min_score
    critical_issues = [
        i for i in output.result.issues if i.severity == IssueSeverity.CRITICAL
    ]

    print("\n   CI/CD Validation:")
    print(f"   • Minimum Score Required: {min_score:.2f}")
    print(f"   • Actual Score: {output.result.compliance_score:.2f}")
    print(f"   • Critical Issues: {len(critical_issues)}")

    if passes_ci and len(critical_issues) == 0:
        print("   • Status: ✅ PASS - Code meets quality standards")
        print("   • Action: Approve merge/deployment")
    else:
        print("   • Status: ❌ FAIL - Code needs improvement")
        print("   • Action: Block merge, fix issues")

        if critical_issues:
            print("\n   Critical Issues to Fix:")
            for issue in critical_issues:
                print(f"   • {issue.message}")


async def example_detailed_output():
    """Example 6: Detailed output inspection"""
    print("\n" + "=" * 70)
    print("Example 6: Detailed Output Inspection")
    print("=" * 70)

    validator = NodeOnexValidatorCompute()

    input_state = ModelValidationInput(
        code_content=VALID_COMPUTE_NODE,
        file_path="node_example_compute.py",
    )

    output = await validator.execute_compute(input_state)

    # Convert to dictionary for inspection
    result_dict = output.to_dict()

    print("\n   Complete Output Structure:")
    print("   • result")
    print(f"     - compliance_score: {result_dict['result']['compliance_score']:.2f}")
    print(
        f"     - compliance_percentage: {result_dict['result']['compliance_percentage']:.0f}%"
    )
    print(f"     - node_type: {result_dict['result']['node_type']}")
    print(f"     - has_contracts: {result_dict['result']['has_contracts']}")
    print(f"     - passed_checks: {result_dict['result']['passed_checks']}")
    print(f"     - total_checks: {result_dict['result']['total_checks']}")
    print("     - summary:")
    for severity, count in result_dict["result"]["summary"].items():
        if count > 0:
            print(f"       * {severity}: {count}")

    print(f"   • processing_time_ms: {result_dict['processing_time_ms']:.1f}ms")
    print(f"   • correlation_id: {result_dict['correlation_id'][:16]}...")
    print("   • metadata:")
    for key, value in result_dict["metadata"].items():
        print(f"     - {key}: {value}")


# ============================================================================
# Main
# ============================================================================


async def main():
    """Run all examples"""
    print("\n" + "=" * 70)
    print("ONEX Compliance Validator - Usage Examples")
    print("=" * 70)

    await example_basic_validation()
    await example_invalid_code_validation()
    await example_selective_validation()
    await example_batch_validation()
    await example_ci_cd_integration()
    await example_detailed_output()

    print("\n" + "=" * 70)
    print("Examples Complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
