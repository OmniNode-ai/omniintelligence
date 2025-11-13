#!/usr/bin/env python3
"""
WFC-07 Remaining Agent Compatibility Assessment
Test remaining 39 agents for framework compatibility and integration gaps
"""

from pathlib import Path


class RemainingAgentCompatibilityTest:
    """Test remaining agents for framework compatibility"""

    def __init__(self):
        self.updated_agents = {
            "agent-api-architect.md",
            "agent-testing.md",
            "agent-performance.md",
            "agent-code-quality-analyzer.md",
            "agent-security-audit.md",
            "agent-documentation-architect.md",
            "agent-debug-intelligence.md",
            "agent-workflow-coordinator.md",
        }

        # Get all agent files
        agent_dir = Path("/Volumes/PRO-G40/Code/Archon/agents")
        self.all_agents = list(agent_dir.glob("agent-*.md"))

        # Filter to get remaining agents
        self.remaining_agents = [
            agent for agent in self.all_agents if agent.name not in self.updated_agents
        ]

        print(f"Total agents: {len(self.all_agents)}")
        print(f"Updated agents: {len(self.updated_agents)}")
        print(f"Remaining agents to test: {len(self.remaining_agents)}")

    def assess_agent_framework_readiness(self, agent_file):
        """Assess how ready an agent is for framework integration"""
        try:
            with open(agent_file, "r") as f:
                content = f.read()

            # Check current structure patterns
            has_archon_integration = (
                "@ARCHON_INTEGRATION.md" in content
                or "Integration Framework" in content
            )
            has_common_workflows = any(
                pattern in content
                for pattern in [
                    "@COMMON_WORKFLOW.md",
                    "@COMMON_RAG_INTELLIGENCE.md",
                    "@COMMON_ONEX_STANDARDS.md",
                ]
            )

            # Check for existing framework-compatible patterns
            has_bfros = "BFROS" in content
            has_anti_yolo = "Anti-YOLO" in content or "YOLO" in content
            has_intelligence_gathering = any(
                pattern in content.lower()
                for pattern in ["intelligence", "rag", "gather", "research"]
            )
            has_quality_gates = any(
                pattern in content.lower()
                for pattern in ["quality", "validation", "compliance", "gate"]
            )
            has_performance_awareness = any(
                pattern in content.lower()
                for pattern in ["performance", "optimization", "efficiency", "metrics"]
            )

            # Check agent architecture patterns
            has_clean_agent_principles = any(
                pattern in content
                for pattern in [
                    "single responsibility",
                    "context inheritance",
                    "systematic",
                ]
            )
            has_delegation_patterns = any(
                pattern in content.lower()
                for pattern in ["delegation", "handoff", "coordinate"]
            )

            # Calculate readiness scores
            framework_readiness = (
                sum(
                    [
                        has_archon_integration
                        * 2,  # Already integrated (double weight)
                        has_common_workflows * 2,  # Has common workflow patterns
                        has_bfros,
                        has_anti_yolo,
                        has_intelligence_gathering,
                        has_quality_gates,
                        has_performance_awareness,
                        has_clean_agent_principles,
                        has_delegation_patterns,
                    ]
                )
                / 11.0
            )  # Max possible score

            # Estimate integration effort
            if has_archon_integration:
                integration_effort = "NONE - Already integrated"
            elif framework_readiness >= 0.7:
                integration_effort = "LOW - 15-30 minutes"
            elif framework_readiness >= 0.5:
                integration_effort = "MEDIUM - 30-60 minutes"
            elif framework_readiness >= 0.3:
                integration_effort = "HIGH - 1-2 hours"
            else:
                integration_effort = "VERY HIGH - 2+ hours"

            return {
                "readiness_score": framework_readiness,
                "integration_effort": integration_effort,
                "has_archon_integration": has_archon_integration,
                "has_common_workflows": has_common_workflows,
                "has_intelligence_patterns": has_intelligence_gathering,
                "has_quality_patterns": has_quality_gates,
                "has_performance_patterns": has_performance_awareness,
                "assessment_details": {
                    "bfros": has_bfros,
                    "anti_yolo": has_anti_yolo,
                    "intelligence": has_intelligence_gathering,
                    "quality": has_quality_gates,
                    "performance": has_performance_awareness,
                    "clean_principles": has_clean_agent_principles,
                    "delegation": has_delegation_patterns,
                },
            }

        except Exception as e:
            return {
                "readiness_score": 0,
                "integration_effort": f"ERROR: {e}",
                "error": str(e),
            }

    def run_compatibility_assessment(self):
        """Run compatibility assessment on all remaining agents"""
        print("\n🔍 REMAINING AGENT COMPATIBILITY ASSESSMENT")
        print("=" * 60)

        results = {}
        total_agents = len(self.remaining_agents)
        high_readiness_agents = 0
        medium_readiness_agents = 0
        low_readiness_agents = 0

        for i, agent_file in enumerate(self.remaining_agents, 1):
            agent_name = agent_file.name
            print(f"[{i:2d}/{total_agents}] Testing {agent_name}...")

            assessment = self.assess_agent_framework_readiness(agent_file)
            results[agent_name] = assessment

            readiness = assessment.get("readiness_score", 0)
            effort = assessment.get("integration_effort", "UNKNOWN")

            if readiness >= 0.7:
                high_readiness_agents += 1
                status = "✅ HIGH"
            elif readiness >= 0.5:
                medium_readiness_agents += 1
                status = "⚠️ MEDIUM"
            elif readiness >= 0.3:
                low_readiness_agents += 1
                status = "❌ LOW"
            else:
                status = "🚫 VERY LOW"

            print(f"    {status} readiness: {readiness:.1%} - {effort}")

        # Summary statistics
        print("\n📊 COMPATIBILITY ASSESSMENT SUMMARY")
        print("=" * 60)

        needs_significant_work = low_readiness_agents + (
            total_agents
            - high_readiness_agents
            - medium_readiness_agents
            - low_readiness_agents
        )

        print(
            f"High Readiness (≥70%):    {high_readiness_agents:2d} agents - Quick integration possible"
        )
        print(
            f"Medium Readiness (≥50%):  {medium_readiness_agents:2d} agents - Moderate work needed"
        )
        print(
            f"Low Readiness (<50%):     {needs_significant_work:2d} agents - Significant work needed"
        )
        print(f"Total Remaining:          {total_agents:2d} agents")

        # Calculate completion estimates
        quick_time = high_readiness_agents * 0.375  # 22.5 minutes average
        medium_time = medium_readiness_agents * 0.75  # 45 minutes average
        high_time = needs_significant_work * 1.5  # 1.5 hours average

        total_estimated_hours = quick_time + medium_time + high_time

        print("\n⏱️ INTEGRATION TIME ESTIMATES")
        print(
            f"Quick integration:     {quick_time:.1f} hours ({high_readiness_agents} agents)"
        )
        print(
            f"Medium integration:    {medium_time:.1f} hours ({medium_readiness_agents} agents)"
        )
        print(
            f"High effort integration: {high_time:.1f} hours ({needs_significant_work} agents)"
        )
        print(f"TOTAL ESTIMATED TIME:  {total_estimated_hours:.1f} hours")

        # Identify top candidates for next batch
        print("\n🎯 TOP CANDIDATES FOR NEXT INTEGRATION BATCH")
        sorted_agents = sorted(
            [(name, data) for name, data in results.items()],
            key=lambda x: x[1].get("readiness_score", 0),
            reverse=True,
        )

        for i, (agent_name, data) in enumerate(sorted_agents[:10], 1):
            readiness = data.get("readiness_score", 0)
            effort = data.get("integration_effort", "UNKNOWN")
            print(f"  {i:2d}. {agent_name:<35} ({readiness:.1%}) - {effort}")

        return {
            "total_remaining": total_agents,
            "high_readiness": high_readiness_agents,
            "medium_readiness": medium_readiness_agents,
            "low_readiness": needs_significant_work,
            "estimated_total_hours": total_estimated_hours,
            "detailed_results": results,
            "top_candidates": sorted_agents[:10],
        }


