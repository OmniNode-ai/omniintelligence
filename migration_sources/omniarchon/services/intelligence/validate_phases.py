#!/usr/bin/env python3
"""
Validate Phase 1 and Phase 2 code with ONEX validator.
"""

import asyncio
import json

# Add src to path
import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent))

from src.services.pattern_learning.phase3_validation.node_onex_validator_compute import (
    ModelOnexValidationInput,
    NodeOnexValidatorCompute,
)


async def validate_file(
    validator: NodeOnexValidatorCompute, file_path: Path
) -> Dict[str, Any]:
    """Validate a single file."""
    try:
        with open(file_path, "r") as f:
            code_content = f.read()

        input_state = ModelOnexValidationInput(
            code_path=str(file_path),
            code_content=code_content,
            correlation_id=f"validate-{file_path.name}",
            check_naming=True,
            check_contracts=True,
            check_node_type=True,
            check_architecture=True,
        )

        result = await validator.execute_compute(input_state)

        return {
            "file": str(file_path.relative_to(Path(__file__).parent)),
            "compliance_score": result.compliance_score,
            "passed": result.passed,
            "issues_count": len(result.issues),
            "critical_issues": result.metrics.get("critical_issues", 0),
            "high_issues": result.metrics.get("high_issues", 0),
            "recommendations": result.recommendations[:3],  # First 3
        }
    except Exception as e:
        return {
            "file": str(file_path),
            "error": str(e),
            "compliance_score": 0.0,
            "passed": False,
        }


async def main():
    """Main validation workflow."""
    validator = NodeOnexValidatorCompute()
    base_path = Path(__file__).parent / "src" / "services" / "pattern_learning"

    # Collect all node files
    phase1_files = list((base_path / "phase1_foundation").rglob("node_*.py"))
    phase2_files = list((base_path / "phase2_matching").rglob("node_*.py"))

    print(f"🔍 Validating {len(phase1_files)} Phase 1 files...")
    print(f"🔍 Validating {len(phase2_files)} Phase 2 files...")
    print()

    # Validate Phase 1
    phase1_results = []
    for file_path in sorted(phase1_files):
        result = await validate_file(validator, file_path)
        phase1_results.append(result)
        status = "✅" if result["passed"] else "⚠️"
        score = result["compliance_score"]
        print(f"{status} Phase 1: {file_path.name:<50} Score: {score:.2f}")

    print()

    # Validate Phase 2
    phase2_results = []
    for file_path in sorted(phase2_files):
        result = await validate_file(validator, file_path)
        phase2_results.append(result)
        status = "✅" if result["passed"] else "⚠️"
        score = result["compliance_score"]
        print(f"{status} Phase 2: {file_path.name:<50} Score: {score:.2f}")

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    # Phase 1 summary
    phase1_scores = [r["compliance_score"] for r in phase1_results]
    phase1_avg = sum(phase1_scores) / len(phase1_scores) if phase1_scores else 0
    phase1_passed = sum(1 for r in phase1_results if r["passed"])

    print(f"\n📊 Phase 1 ({len(phase1_files)} files):")
    print(f"   Average Compliance: {phase1_avg:.2%}")
    print(f"   Passed: {phase1_passed}/{len(phase1_files)}")
    print(f"   Min Score: {min(phase1_scores):.2f}")
    print(f"   Max Score: {max(phase1_scores):.2f}")

    # Phase 2 summary
    phase2_scores = [r["compliance_score"] for r in phase2_results]
    phase2_avg = sum(phase2_scores) / len(phase2_scores) if phase2_scores else 0
    phase2_passed = sum(1 for r in phase2_results if r["passed"])

    print(f"\n📊 Phase 2 ({len(phase2_files)} files):")
    print(f"   Average Compliance: {phase2_avg:.2%}")
    print(f"   Passed: {phase2_passed}/{len(phase2_files)}")
    print(f"   Min Score: {min(phase2_scores):.2f}")
    print(f"   Max Score: {max(phase2_scores):.2f}")

    # Overall
    all_scores = phase1_scores + phase2_scores
    overall_avg = sum(all_scores) / len(all_scores) if all_scores else 0
    overall_passed = phase1_passed + phase2_passed
    overall_total = len(phase1_files) + len(phase2_files)

    print(f"\n📊 Overall ({overall_total} files):")
    print(f"   Average Compliance: {overall_avg:.2%}")
    print(f"   Passed: {overall_passed}/{overall_total}")

    # Save detailed results
    results_file = Path(__file__).parent / "phase_validation_results.json"
    with open(results_file, "w") as f:
        json.dump(
            {
                "phase1": phase1_results,
                "phase2": phase2_results,
                "summary": {
                    "phase1_avg_compliance": phase1_avg,
                    "phase1_passed": phase1_passed,
                    "phase1_total": len(phase1_files),
                    "phase2_avg_compliance": phase2_avg,
                    "phase2_passed": phase2_passed,
                    "phase2_total": len(phase2_files),
                    "overall_avg_compliance": overall_avg,
                    "overall_passed": overall_passed,
                    "overall_total": overall_total,
                },
            },
            f,
            indent=2,
        )

    print(f"\n💾 Detailed results saved to: {results_file}")

    return overall_avg >= 0.8  # Success if >80% compliance


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
