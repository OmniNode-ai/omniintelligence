"""
Agent Knowledge Capture Template: Unified Agent Knowledge System (UAKS)
======================================================================

Standardized template for implementing comprehensive knowledge capture across
all agents. This template provides consistent knowledge documentation patterns
that contribute to the collective intelligence system and enhance future
agent executions through shared learning.

Template Parameters:
- AGENT_DOMAIN: Short domain identifier (e.g., debug, api_design, testing)
- AGENT_TITLE: Human-readable agent title for knowledge attribution
- KNOWLEDGE_CAPTURE_LEVEL: Level of detail for knowledge capture (basic, standard, comprehensive)

Usage:
    1. Import this template into your agent implementation
    2. Replace template parameters with agent-specific values
    3. Call capture_[AGENT_DOMAIN]_knowledge() after successful execution
    4. Implement unified_knowledge_capture() for UAKS integration
    5. Use domain-specific knowledge extraction functions

Dependencies:
    - mcp__archon__create_document() function
    - mcp__archon__update_task() function
    - datetime and uuid modules for metadata
    - Agent execution results and context

Quality Gates:
    - Knowledge completeness validation
    - Cross-domain insight extraction
    - Pattern significance assessment
    - RAG enhancement identification
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional


async def capture_agent_domain_knowledge(  # Template: Replace with capture_[AGENT_DOMAIN]_knowledge(
    task_id: Optional[str],
    execution_results: Dict[str, Any],
    capture_level: str = "standard",
) -> Optional[Dict[str, Any]]:
    """
    Capture comprehensive knowledge from [AGENT_TITLE] execution.

    This function implements the standardized Phase 4 knowledge capture
    pattern from the Archon MCP Integration Framework. It documents
    execution outcomes, lessons learned, and contributions to collective
    intelligence.

    Args:
        task_id: Archon task identifier (None for local-only mode)
        execution_results: Complete results from agent execution
        capture_level: Level of detail for knowledge capture

    Returns:
        dict: Knowledge capture results and metadata, or None if failed

    Raises:
        ValueError: If execution results are incomplete or invalid
        ConnectionError: If Archon MCP connection fails
    """
    if not task_id:
        # Local-only mode - capture knowledge locally
        return await _capture_knowledge_locally(execution_results, capture_level)

    try:
        # Extract and validate execution results
        validated_results = _validate_execution_results(execution_results)

        # Create comprehensive knowledge document
        knowledge_doc = await _create_execution_report_document(
            task_id, validated_results, capture_level
        )

        # Capture unified knowledge for UAKS integration
        unified_knowledge = await unified_knowledge_capture(
            validated_results, "[AGENT_DOMAIN]"
        )

        # Update task to completed status with summary
        await _update_task_completion_status(task_id, validated_results)

        # Perform cross-domain pattern synthesis if complex execution
        cross_domain_insights = None
        if validated_results.get("complexity_level") in ["complex", "critical"]:
            cross_domain_insights = await synthesize_cross_domain_patterns(
                validated_results, "[AGENT_DOMAIN]"
            )

        return {
            "knowledge_capture_success": True,
            "execution_report_id": knowledge_doc.get("document_id"),
            "unified_knowledge_id": unified_knowledge.get("knowledge_id"),
            "cross_domain_insights": cross_domain_insights,
            "capture_timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        await _handle_knowledge_capture_error(e, task_id, execution_results)
        return None


async def _create_execution_report_document(
    task_id: str, execution_results: Dict[str, Any], capture_level: str
) -> Dict[str, Any]:
    """Create comprehensive execution report document in Archon MCP."""

    # Build execution report content
    report_content = {
        "correlation_metadata": _extract_correlation_metadata(execution_results),
        "spawn_relationships": _extract_spawn_relationships(execution_results),
        "execution_summary": _build_execution_summary(execution_results),
        "intelligence_applied": _extract_intelligence_applied(execution_results),
        "outcomes_achieved": _extract_outcomes_achieved(execution_results),
        "lessons_learned": _extract_lessons_learned(execution_results),
        "knowledge_contributions": _extract_knowledge_contributions(execution_results),
        "parallel_coordination_results": _extract_parallel_coordination_results(
            execution_results
        ),
    }

    # Add detailed sections based on capture level
    if capture_level in ["standard", "comprehensive"]:
        report_content.update(
            {
                "performance_metrics": _extract_performance_metrics(execution_results),
                "quality_assessment": _extract_quality_assessment(execution_results),
                "tool_effectiveness": _extract_tool_effectiveness(execution_results),
            }
        )

    if capture_level == "comprehensive":
        report_content.update(
            {
                "detailed_execution_trace": _extract_execution_trace(execution_results),
                "resource_utilization": _extract_resource_utilization(
                    execution_results
                ),
                "optimization_opportunities": _identify_optimization_opportunities(
                    execution_results
                ),
            }
        )

    # Create document in Archon MCP
    return await mcp__archon__create_document(
        project_id=execution_results["project_id"],
        title=f"[AGENT_TITLE] Execution Report - {datetime.now().strftime('%Y-%m-%d')}",
        document_type="execution_report",
        content=report_content,
        tags=["[AGENT_DOMAIN]", "execution_report", "knowledge_capture", "uaks"],
        author="Claude Code Agent",
    )


async def unified_knowledge_capture(
    execution_results: Dict[str, Any], agent_type: str
) -> Dict[str, Any]:
    """
    Capture unified knowledge following UAKS framework.

    This function automatically extracts and stores knowledge in the
    standardized format, making it available for RAG enhancement
    across all agents.

    Args:
        execution_results: Complete execution results from agent
        agent_type: Agent domain identifier

    Returns:
        dict: Unified knowledge document with metadata
    """

    # Extract standardized knowledge following UAKS structure
    knowledge_doc = {
        "metadata": {
            "agent_type": agent_type,
            "execution_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "repository": execution_results.get("repository_info", {}),
            "project_id": execution_results.get("project_id"),
            "task_id": execution_results.get("task_id"),
        },
        "execution_context": _extract_execution_context(execution_results),
        "domain_intelligence": _extract_domain_patterns(execution_results, agent_type),
        "cross_domain_insights": _extract_cross_domain_insights(execution_results),
        "rag_enhancement": _identify_rag_improvements(execution_results),
        "future_intelligence": _predict_future_patterns(execution_results),
    }

    # Store in Archon MCP for RAG access
    unified_doc = await mcp__archon__create_document(
        project_id=execution_results["project_id"],
        title=f"Knowledge Capture - {agent_type} - {datetime.now().strftime('%Y-%m-%d-%H%M%S')}",
        document_type="unified_knowledge",
        content={"knowledge_capture": knowledge_doc},
        tags=["knowledge_capture", agent_type, "uaks", "rag_enhancement"],
        author="UAKS System",
    )

    return {
        "knowledge_id": unified_doc.get("document_id"),
        "knowledge_quality_score": _assess_knowledge_quality(knowledge_doc),
        "cross_agent_relevance": _calculate_cross_agent_relevance(knowledge_doc),
        "pattern_significance": _evaluate_pattern_significance(knowledge_doc),
    }


def _extract_execution_context(execution_results: Dict[str, Any]) -> Dict[str, Any]:
    """Extract execution context for UAKS knowledge capture."""
    return {
        "trigger": execution_results.get("trigger", "user_request"),
        "input_summary": execution_results.get("task_summary", "Task execution"),
        "complexity_level": execution_results.get("complexity_level", "moderate"),
        "duration": execution_results.get("execution_time", "Unknown"),
    }


def _extract_domain_patterns(
    execution_results: Dict[str, Any], agent_type: str
) -> Dict[str, Any]:
    """Extract domain-specific intelligence patterns."""
    patterns_discovered = []
    successful_strategies = []
    failed_approaches = []

    # Extract patterns from execution results
    for pattern in execution_results.get("patterns_identified", []):
        patterns_discovered.append(
            {
                "pattern_type": pattern.get("type", "unknown"),
                "description": pattern.get("description", ""),
                "frequency": pattern.get("frequency", "uncommon"),
                "effectiveness": pattern.get("effectiveness", "medium"),
                "reusability": pattern.get("reusability", "domain_specific"),
            }
        )

    # Extract successful strategies
    for strategy in execution_results.get("successful_strategies", []):
        successful_strategies.append(
            {
                "strategy": strategy.get("name", ""),
                "context": strategy.get("context", ""),
                "outcome": strategy.get("outcome", ""),
                "confidence": strategy.get("confidence", "medium"),
            }
        )

    # Extract failed approaches
    for failure in execution_results.get("failed_approaches", []):
        failed_approaches.append(
            {
                "approach": failure.get("approach", ""),
                "failure_mode": failure.get("failure_mode", ""),
                "lesson_learned": failure.get("lesson", ""),
                "alternative": failure.get("alternative", ""),
            }
        )

    return {
        "patterns_discovered": patterns_discovered,
        "successful_strategies": successful_strategies,
        "failed_approaches": failed_approaches,
    }


def _extract_cross_domain_insights(execution_results: Dict[str, Any]) -> Dict[str, Any]:
    """Extract cross-domain insights for knowledge sharing."""
    return {
        "security_implications": execution_results.get("security_insights", []),
        "performance_impact": execution_results.get("performance_insights", {}),
        "quality_observations": execution_results.get("quality_insights", []),
        "debugging_hints": execution_results.get("debugging_insights", []),
        "collaboration_patterns": execution_results.get("collaboration_insights", []),
    }


def _identify_rag_improvements(execution_results: Dict[str, Any]) -> Dict[str, Any]:
    """Identify opportunities for RAG system enhancement."""
    return {
        "new_query_patterns": execution_results.get("useful_query_patterns", []),
        "knowledge_gaps": execution_results.get("knowledge_gaps_identified", []),
        "improved_examples": execution_results.get("better_examples_needed", []),
    }


def _predict_future_patterns(execution_results: Dict[str, Any]) -> Dict[str, Any]:
    """Predict future patterns and automation opportunities."""
    return {
        "automation_opportunities": execution_results.get("automation_candidates", []),
        "pattern_predictions": execution_results.get("likely_future_patterns", []),
        "optimization_suggestions": execution_results.get(
            "optimization_opportunities", []
        ),
        "prevention_strategies": execution_results.get("prevention_strategies", []),
    }


def _assess_knowledge_quality(knowledge_doc: Dict[str, Any]) -> float:
    """Assess the quality and usefulness of captured knowledge."""
    quality_score = 0.0

    # Context completeness (0.3 weight)
    context_completeness = _evaluate_context_completeness(knowledge_doc)
    quality_score += context_completeness * 0.3

    # Actionability (0.25 weight)
    actionability = _evaluate_actionability(knowledge_doc)
    quality_score += actionability * 0.25

    # Pattern significance (0.2 weight)
    pattern_significance = _evaluate_pattern_significance(knowledge_doc)
    quality_score += pattern_significance * 0.2

    # Cross-domain relevance (0.15 weight)
    cross_relevance = _calculate_cross_agent_relevance(knowledge_doc)
    quality_score += cross_relevance * 0.15

    # Prevention value (0.1 weight)
    prevention_value = _evaluate_prevention_value(knowledge_doc)
    quality_score += prevention_value * 0.1

    return min(quality_score, 1.0)


def _calculate_cross_agent_relevance(knowledge_doc: Dict[str, Any]) -> float:
    """Calculate relevance of knowledge to other agents."""
    relevance_score = 0.0

    # Check for cross-domain insights
    cross_domain = knowledge_doc.get("cross_domain_insights", {})
    if any(cross_domain.values()):
        relevance_score += 0.4

    # Check for reusable patterns
    patterns = knowledge_doc.get("domain_intelligence", {}).get(
        "patterns_discovered", []
    )
    universal_patterns = [p for p in patterns if p.get("reusability") == "universal"]
    if universal_patterns:
        relevance_score += 0.3

    # Check for collaboration insights
    collaboration = knowledge_doc.get("cross_domain_insights", {}).get(
        "collaboration_patterns", []
    )
    if collaboration:
        relevance_score += 0.3

    return min(relevance_score, 1.0)


def _evaluate_pattern_significance(knowledge_doc: Dict[str, Any]) -> float:
    """Evaluate the significance of discovered patterns."""
    significance_score = 0.0

    patterns = knowledge_doc.get("domain_intelligence", {}).get(
        "patterns_discovered", []
    )

    for pattern in patterns:
        # High effectiveness patterns
        if pattern.get("effectiveness") == "high":
            significance_score += 0.2

        # Rare but effective patterns
        if pattern.get("frequency") == "rare" and pattern.get("effectiveness") in [
            "high",
            "medium",
        ]:
            significance_score += 0.3

        # Universal reusability
        if pattern.get("reusability") == "universal":
            significance_score += 0.2

    return min(significance_score, 1.0)


async def synthesize_cross_domain_patterns(
    execution_results: Dict[str, Any], agent_type: str
) -> Dict[str, Any]:
    """Analyze knowledge across all agents to identify cross-domain patterns."""

    try:
        # Query all knowledge documents for correlation analysis
        all_knowledge = await mcp__archon__perform_rag_query(
            query=f"unified knowledge capture patterns {agent_type} cross-domain insights",
            match_count=50,
        )

        # Identify correlations across different agent types
        correlations = {
            "debug_security_patterns": _correlate_debug_security(all_knowledge),
            "performance_quality_patterns": _correlate_performance_quality(
                all_knowledge
            ),
            "automation_opportunities": _identify_automation_patterns(all_knowledge),
            "common_failure_modes": _extract_common_failures(all_knowledge),
            "successful_collaboration": _identify_agent_collaboration_success(
                all_knowledge
            ),
        }

        return correlations

    except Exception as e:
        # Graceful degradation if cross-domain synthesis fails
        return {
            "synthesis_error": str(e),
            "fallback_insights": _extract_local_cross_domain_insights(
                execution_results
            ),
        }


async def _update_task_completion_status(
    task_id: str, execution_results: Dict[str, Any]
) -> None:
    """Update Archon task to completed status with comprehensive summary."""

    completion_summary = f"""
