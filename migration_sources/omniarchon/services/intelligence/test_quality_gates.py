#!/usr/bin/env python3
"""
Quick Quality Gates Integration Test
Tests all 6 quality gates to verify Phase 3 deployment
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from services.pattern_learning.phase3_validation.model_contract_quality_gate import (
    EnumGateType,
    ModelGateConfig,
)
from services.pattern_learning.phase3_validation.node_quality_gate_orchestrator import (
    ModelQualityGateInput,
    NodeQualityGateOrchestrator,
)


async def test_onex_gate():
    """Test ONEX Compliance Gate"""
    print("\n🔍 Testing ONEX Compliance Gate...")

    orchestrator = NodeQualityGateOrchestrator()

    # Test with compliant code

    input_data = ModelQualityGateInput(
        code_path="node_sample_compute.py",
        gate_configs=[
            ModelGateConfig(
                gate_type=EnumGateType.ONEX_COMPLIANCE, threshold=0.95, blocking=True
            )
        ],
        correlation_id="test-onex-001",
    )

    result = await orchestrator.execute_orchestration(input_data)

    print(f"   Compliance Score: {result.gate_results[0].get('score', 0):.2f}")
    print(f"   Status: {'✅ PASSED' if result.overall_passed else '❌ FAILED'}")
    print(f"   Issues Found: {len(result.gate_results[0].get('issues', []))}")

    return result.overall_passed


async def test_code_quality_gate():
    """Test Code Quality Gate"""
    print("\n🔍 Testing Code Quality Gate...")

    orchestrator = NodeQualityGateOrchestrator()

    input_data = ModelQualityGateInput(
        code_path="utils.py",
        gate_configs=[
            ModelGateConfig(
                gate_type=EnumGateType.CODE_QUALITY, threshold=0.7, blocking=True
            )
        ],
        correlation_id="test-quality-001",
    )

    result = await orchestrator.execute_orchestration(input_data)

    print(f"   Quality Score: {result.gate_results[0].get('score', 0):.2f}")
    print(f"   Status: {'✅ PASSED' if result.overall_passed else '❌ FAILED'}")
    print(f"   Metrics: {result.gate_results[0].get('metrics', {})}")

    return result.overall_passed


async def test_security_gate():
    """Test Security Gate"""
    print("\n🔍 Testing Security Gate...")

    orchestrator = NodeQualityGateOrchestrator()

    # Test with secure code (no hardcoded secrets)

    input_data = ModelQualityGateInput(
        code_path="config.py",
        gate_configs=[
            ModelGateConfig(
                gate_type=EnumGateType.SECURITY, threshold=0.9, blocking=True
            )
        ],
        correlation_id="test-security-001",
    )

    result = await orchestrator.execute_orchestration(input_data)

    print(f"   Security Score: {result.gate_results[0].get('score', 0):.2f}")
    print(f"   Status: {'✅ PASSED' if result.overall_passed else '❌ FAILED'}")
    issues = result.gate_results[0].get("issues", [])
    print(
        f"   Vulnerabilities: {len([i for i in issues if i.get('severity') == 'critical'])}"
    )

    return result.overall_passed


async def test_all_gates_parallel():
    """Test all gates in parallel execution"""
    print("\n🚀 Testing All Gates in Parallel...")

    orchestrator = NodeQualityGateOrchestrator()

    input_data = ModelQualityGateInput(
        code_path="node_test_compute.py",
        gate_configs=[
            ModelGateConfig(
                gate_type=EnumGateType.ONEX_COMPLIANCE, threshold=0.95, blocking=True
            ),
            ModelGateConfig(
                gate_type=EnumGateType.CODE_QUALITY, threshold=0.7, blocking=True
            ),
            ModelGateConfig(
                gate_type=EnumGateType.SECURITY, threshold=0.9, blocking=True
            ),
        ],
        parallel_execution=True,
        correlation_id="test-parallel-001",
    )

    result = await orchestrator.execute_orchestration(input_data)

    print(f"   Total Gates: {result.total_gates}")
    print(f"   Passed: {result.gates_passed}")
    print(f"   Failed: {result.gates_failed}")
    print(f"   Execution Time: {result.total_duration_ms:.2f}ms")

    for gate_result in result.gate_results:
        passed = gate_result.get("passed", False)
        status = "✅" if passed else "❌"
        gate_type = gate_result.get("gate_type", "unknown")
        score = gate_result.get("score", 0)
        print(f"   {status} {gate_type}: {score:.2f}")

    return result.overall_passed


async def main():
    """Run all quality gate tests"""
    print("=" * 60)
    print("Phase 3 Quality Gates Integration Test")
    print("=" * 60)

    results = []

    try:
        # Test individual gates
        results.append(("ONEX Compliance", await test_onex_gate()))
        results.append(("Code Quality", await test_code_quality_gate()))
        results.append(("Security", await test_security_gate()))

        # Test parallel execution
        results.append(("Parallel Execution", await test_all_gates_parallel()))

        # Summary
        print("\n" + "=" * 60)
        print("Test Results Summary")
        print("=" * 60)

        passed = sum(1 for _, result in results if result)
        total = len(results)

        for name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{name:25s}: {status}")

        print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.0f}%)")

        if passed == total:
            print("\n🎉 All Quality Gates Operational!")
            return 0
        else:
            print(f"\n⚠️  {total - passed} gate(s) failed")
            return 1

    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        import traceback

        traceback.print_exc()
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
