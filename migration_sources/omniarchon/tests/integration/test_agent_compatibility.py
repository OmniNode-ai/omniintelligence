#!/usr/bin/env python3
"""
Agent Compatibility Testing Script for WS6: Agent Reference Updates
Tests all agents for backwards compatibility, new capabilities access, and performance.
"""

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class CompatibilityTestResult:
    """Results from compatibility testing."""

    agent_path: str
    backwards_compatible: bool
    new_capabilities_access: bool
    include_resolution_time: float
    mandatory_functions_available: bool
    template_system_functional: bool
    pattern_catalog_accessible: bool
    validation_errors: List[str]


class AgentCompatibilityValidator:
    """Validate agent compatibility with new framework capabilities."""

    def __init__(self):
        self.agents_dir = Path("/Volumes/PRO-G40/Code/Archon/agents")
        self.configs_dir = Path("/Volumes/PRO-G40/Code/Archon/agents/configs")

        # Required @include references for backwards compatibility
        self.required_includes = [
            "@COMMON_WORKFLOW.md",
            "@COMMON_RAG_INTELLIGENCE.md",
            "@COMMON_ONEX_STANDARDS.md",
            "@COMMON_AGENT_PATTERNS.md",
            "@COMMON_CONTEXT_INHERITANCE.md",
            "@COMMON_CONTEXT_LIFECYCLE.md",
        ]

        # New framework capabilities
        self.new_capabilities = [
            "@MANDATORY_FUNCTIONS.md",
            "@COMMON_TEMPLATES.md",
            "@FRAMEWORK_QUALITY_ASSESSMENT.md",
        ]

    def validate_all_agents(self) -> Dict[str, Any]:
        """Validate all agents for compatibility and performance."""
        agent_files = list(self.agents_dir.glob("agent-*.md"))

        validation_results = {
            "total_agents": len(agent_files),
            "agents_passed": 0,
            "agents_failed": 0,
            "average_resolution_time": 0.0,
            "max_resolution_time": 0.0,
            "performance_target_met": True,
            "detailed_results": {},
            "summary": {
                "backwards_compatibility_rate": 0.0,
                "new_capabilities_rate": 0.0,
                "performance_compliance_rate": 0.0,
            },
        }

        total_resolution_time = 0.0
        backwards_compatible_count = 0
        new_capabilities_count = 0
        performance_compliant_count = 0

        for agent_file in agent_files:
            agent_name = agent_file.name
            try:
                result = self.validate_agent(str(agent_file))
                validation_results["detailed_results"][agent_name] = result

                # Update counters
                total_resolution_time += result.include_resolution_time

                if result.backwards_compatible:
                    backwards_compatible_count += 1

                if result.new_capabilities_access:
                    new_capabilities_count += 1

                if result.include_resolution_time <= 50.0:
                    performance_compliant_count += 1

                # Overall pass/fail
                if result.backwards_compatible and result.new_capabilities_access:
                    validation_results["agents_passed"] += 1
                else:
                    validation_results["agents_failed"] += 1

            except Exception as e:
                validation_results["agents_failed"] += 1
                validation_results["detailed_results"][agent_name] = (
                    CompatibilityTestResult(
                        agent_path=str(agent_file),
                        backwards_compatible=False,
                        new_capabilities_access=False,
                        include_resolution_time=0.0,
                        mandatory_functions_available=False,
                        template_system_functional=False,
                        pattern_catalog_accessible=False,
                        validation_errors=[f"Validation exception: {str(e)}"],
                    )
                )

        # Calculate summary metrics
        total_agents = validation_results["total_agents"]
        validation_results["average_resolution_time"] = (
            total_resolution_time / total_agents
        )
        validation_results["max_resolution_time"] = max(
            result.include_resolution_time
            for result in validation_results["detailed_results"].values()
        )
        validation_results["performance_target_met"] = (
            validation_results["max_resolution_time"] <= 50.0
        )

        validation_results["summary"] = {
            "backwards_compatibility_rate": backwards_compatible_count / total_agents,
            "new_capabilities_rate": new_capabilities_count / total_agents,
            "performance_compliance_rate": performance_compliant_count / total_agents,
        }

        return validation_results

    def validate_agent(self, agent_path: str) -> CompatibilityTestResult:
        """
        Validate agent compatibility and functionality.

        Returns:
            CompatibilityTestResult: Comprehensive validation results
        """
        result = CompatibilityTestResult(
            agent_path=agent_path,
            backwards_compatible=True,
            new_capabilities_access=True,
            include_resolution_time=0.0,
            mandatory_functions_available=True,
            template_system_functional=True,
            pattern_catalog_accessible=True,
            validation_errors=[],
        )

        try:
            # Read agent content
            with open(agent_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Test @include resolution time (<50ms requirement)
            start_time = time.time()
            self._resolve_includes(content)
            resolution_time = (time.time() - start_time) * 1000
            result.include_resolution_time = resolution_time

            if resolution_time > 50:
                result.validation_errors.append(
                    f"Include resolution time {resolution_time:.1f}ms exceeds 50ms target"
                )

            # Test backwards compatibility (existing @includes preserved OR @AGENT_COMMON_HEADER.md present)
            if "@AGENT_COMMON_HEADER.md" in content:
                # Agent uses enhanced header which includes all required functionality
                pass  # Backwards compatible through header
            else:
                # Check for individual includes
                for include_ref in self.required_includes:
                    if include_ref not in content:
                        result.backwards_compatible = False
                        result.validation_errors.append(
                            f"Missing required include: {include_ref}"
                        )

            # Test new capabilities accessibility
            capabilities_found = 0
            for capability in self.new_capabilities:
                if capability in content:
                    capabilities_found += 1

            # For updated agents, we should find at least the mandatory functions and templates
            if "@MANDATORY_FUNCTIONS.md" not in content:
                # Check if this is via AGENT_COMMON_HEADER.md enhancement
                if (
                    "@AGENT_COMMON_HEADER.md" in content
                    or "Enhanced Framework Integration" in content
                ):
                    # Agent has new capabilities through the framework
                    pass
                else:
                    result.new_capabilities_access = False
                    result.validation_errors.append(
                        "Mandatory functions not accessible"
                    )

            # Test mandatory functions availability
            if not self._check_mandatory_functions(content):
                result.mandatory_functions_available = False
                result.validation_errors.append("Mandatory functions not accessible")

            # Test template system functionality
            if not self._check_template_system(content):
                result.template_system_functional = False
                result.validation_errors.append("Template system not functional")

            # Test pattern catalog accessibility
            if not self._check_pattern_catalog(content):
                result.pattern_catalog_accessible = False
                result.validation_errors.append("Pattern catalog not accessible")

            # Overall capability assessment
            result.new_capabilities_access = all(
                [
                    result.mandatory_functions_available,
                    result.template_system_functional,
                    result.pattern_catalog_accessible,
                ]
            )

        except Exception as e:
            result.backwards_compatible = False
            result.new_capabilities_access = False
            result.validation_errors.append(f"Validation exception: {str(e)}")

        return result

    def _resolve_includes(self, content: str) -> List[str]:
        """Simulate @include resolution for performance testing."""
        # Find all @include references
        include_pattern = r"@([A-Z_]+\.md)"
        includes = re.findall(include_pattern, content)

        # Simulate resolution time (actual resolution would be faster)
        resolved = []
        for include in includes:
            # Simulate file access
            include_path = self.agents_dir.parent / ".claude" / "agents" / include
            if include_path.exists():
                resolved.append(include)
            time.sleep(0.001)  # Simulate minimal file access time

        return resolved

    def _check_mandatory_functions(self, content: str) -> bool:
        """Check if mandatory functions are accessible."""
        # Check for direct reference or framework integration
        mandatory_indicators = [
            "@MANDATORY_FUNCTIONS.md",
            "gather_comprehensive_pre_execution_intelligence",
            "execute_task_with_intelligence",
            "capture_debug_intelligence_on_error",
            "Enhanced Framework Integration",
        ]

        return any(indicator in content for indicator in mandatory_indicators)

    def _check_template_system(self, content: str) -> bool:
        """Check if template system is functional."""
        template_indicators = [
            "@COMMON_TEMPLATES.md",
            "orchestrated_intelligence_research",
            "unified_knowledge_capture",
            "Template System",
            "Configuration:",
        ]

        return any(indicator in content for indicator in template_indicators)

    def _check_pattern_catalog(self, content: str) -> bool:
        """Check if pattern catalog is accessible."""
        pattern_indicators = [
            "@COMMON_AGENT_PATTERNS.md",
            "Enhanced Pattern Catalog",
            "CDP-001",
            "QAP-001",
            "IGP-001",  # Sample pattern references
            "applicable patterns",
        ]

        return any(indicator in content for indicator in pattern_indicators)


class PerformanceBenchmark:
    """Benchmark framework performance."""

    def __init__(self):
        self.agents_dir = Path("/Volumes/PRO-G40/Code/Archon/agents")

    def benchmark_include_resolution(self) -> Dict[str, float]:
        """Benchmark @include resolution performance (<50ms target)."""
        agent_files = list(self.agents_dir.glob("agent-*.md"))
        resolution_times = []

        for agent_path in agent_files:
            with open(agent_path, "r", encoding="utf-8") as f:
                content = f.read()

            start = time.time()
            self._resolve_all_includes(content)
            duration = (time.time() - start) * 1000
            resolution_times.append(duration)

        return {
            "avg_resolution_time_ms": sum(resolution_times) / len(resolution_times),
            "max_resolution_time_ms": max(resolution_times),
            "min_resolution_time_ms": min(resolution_times),
            "target_met": max(resolution_times) < 50.0,
            "agents_tested": len(agent_files),
        }

    def _resolve_all_includes(self, content: str):
        """Simulate complete @include resolution."""
        include_pattern = r"@([A-Z_]+\.md)"
        includes = re.findall(include_pattern, content)

        for include in includes:
            time.sleep(0.001)  # Simulate file access


def main():
    """Main function to run compatibility tests."""
    print("🧪 WS6: Agent Reference Updates - Compatibility Testing")
    print("=" * 60)

    # Run comprehensive validation
    validator = AgentCompatibilityValidator()
    validation_results = validator.validate_all_agents()

    print("📊 Validation Results:")
    print(f"   Total agents tested: {validation_results['total_agents']}")
    print(f"   Agents passed: {validation_results['agents_passed']}")
    print(f"   Agents failed: {validation_results['agents_failed']}")
    print(
        f"   Overall success rate: {validation_results['agents_passed']/validation_results['total_agents']*100:.1f}%"
    )

    print("\n⚡ Performance Metrics:")
    print(
        f"   Average @include resolution: {validation_results['average_resolution_time']:.1f}ms"
    )
    print(
        f"   Maximum @include resolution: {validation_results['max_resolution_time']:.1f}ms"
    )
    print(
        f"   Performance target (<50ms): {'✅ MET' if validation_results['performance_target_met'] else '❌ FAILED'}"
    )

    print("\n📈 Compatibility Summary:")
    summary = validation_results["summary"]
    print(
        f"   Backwards compatibility: {summary['backwards_compatibility_rate']*100:.1f}%"
    )
    print(f"   New capabilities access: {summary['new_capabilities_rate']*100:.1f}%")
    print(
        f"   Performance compliance: {summary['performance_compliance_rate']*100:.1f}%"
    )

    # Show detailed results for any failures
    failed_agents = [
        agent
        for agent, result in validation_results["detailed_results"].items()
        if not (result.backwards_compatible and result.new_capabilities_access)
    ]

    if failed_agents:
        print(f"\n❌ Failed Agents ({len(failed_agents)}):")
        for agent in failed_agents[:10]:  # Show first 10 failures
            result = validation_results["detailed_results"][agent]
            print(f"   - {agent}:")
            for error in result.validation_errors:
                print(f"     • {error}")

    # Success criteria
    success_criteria = {
        "100% backwards compatibility": summary["backwards_compatibility_rate"] >= 1.0,
        "New capabilities accessible": summary["new_capabilities_rate"]
        >= 0.7,  # 70% threshold for progressive rollout
        "Performance target met": validation_results["performance_target_met"],
    }

    print("\n🎯 Success Criteria:")
    for criteria, met in success_criteria.items():
        status = "✅ MET" if met else "❌ FAILED"
        print(f"   {criteria}: {status}")

    if all(success_criteria.values()):
        print("\n✅ ALL SUCCESS CRITERIA MET!")
        print("🚀 Ready to proceed with remaining agent updates")
        return True
    else:
        print("\n⚠️  Some success criteria not met - review required")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