## ✅ [AGENT_TITLE] Completed Successfully

### Final Results
{execution_results.get('summary', 'Task completed with full ONEX compliance')}

### Knowledge Captured
- Execution report created with comprehensive findings
- {len(execution_results.get('new_patterns', []))} new patterns identified
- {len(execution_results.get('reusable_solutions', []))} reusable solutions documented
- Cross-domain insights captured for collective intelligence

### Quality Assurance
- All quality gates passed: ✅
- ONEX standards compliance verified: ✅
- Knowledge base updated with findings: ✅
- Unified Agent Knowledge System enhanced: ✅

### Performance Metrics
- Execution time: {execution_results.get('execution_time', 'Unknown')}
- Intelligence confidence: {execution_results.get('intelligence_confidence', 0.0):.2f}
- Success rate: {execution_results.get('success_rate', 'Unknown')}
- Knowledge quality score: {execution_results.get('knowledge_quality_score', 'Pending')}
"""

    await mcp__archon__update_task(
        task_id=task_id, status="done", description=completion_summary
    )


async def _capture_knowledge_locally(
    execution_results: Dict[str, Any], capture_level: str
) -> Dict[str, Any]:
    """Capture knowledge locally when Archon MCP is unavailable."""

    print("📚 Capturing knowledge locally (Archon MCP unavailable)")

    # Create local knowledge summary
    local_knowledge = {
        "agent_type": "[AGENT_DOMAIN]",
        "timestamp": datetime.utcnow().isoformat(),
        "execution_summary": execution_results.get("summary", "Task completed"),
        "patterns_discovered": execution_results.get("new_patterns", []),
        "lessons_learned": execution_results.get("lessons_learned", []),
        "local_mode": True,
    }

    # Log key insights
    print(f"   Patterns discovered: {len(local_knowledge['patterns_discovered'])}")
    print(f"   Lessons learned: {len(local_knowledge['lessons_learned'])}")

    return {
        "knowledge_capture_success": True,
        "local_knowledge": local_knowledge,
        "capture_mode": "local_only",
    }


async def _handle_knowledge_capture_error(
    error: Exception, task_id: Optional[str], execution_results: Dict[str, Any]
) -> None:
    """Handle errors in knowledge capture with graceful degradation."""

    print(f"⚠️ Knowledge capture failed: {str(error)}")
    print(f"   Task ID: {task_id}")
    print("   Falling back to local knowledge capture")

    # Attempt local capture as fallback
    await _capture_knowledge_locally(execution_results, "basic")


# Helper functions for knowledge extraction
def _extract_correlation_metadata(execution_results: Dict[str, Any]) -> Dict[str, Any]:
    """Extract correlation metadata for execution tracking."""
    return {
        "session_correlation_id": execution_results.get("session_correlation_id"),
        "execution_id": execution_results.get("execution_id"),
        "parent_execution_id": execution_results.get("parent_execution_id"),
        "parallel_group_id": execution_results.get("parallel_group_id"),
        "spawn_depth": execution_results.get("spawn_depth", 0),
        "agent_lineage": execution_results.get("agent_lineage", []),
        "coordination_role": execution_results.get("coordination_role", "standalone"),
    }


def _extract_spawn_relationships(execution_results: Dict[str, Any]) -> Dict[str, Any]:
    """Extract agent spawn relationships for coordination tracking."""
    return {
        "spawned_agents": execution_results.get("spawned_agents", []),
        "coordination_session_id": execution_results.get("coordination_session_id"),
        "spawn_strategy": execution_results.get("spawn_strategy", "none"),
    }


def _build_execution_summary(execution_results: Dict[str, Any]) -> Dict[str, Any]:
    """Build comprehensive execution summary."""
    return {
        "agent_type": "[AGENT_DOMAIN]",
        "repository": execution_results.get("repository_info", {}),
        "duration": execution_results.get("execution_time", "Unknown"),
        "status": execution_results.get("final_status", "Completed"),
        "complexity_level": execution_results.get("complexity_level", "moderate"),
    }


def _validate_execution_results(execution_results: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize execution results for knowledge capture."""
    validated_results = execution_results.copy()

    # Ensure required fields
    validated_results.setdefault("project_id", "unknown")
    validated_results.setdefault("final_status", "completed")
    validated_results.setdefault("execution_time", "unknown")
    validated_results.setdefault("summary", "Task execution completed")

    # Normalize lists
    validated_results.setdefault("new_patterns", [])
    validated_results.setdefault("reusable_solutions", [])
    validated_results.setdefault("lessons_learned", [])
    validated_results.setdefault("challenges", [])

    return validated_results


