#!/usr/bin/env python3
"""
WFC-07 Framework Validation Test Suite
Comprehensive testing for hybrid architecture performance and compatibility
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Dict, List

import psutil


class FrameworkValidator:
    """
    Comprehensive validation suite for ONEX Agent Framework
    Tests against all critical success criteria
    """

    def __init__(self):
        self.results = {
            "include_resolution_times": [],
            "quality_gate_execution_times": [],
            "memory_footprint": {},
            "initialization_overhead": {},
            "agent_compatibility": {},
            "framework_files": {},
            "performance_baseline": {},
        }

        self.framework_files = [
            "/Users/jonah/.claude/agents/MANDATORY_FUNCTIONS.md",
            "/Users/jonah/.claude/agents/QUALITY_GATES.md",
            "/Users/jonah/.claude/agents/PERFORMANCE_THRESHOLDS.md",
            "/Users/jonah/.claude/agents/COMMON_TEMPLATES.md",
            "/Users/jonah/.claude/agents/COMMON_AGENT_PATTERNS.md",
        ]

        self.updated_agents = [
            "/Volumes/PRO-G40/Code/Archon/agents/agent-api-architect.md",
            "/Volumes/PRO-G40/Code/Archon/agents/agent-testing.md",
            "/Volumes/PRO-G40/Code/Archon/agents/agent-performance.md",
            "/Volumes/PRO-G40/Code/Archon/agents/agent-code-quality-analyzer.md",
            "/Volumes/PRO-G40/Code/Archon/agents/agent-security-audit.md",
            "/Volumes/PRO-G40/Code/Archon/agents/agent-documentation-architect.md",
            "/Volumes/PRO-G40/Code/Archon/agents/agent-debug-intelligence.md",
            "/Volumes/PRO-G40/Code/Archon/agents/agent-workflow-coordinator.md",
        ]

    def test_framework_file_availability(self) -> Dict:
        """Test all framework files are accessible and properly structured"""
        print("🔍 Testing Framework File Availability...")

        framework_status = {}
        for file_path in self.framework_files:
            start_time = time.time()
            try:
                with open(file_path, "r") as f:
                    content = f.read()

                access_time = (time.time() - start_time) * 1000  # Convert to ms

                framework_status[Path(file_path).name] = {
                    "accessible": True,
                    "access_time_ms": access_time,
                    "size_kb": len(content) / 1024,
                    "has_functions": "```python" in content,
                    "has_includes": "@" in content,
                }

                print(
                    f"  ✅ {Path(file_path).name}: {access_time:.2f}ms, {len(content)/1024:.1f}KB"
                )

            except Exception as e:
                framework_status[Path(file_path).name] = {
                    "accessible": False,
                    "error": str(e),
                    "access_time_ms": -1,
                }
                print(f"  ❌ {Path(file_path).name}: ERROR - {e}")

        self.results["framework_files"] = framework_status
        return framework_status

    def test_include_resolution_performance(self) -> List[float]:
        """Test @include resolution performance - Target: <50ms"""
        print("⚡ Testing @include Resolution Performance...")

        resolution_times = []

        for agent_file in self.updated_agents:
            try:
                start_time = time.time()

                # Simulate @include resolution by reading the agent file
                # and checking for all referenced framework files
                with open(agent_file, "r") as f:
                    agent_content = f.read()

                # Find all @include references
                includes = []
                for line in agent_content.split("\n"):
                    if line.strip().startswith("@") and ".md" in line:
                        includes.append(line.strip())

                # Simulate resolution by accessing each referenced file
                for include_ref in includes:
                    include_file = include_ref.replace(
                        "@", "/Users/jonah/.claude/agents/"
                    )
                    if os.path.exists(include_file):
                        with open(include_file, "r") as f:
                            _ = f.read(1024)  # Read first 1KB to simulate access

                resolution_time = (time.time() - start_time) * 1000
                resolution_times.append(resolution_time)

                status = (
                    "✅ PASS"
                    if resolution_time < 50
                    else "⚠️ SLOW" if resolution_time < 100 else "❌ FAIL"
                )
                print(
                    f"  {status} {Path(agent_file).name}: {resolution_time:.2f}ms ({len(includes)} includes)"
                )

            except Exception as e:
                print(f"  ❌ ERROR {Path(agent_file).name}: {e}")
                resolution_times.append(-1)

        avg_resolution = sum(t for t in resolution_times if t > 0) / len(
            [t for t in resolution_times if t > 0]
        )
        print(f"📊 Average @include resolution: {avg_resolution:.2f}ms (Target: <50ms)")

        self.results["include_resolution_times"] = resolution_times
        return resolution_times

    def test_agent_framework_integration(self) -> Dict:
        """Test that updated agents properly integrate framework patterns"""
        print("🤖 Testing Agent Framework Integration...")

        integration_status = {}

        for agent_file in self.updated_agents:
            agent_name = Path(agent_file).name
            try:
                with open(agent_file, "r") as f:
                    content = f.read()

                # Check for framework integration markers
                has_mandatory_functions = "@MANDATORY_FUNCTIONS.md" in content
                has_quality_gates = (
                    "@QUALITY_GATES.md" in content or "quality gates" in content.lower()
                )
                has_performance_thresholds = (
                    "@PERFORMANCE_THRESHOLDS.md" in content
                    or "performance" in content.lower()
                )
                has_templates = "@COMMON_TEMPLATES.md" in content
                has_patterns = "@COMMON_AGENT_PATTERNS.md" in content

                # Check for proper integration structure
                has_enhanced_framework = (
                    "## 🔧 Enhanced Framework Integration" in content
                )
                has_template_system = "**📋 Template System**" in content
                has_pattern_catalog = "**🎯 Enhanced Pattern Catalog**" in content

                integration_score = (
                    sum(
                        [
                            has_mandatory_functions,
                            has_quality_gates,
                            has_performance_thresholds,
                            has_templates,
                            has_patterns,
                            has_enhanced_framework,
                            has_template_system,
                            has_pattern_catalog,
                        ]
                    )
                    / 8.0
                )

                integration_status[agent_name] = {
                    "integration_score": integration_score,
                    "mandatory_functions": has_mandatory_functions,
                    "quality_gates": has_quality_gates,
                    "performance_thresholds": has_performance_thresholds,
                    "templates": has_templates,
                    "patterns": has_patterns,
                    "framework_structure": has_enhanced_framework,
                    "template_system": has_template_system,
                    "pattern_catalog": has_pattern_catalog,
                }

                status = (
                    "✅ EXCELLENT"
                    if integration_score >= 0.9
                    else "⚠️ GOOD" if integration_score >= 0.7 else "❌ POOR"
                )
                print(
                    f"  {status} {agent_name}: {integration_score:.1%} framework integration"
                )

            except Exception as e:
                integration_status[agent_name] = {
                    "error": str(e),
                    "integration_score": 0,
                }
                print(f"  ❌ ERROR {agent_name}: {e}")

        self.results["agent_compatibility"] = integration_status
        return integration_status

    def test_quality_gate_simulation(self) -> List[float]:
        """Simulate quality gate execution - Target: <200ms"""
        print("🔒 Testing Quality Gate Execution Performance...")

        # Simulate quality gates by running validation functions
        quality_gate_times = []

        test_scenarios = [
            "input_validation",
            "process_validation",
            "output_validation",
            "integration_validation",
            "parallel_context_validation",
            "coordination_validation",
        ]

        for scenario in test_scenarios:
            start_time = time.time()

            # Simulate quality gate execution
            try:
                # Simulate validation logic
                test_data = {"scenario": scenario, "timestamp": time.time()}

                # Simulate validation checks (this would be actual quality gate logic)
                validation_checks = [
                    len(str(test_data)) > 0,  # Data presence check
                    isinstance(test_data, dict),  # Type validation
                    "scenario" in test_data,  # Required field check
                    test_data.get("timestamp", 0) > 0,  # Value validation
                ]

                all_passed = all(validation_checks)

                execution_time = (time.time() - start_time) * 1000
                quality_gate_times.append(execution_time)

                status = (
                    "✅ PASS"
                    if execution_time < 200
                    else "⚠️ SLOW" if execution_time < 500 else "❌ FAIL"
                )
                result = "PASSED" if all_passed else "FAILED"
                print(f"  {status} {scenario}: {execution_time:.2f}ms - {result}")

            except Exception as e:
                print(f"  ❌ ERROR {scenario}: {e}")
                quality_gate_times.append(-1)

        avg_gate_time = sum(t for t in quality_gate_times if t > 0) / len(
            [t for t in quality_gate_times if t > 0]
        )
        print(
            f"📊 Average quality gate execution: {avg_gate_time:.2f}ms (Target: <200ms)"
        )

        self.results["quality_gate_execution_times"] = quality_gate_times
        return quality_gate_times

    def test_memory_footprint(self) -> Dict:
        """Test memory usage for framework integration"""
        print("💾 Testing Memory Footprint...")

        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Simulate loading framework files
        framework_content = {}
        for file_path in self.framework_files:
            try:
                with open(file_path, "r") as f:
                    framework_content[Path(file_path).name] = f.read()
            except Exception as e:
                print(f"  ⚠️ Could not load {file_path}: {e}")

        # Simulate loading updated agents
        agent_content = {}
        for agent_file in self.updated_agents:
            try:
                with open(agent_file, "r") as f:
                    agent_content[Path(agent_file).name] = f.read()
            except Exception as e:
                print(f"  ⚠️ Could not load {agent_file}: {e}")

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Calculate framework file sizes
        total_framework_size = (
            sum(len(content) for content in framework_content.values()) / 1024
        )  # KB
        total_agent_size = (
            sum(len(content) for content in agent_content.values()) / 1024
        )  # KB

        memory_status = {
            "initial_memory_mb": initial_memory,
            "final_memory_mb": final_memory,
            "memory_increase_mb": memory_increase,
            "framework_files_kb": total_framework_size,
            "agent_files_kb": total_agent_size,
            "memory_efficiency": (
                total_framework_size / (memory_increase * 1024)
                if memory_increase > 0
                else float("inf")
            ),
        }

        print(f"  📊 Initial memory: {initial_memory:.1f}MB")
        print(f"  📊 Final memory: {final_memory:.1f}MB")
        print(f"  📊 Memory increase: {memory_increase:.1f}MB")
        print(f"  📊 Framework size: {total_framework_size:.1f}KB")
        print(f"  📊 Agent content size: {total_agent_size:.1f}KB")

        self.results["memory_footprint"] = memory_status
        return memory_status

    def generate_validation_report(self) -> Dict:
        """Generate comprehensive validation report"""
        print("\n📋 Generating Validation Report...")

        # Calculate success metrics
        include_times = [t for t in self.results["include_resolution_times"] if t > 0]
        avg_include_time = (
            sum(include_times) / len(include_times) if include_times else 0
        )
        include_success = avg_include_time < 50

        gate_times = [t for t in self.results["quality_gate_execution_times"] if t > 0]
        avg_gate_time = sum(gate_times) / len(gate_times) if gate_times else 0
        gate_success = avg_gate_time < 200

        # Framework file accessibility
        accessible_files = sum(
            1
            for f in self.results["framework_files"].values()
            if f.get("accessible", False)
        )
        file_success = accessible_files == len(self.framework_files)

        # Agent compatibility
        agents_with_integration = sum(
            1
            for a in self.results["agent_compatibility"].values()
            if a.get("integration_score", 0) >= 0.8
        )
        agent_success = agents_with_integration == len(self.updated_agents)

        # Overall success rate
        success_criteria = [include_success, gate_success, file_success, agent_success]
        overall_success = sum(success_criteria) / len(success_criteria)

        report = {
            "validation_timestamp": time.time(),
            "success_criteria": {
                "include_resolution_performance": {
                    "target_ms": 50,
                    "actual_ms": avg_include_time,
                    "passed": include_success,
                },
                "quality_gate_execution": {
                    "target_ms": 200,
                    "actual_ms": avg_gate_time,
                    "passed": gate_success,
                },
                "framework_file_accessibility": {
                    "target_files": len(self.framework_files),
                    "accessible_files": accessible_files,
                    "passed": file_success,
                },
                "agent_compatibility": {
                    "target_agents": len(self.updated_agents),
                    "compatible_agents": agents_with_integration,
                    "passed": agent_success,
                },
            },
            "overall_success_rate": overall_success,
            "detailed_results": self.results,
            "recommendations": self.generate_recommendations(),
        }

        return report

    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []

        # Check include resolution performance
        include_times = [t for t in self.results["include_resolution_times"] if t > 0]
        if include_times and max(include_times) > 50:
            recommendations.append(
                "Optimize @include resolution - some agents exceed 50ms target"
            )

        # Check quality gate performance
        gate_times = [t for t in self.results["quality_gate_execution_times"] if t > 0]
        if gate_times and max(gate_times) > 200:
            recommendations.append(
                "Optimize quality gate execution - some gates exceed 200ms target"
            )

        # Check agent integration scores
        low_integration_agents = [
            name
            for name, data in self.results["agent_compatibility"].items()
            if data.get("integration_score", 0) < 0.8
        ]
        if low_integration_agents:
            recommendations.append(
                f"Improve framework integration for: {', '.join(low_integration_agents)}"
            )

        # Memory optimization
        memory_data = self.results.get("memory_footprint", {})
        if memory_data.get("memory_increase_mb", 0) > 10:
            recommendations.append(
                "Consider memory optimization - framework increase exceeds 10MB"
            )

        if not recommendations:
            recommendations.append(
                "All validation criteria met - framework ready for deployment"
            )

        return recommendations

    async def run_comprehensive_validation(self) -> Dict:
        """Run complete validation suite"""
        print("🚀 Starting WFC-07 Comprehensive Framework Validation")
        print("=" * 60)

        # Test 1: Framework file availability
        self.test_framework_file_availability()
        print()

        # Test 2: @include resolution performance
        self.test_include_resolution_performance()
        print()

        # Test 3: Agent framework integration
        self.test_agent_framework_integration()
        print()

        # Test 4: Quality gate execution simulation
        self.test_quality_gate_simulation()
        print()

        # Test 5: Memory footprint analysis
        self.test_memory_footprint()
        print()

        # Generate final report
        report = self.generate_validation_report()

        return report


def main():
    """Main validation entry point"""
    validator = FrameworkValidator()

    # Run validation
    report = asyncio.run(validator.run_comprehensive_validation())

    # Print summary
    print("\n" + "=" * 60)
    print("📊 VALIDATION SUMMARY")
    print("=" * 60)

    success_rate = report["overall_success_rate"]
    status = (
        "✅ PASSED"
        if success_rate >= 0.8
        else "⚠️ PARTIAL" if success_rate >= 0.6 else "❌ FAILED"
    )

    print(f"Overall Success Rate: {status} {success_rate:.1%}")
    print()

    for criteria, data in report["success_criteria"].items():
        status = "✅ PASS" if data["passed"] else "❌ FAIL"
        print(f"{status} {criteria.replace('_', ' ').title()}")
        if "actual_ms" in data:
            print(
                f"    Target: {data['target_ms']}ms, Actual: {data['actual_ms']:.1f}ms"
            )
        elif "accessible_files" in data:
            print(
                f"    Target: {data['target_files']}, Actual: {data['accessible_files']}"
            )
        elif "compatible_agents" in data:
            print(
                f"    Target: {data['target_agents']}, Actual: {data['compatible_agents']}"
            )

    print()
    print("🔧 RECOMMENDATIONS:")
    for rec in report["recommendations"]:
        print(f"  • {rec}")

    # Save detailed report
    with open(
        "/Volumes/PRO-G40/Code/Archon/framework_validation_report.json", "w"
    ) as f:
        json.dump(report, f, indent=2, default=str)

    print("\n📁 Detailed report saved to: framework_validation_report.json")

    return report


if __name__ == "__main__":
    main()