def main():
    """Main assessment entry point"""
    tester = RemainingAgentCompatibilityTest()
    results = tester.run_compatibility_assessment()

    # Calculate current ecosystem status
    total_agents = len(tester.all_agents)
    updated_agents = len(tester.updated_agents)
    remaining_agents = results["total_remaining"]

    current_compatibility = updated_agents / total_agents

    print("\n🌐 ECOSYSTEM COMPATIBILITY STATUS")
    print("=" * 60)
    print(
        f"Current Compatibility:     {current_compatibility:.1%} ({updated_agents}/{total_agents} agents)"
    )
    print(
        f"Remaining Work:           {100 - current_compatibility*100:.1f}% ({remaining_agents} agents)"
    )
    print("Target: 100% Compatibility (38/38 agents - assuming some are deprecated)")

    # Recommendations
    print("\n🎯 RECOMMENDATIONS FOR 100% COMPATIBILITY")
    print("=" * 60)

    if results["high_readiness"] >= 10:
        print(
            f"• IMMEDIATE: Integrate {min(10, results['high_readiness'])} high-readiness agents (~{results['high_readiness'] * 0.375:.1f} hours)"
        )

    if results["medium_readiness"] > 0:
        print(
            f"• NEXT PHASE: Integrate {results['medium_readiness']} medium-readiness agents (~{results['medium_readiness'] * 0.75:.1f} hours)"
        )

    if results["low_readiness"] > 0:
        print(
            f"• FINAL PHASE: Integrate {results['low_readiness']} low-readiness agents (~{results['low_readiness'] * 1.5:.1f} hours)"
        )

    print(
        f"• TOTAL PROJECT: {results['estimated_total_hours']:.1f} hours to achieve 100% compatibility"
    )

    return results


if __name__ == "__main__":
    main()