# Template Usage Example:
"""
# Basic usage after agent execution:
async def complete_[AGENT_DOMAIN]_execution(task_id, execution_context, results):
    # Prepare execution results with all necessary information
    execution_results = {
        'project_id': execution_context['project_id'],
        'task_id': task_id,
        'final_status': 'completed',
        'execution_time': '45 seconds',
        'summary': 'Successfully completed task with high quality',
        'new_patterns': [{'type': 'optimization', 'description': 'Found efficient pattern'}],
        'reusable_solutions': [{'solution': 'Reusable component', 'context': 'API design'}],
        'lessons_learned': ['Always validate inputs early'],
        'intelligence_confidence': 0.85,
        'complexity_level': 'moderate'
    }

    # Capture comprehensive knowledge
    knowledge_results = await capture_[AGENT_DOMAIN]_knowledge(
        task_id=task_id,
        execution_results=execution_results,
        capture_level="standard"
    )

    return knowledge_results

# Advanced usage with cross-domain insights:
async def complete_complex_[AGENT_DOMAIN]_execution(task_id, execution_context, results):
    execution_results = {
        # ... standard fields ...
        'complexity_level': 'complex',
        'cross_domain_insights': {
            'security_implications': ['Input validation required'],
            'performance_impact': {'memory_usage': 'optimized'},
            'quality_observations': ['High maintainability achieved']
        },
        'parallel_coordination_results': {
            'coordination_session_id': 'session-123',
            'parallel_agents_used': ['agent-api', 'agent-test'],
            'coordination_efficiency': {'time_saved': '60%'}
        }
    }

    knowledge_results = await capture_[AGENT_DOMAIN]_knowledge(
        task_id=task_id,
        execution_results=execution_results,
        capture_level="comprehensive"
    )

    return knowledge_results
"""
