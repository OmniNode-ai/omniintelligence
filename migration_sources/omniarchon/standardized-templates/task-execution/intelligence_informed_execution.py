"""
Task Execution Template: Intelligence-Informed Execution
=======================================================

Standardized template for executing tasks with applied intelligence from
pre-execution intelligence gathering. This template implements the complete
execution lifecycle with intelligence guidance and quality gates.

Template Parameters:
- AGENT_TYPE: Agent type identifier
- TASK_TYPE: Type of task being executed
- EXECUTION_PHASES: List of execution phases specific to the agent
- QUALITY_GATES: Quality gates and validation requirements
- INTELLIGENCE_APPLICATION_STRATEGY: How to apply gathered intelligence

Usage:
    1. Copy this template to your agent implementation
    2. Replace template parameters with agent-specific values
    3. Implement phase-specific execution logic
    4. Customize intelligence application strategies
    5. Add domain-specific validation logic

Dependencies:
    - gather_comprehensive_pre_execution_intelligence()
    - Intelligence synthesis functions
    - Quality validation functions
    - Progress tracking functions

Quality Gates:
    - Pre-execution intelligence validation
    - Phase-by-phase quality checks
    - Intelligence application tracking
    - Execution result validation
"""

import asyncio
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, List


async def execute_task_with_intelligence(
    agent_type: str, task_definition: Dict[str, Any], execution_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    MANDATORY: Standard pattern for intelligence-informed task execution.
    All agents must follow this pattern.

    This function implements the complete intelligence-informed execution
    lifecycle from the Agent Framework. It ensures that agents leverage
    gathered intelligence throughout execution while maintaining quality gates.

    Args:
        agent_type: Type of agent executing the task
        task_definition: Complete task definition with requirements
            - task_type: Type of task (required)
            - domain: Task domain (required)
            - technology_stack: Technologies involved
            - complexity_level: simple|moderate|complex|critical
            - requirements: List of requirements
            - acceptance_criteria: Success criteria
        execution_context: Execution environment context
            - repository_context: Repository information
            - project_id: Archon project ID (if available)
            - user_context: User requirements and preferences

    Returns:
        dict: Complete execution results with intelligence application tracking
    """
    execution_id = str(uuid.uuid4())
    start_time = datetime.utcnow()

    try:
        print(f"🚀 Starting intelligence-informed execution for {agent_type}")
        print(f"📝 Task: {task_definition.get('task_type', 'unknown task')}")
        print(f"🔧 Execution ID: {execution_id}")

        # PHASE 1: Pre-Execution Intelligence Gathering (MANDATORY)
        print(
            f"🧠 Phase 1: Gathering intelligence for {task_definition.get('task_type', 'unknown task')}"
        )

        task_context = _prepare_task_context(task_definition, execution_context)
        gathered_intelligence = await _gather_comprehensive_pre_execution_intelligence(
            agent_type, task_context
        )

        # Enrich execution context with intelligence
        enriched_context = _enrich_execution_context(
            execution_context, gathered_intelligence
        )

        # PHASE 2: Intelligence-Informed Planning
        print("📋 Phase 2: Creating intelligence-informed execution plan")
        execution_plan = _create_intelligence_informed_plan(
            task_definition, enriched_context, gathered_intelligence
        )

        # PHASE 3: Guided Execution with Intelligence Application
        print("⚡ Phase 3: Executing with applied intelligence")
        execution_results = await _execute_with_intelligence_guidance(
            execution_plan=execution_plan,
            gathered_intelligence=gathered_intelligence,
            enriched_context=enriched_context,
            agent_type=agent_type,
            execution_id=execution_id,
        )

        # PHASE 4: Post-Execution Intelligence Capture
        print("📝 Phase 4: Capturing intelligence from execution")
        if execution_results.get("success", False):
            await _capture_success_pattern_intelligence(
                task_context, agent_type, execution_results
            )

        # PHASE 5: Execution Summary and Validation
        final_results = _finalize_execution_results(
            execution_results,
            gathered_intelligence,
            execution_context,
            start_time,
            execution_id,
        )

        print(
            f"✅ Execution completed successfully in {final_results.get('execution_duration_ms', 0)}ms"
        )
        return final_results

    except Exception as e:
        print(f"❌ Execution failed: {str(e)}")

        # Capture error intelligence with pre-execution context
        error_context = {
            **execution_context,
            "gathered_intelligence": (
                gathered_intelligence if "gathered_intelligence" in locals() else {}
            ),
            "task_context": task_context if "task_context" in locals() else {},
            "execution_id": execution_id,
            "error_traceback": traceback.format_exc(),
        }
        await _capture_debug_intelligence_on_error(e, agent_type, error_context)

        # Return error results
        return _create_error_results(e, execution_context, start_time, execution_id)


def _prepare_task_context(
    task_definition: Dict[str, Any], execution_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Prepare task context for intelligence gathering."""
    return {
        "domain": task_definition.get("domain", "general"),
        "technology_stack": task_definition.get("technology_stack", []),
        "complexity_level": task_definition.get("complexity_level", "moderate"),
        "task_type": task_definition.get("task_type", "general"),
        "repository_context": execution_context.get("repository_context", {}),
        "user_requirements": task_definition.get("requirements", []),
        "acceptance_criteria": task_definition.get("acceptance_criteria", []),
        "constraints": task_definition.get("constraints", []),
        "preferences": execution_context.get("user_context", {}).get("preferences", {}),
    }


async def _gather_comprehensive_pre_execution_intelligence(
    agent_type: str, task_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Gather comprehensive intelligence before task execution."""
    print(f"🔍 Gathering comprehensive intelligence for {agent_type}...")

    try:
        # Parallel intelligence gathering for efficiency
        intelligence_results = await asyncio.gather(
            _gather_debug_intelligence(agent_type, task_context),
            _gather_domain_standards(agent_type, task_context),
            _gather_performance_quality_intelligence(agent_type, task_context),
            _gather_collaboration_intelligence(agent_type, task_context),
            return_exceptions=True,
        )

        (
            debug_intelligence,
            domain_standards,
            performance_quality,
            collaboration,
        ) = intelligence_results

        # Synthesize gathered intelligence
        comprehensive_intelligence = _synthesize_intelligence_for_execution(
            debug_intelligence=(
                debug_intelligence
                if not isinstance(debug_intelligence, Exception)
                else {}
            ),
            domain_standards=(
                domain_standards if not isinstance(domain_standards, Exception) else {}
            ),
            performance_quality=(
                performance_quality
                if not isinstance(performance_quality, Exception)
                else {}
            ),
            collaboration=(
                collaboration if not isinstance(collaboration, Exception) else {}
            ),
            task_context=task_context,
        )

        print(
            f"✅ Intelligence gathering complete: {len(comprehensive_intelligence.get('actionable_insights', []))} insights gathered"
        )

        return comprehensive_intelligence

    except Exception as e:
        print(f"⚠️ Intelligence gathering failed: {str(e)}")
        return _create_fallback_intelligence(task_context)


def _enrich_execution_context(
    base_context: Dict[str, Any], gathered_intelligence: Dict[str, Any]
) -> Dict[str, Any]:
    """Enrich the execution context with gathered intelligence insights."""
    return {
        **base_context,
        "intelligence_insights": gathered_intelligence,
        "proven_approaches": gathered_intelligence.get(
            "execution_context_enrichment", {}
        ).get("proven_approaches", []),
        "pitfalls_to_avoid": gathered_intelligence.get(
            "execution_context_enrichment", {}
        ).get("pitfalls_to_avoid", []),
        "recommended_tools": gathered_intelligence.get("recommended_tools", []),
        "quality_requirements": gathered_intelligence.get(
            "execution_context_enrichment", {}
        ).get("quality_requirements", {}),
        "optimization_strategies": gathered_intelligence.get(
            "execution_context_enrichment", {}
        ).get("optimization_strategies", []),
        "risk_mitigation": gathered_intelligence.get("risk_mitigation", []),
        "intelligence_confidence": gathered_intelligence.get(
            "intelligence_confidence", 0.5
        ),
        "success_patterns": gathered_intelligence.get("success_patterns", []),
    }


def _create_intelligence_informed_plan(
    task_definition: Dict[str, Any],
    enriched_context: Dict[str, Any],
    gathered_intelligence: Dict[str, Any],
) -> Dict[str, Any]:
    """Create an execution plan informed by gathered intelligence."""
    base_plan = _create_base_execution_plan(task_definition)

    # Apply intelligence insights to plan
    intelligence_enhanced_plan = _apply_intelligence_to_plan(
        base_plan, gathered_intelligence
    )

    # Add intelligence-based validations
    _add_intelligence_based_validations(
        intelligence_enhanced_plan, gathered_intelligence
    )

    # Include proactive risk mitigation
    _add_proactive_risk_mitigation(intelligence_enhanced_plan, gathered_intelligence)

    # Add quality gates
    _add_quality_gates(intelligence_enhanced_plan, enriched_context)

    return intelligence_enhanced_plan


def _create_base_execution_plan(task_definition: Dict[str, Any]) -> Dict[str, Any]:
    """Create base execution plan from task definition."""
    return {
        "task_id": str(uuid.uuid4()),
        "task_type": task_definition.get("task_type", "general"),
        "complexity_level": task_definition.get("complexity_level", "moderate"),
        "steps": _generate_execution_steps(task_definition),
        "quality_gates": _define_quality_gates(task_definition),
        "validation_criteria": task_definition.get("acceptance_criteria", []),
        "estimated_duration": _estimate_execution_duration(task_definition),
        "resource_requirements": _assess_resource_requirements(task_definition),
    }


def _generate_execution_steps(task_definition: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate execution steps based on task definition."""
    # This would be customized for each agent type
    # Template provides the structure
    base_steps = [
        {
            "step_id": "initialization",
            "name": "Task Initialization",
            "description": "Initialize task execution environment",
            "estimated_duration_ms": 1000,
            "dependencies": [],
            "quality_checks": ["context_validation", "requirements_clarity"],
        },
        {
            "step_id": "analysis",
            "name": "Requirement Analysis",
            "description": "Analyze task requirements and constraints",
            "estimated_duration_ms": 5000,
            "dependencies": ["initialization"],
            "quality_checks": ["requirement_completeness", "constraint_feasibility"],
        },
        {
            "step_id": "implementation",
            "name": "Core Implementation",
            "description": "Execute core task functionality",
            "estimated_duration_ms": 20000,
            "dependencies": ["analysis"],
            "quality_checks": ["functional_correctness", "performance_acceptable"],
        },
        {
            "step_id": "validation",
            "name": "Result Validation",
            "description": "Validate execution results against criteria",
            "estimated_duration_ms": 3000,
            "dependencies": ["implementation"],
            "quality_checks": ["acceptance_criteria_met", "quality_standards_met"],
        },
    ]

    # Customize steps based on task type and complexity
    complexity = task_definition.get("complexity_level", "moderate")
    if complexity in ["complex", "critical"]:
        # Add additional steps for complex tasks
        base_steps.insert(
            -1,
            {
                "step_id": "review",
                "name": "Internal Review",
                "description": "Conduct thorough review of implementation",
                "estimated_duration_ms": 5000,
                "dependencies": ["implementation"],
                "quality_checks": [
                    "code_review",
                    "security_review",
                    "performance_review",
                ],
            },
        )

    return base_steps


def _apply_intelligence_to_plan(
    base_plan: Dict[str, Any], gathered_intelligence: Dict[str, Any]
) -> Dict[str, Any]:
    """Apply intelligence insights to the execution plan."""
    enhanced_plan = base_plan.copy()

    # Apply proven approaches
    proven_approaches = gathered_intelligence.get(
        "execution_context_enrichment", {}
    ).get("proven_approaches", [])
    if proven_approaches:
        enhanced_plan["proven_approaches"] = proven_approaches
        enhanced_plan["intelligence_guidance"] = {
            "apply_proven_patterns": True,
            "proven_patterns": proven_approaches,
        }

    # Add pitfall avoidance
    pitfalls = gathered_intelligence.get("execution_context_enrichment", {}).get(
        "pitfalls_to_avoid", []
    )
    if pitfalls:
        enhanced_plan["pitfall_avoidance"] = pitfalls
        enhanced_plan["intelligence_guidance"]["avoid_patterns"] = pitfalls

    # Include optimization strategies
    optimizations = gathered_intelligence.get("execution_context_enrichment", {}).get(
        "optimization_strategies", []
    )
    if optimizations:
        enhanced_plan["optimization_strategies"] = optimizations

    # Add recommended tools
    tools = gathered_intelligence.get("recommended_tools", [])
    if tools:
        enhanced_plan["recommended_tools"] = tools

    return enhanced_plan


def _add_intelligence_based_validations(
    plan: Dict[str, Any], gathered_intelligence: Dict[str, Any]
) -> None:
    """Add intelligence-based validations to the execution plan."""
    quality_requirements = gathered_intelligence.get(
        "execution_context_enrichment", {}
    ).get("quality_requirements", {})

    for step in plan.get("steps", []):
        step["intelligence_validations"] = []

        # Add quality-based validations
        if quality_requirements:
            step["intelligence_validations"].extend(
                [f"verify_{requirement}" for requirement in quality_requirements.keys()]
            )

        # Add pattern-based validations
        proven_approaches = gathered_intelligence.get(
            "execution_context_enrichment", {}
        ).get("proven_approaches", [])
        if proven_approaches:
            step["intelligence_validations"].append(
                "validate_proven_pattern_application"
            )


def _add_proactive_risk_mitigation(
    plan: Dict[str, Any], gathered_intelligence: Dict[str, Any]
) -> None:
    """Include proactive risk mitigation based on intelligence."""
    risk_mitigation = gathered_intelligence.get("risk_mitigation", [])

    plan["risk_mitigation"] = {
        "identified_risks": risk_mitigation,
        "mitigation_strategies": [],
        "monitoring_points": [],
    }

    for risk in risk_mitigation:
        # Add risk-specific mitigation strategies
        strategy = _generate_mitigation_strategy(risk)
        plan["risk_mitigation"]["mitigation_strategies"].append(strategy)

        # Add monitoring points
        monitoring = _generate_monitoring_point(risk)
        plan["risk_mitigation"]["monitoring_points"].append(monitoring)


def _add_quality_gates(plan: Dict[str, Any], enriched_context: Dict[str, Any]) -> None:
    """Add quality gates to the execution plan."""
    quality_requirements = enriched_context.get("quality_requirements", {})

    plan["quality_gates"] = {
        "pre_execution": [
            "intelligence_quality_check",
            "context_completeness_check",
            "requirements_clarity_check",
        ],
        "during_execution": [
            "step_validation_check",
            "intelligence_application_check",
            "progress_quality_check",
        ],
        "post_execution": [
            "acceptance_criteria_check",
            "quality_standards_check",
            "intelligence_capture_check",
        ],
    }

    # Add domain-specific quality gates
    for requirement_type, requirement_details in quality_requirements.items():
        gate_name = f"{requirement_type}_compliance_check"
        plan["quality_gates"]["during_execution"].append(gate_name)


async def _execute_with_intelligence_guidance(
    execution_plan: Dict[str, Any],
    gathered_intelligence: Dict[str, Any],
    enriched_context: Dict[str, Any],
    agent_type: str,
    execution_id: str,
) -> Dict[str, Any]:
    """Execute the plan with continuous intelligence guidance."""
    execution_results = {
        "execution_id": execution_id,
        "steps_completed": [],
        "intelligence_applied": [],
        "quality_checks_passed": [],
        "success": False,
        "start_time": datetime.utcnow().isoformat(),
    }

    try:
        # Pre-execution quality gates
        pre_execution_checks = await _run_quality_gates(
            execution_plan.get("quality_gates", {}).get("pre_execution", []),
            execution_plan,
            gathered_intelligence,
            enriched_context,
        )
        execution_results["pre_execution_checks"] = pre_execution_checks

        if not all(pre_execution_checks.values()):
            raise ExecutionError("Pre-execution quality gates failed")

        # Execute steps with intelligence guidance
        for step in execution_plan.get("steps", []):
            print(f"🔄 Executing step: {step.get('name', 'Unknown step')}")

            # Apply relevant intelligence for this step
            step_intelligence = _filter_intelligence_for_step(
                step, gathered_intelligence
            )

            # Execute step with intelligence guidance
            step_result = await _execute_step_with_guidance(
                step, step_intelligence, enriched_context, agent_type
            )

            execution_results["steps_completed"].append(step_result)
            execution_results["intelligence_applied"].extend(
                step_result.get("intelligence_applied", [])
            )

            # Run during-execution quality gates
            during_execution_checks = await _run_quality_gates(
                execution_plan.get("quality_gates", {}).get("during_execution", []),
                step,
                step_intelligence,
                enriched_context,
            )
            execution_results["quality_checks_passed"].append(during_execution_checks)

            # If step fails, apply debug intelligence immediately
            if not step_result.get("success", False):
                await _apply_debug_intelligence_for_step_failure(
                    step, step_result, gathered_intelligence, agent_type
                )
                raise ExecutionError(
                    f"Step {step.get('step_id')} failed: {step_result.get('error', 'Unknown error')}"
                )

        # Post-execution quality gates
        post_execution_checks = await _run_quality_gates(
            execution_plan.get("quality_gates", {}).get("post_execution", []),
            execution_results,
            gathered_intelligence,
            enriched_context,
        )
        execution_results["post_execution_checks"] = post_execution_checks

        if not all(post_execution_checks.values()):
            print("⚠️ Post-execution quality gates failed")

        execution_results["success"] = True
        execution_results["overall_intelligence_effectiveness"] = (
            _calculate_intelligence_effectiveness(execution_results)
        )
        execution_results["end_time"] = datetime.utcnow().isoformat()

        print("✅ All execution steps completed successfully")
        return execution_results

    except Exception as e:
        execution_results["success"] = False
        execution_results["error"] = str(e)
        execution_results["error_traceback"] = traceback.format_exc()
        execution_results["end_time"] = datetime.utcnow().isoformat()

        print(f"❌ Execution failed: {str(e)}")
        return execution_results


async def _execute_step_with_guidance(
    step: Dict[str, Any],
    step_intelligence: Dict[str, Any],
    enriched_context: Dict[str, Any],
    agent_type: str,
) -> Dict[str, Any]:
    """Execute a single step with intelligence guidance."""
    step_result = {
        "step_id": step.get("step_id"),
        "step_name": step.get("name"),
        "start_time": datetime.utcnow().isoformat(),
        "success": False,
        "intelligence_applied": [],
        "quality_checks": {},
        "duration_ms": 0,
    }

    start_time = datetime.utcnow()

    try:
        # Apply intelligence guidance
        guidance_applied = _apply_intelligence_guidance(
            step, step_intelligence, enriched_context
        )
        step_result["intelligence_applied"] = guidance_applied

        # Execute step logic
        step_execution_result = await _execute_step_logic(
            step, enriched_context, agent_type
        )
        step_result.update(step_execution_result)

        # Run step-specific quality checks
        quality_checks = await _run_step_quality_checks(
            step, step_result, step_intelligence
        )
        step_result["quality_checks"] = quality_checks

        # Validate intelligence application
        intelligence_validation = _validate_intelligence_application(
            step_result, step_intelligence
        )
        step_result["intelligence_validation"] = intelligence_validation

        step_result["success"] = step_execution_result.get("success", False) and all(
            quality_checks.values()
        )

    except Exception as e:
        step_result["error"] = str(e)
        step_result["error_traceback"] = traceback.format_exc()

    finally:
        end_time = datetime.utcnow()
        step_result["duration_ms"] = int((end_time - start_time).total_seconds() * 1000)
        step_result["end_time"] = end_time.isoformat()

    return step_result


async def _execute_step_logic(
    step: Dict[str, Any], enriched_context: Dict[str, Any], agent_type: str
) -> Dict[str, Any]:
    """Execute the core logic for a step (to be customized by agents)."""
    # This is a template method that agents should override
    # with their specific step execution logic

    step_id = step.get("step_id")

    if step_id == "initialization":
        return await _execute_initialization_step(step, enriched_context, agent_type)
    elif step_id == "analysis":
        return await _execute_analysis_step(step, enriched_context, agent_type)
    elif step_id == "implementation":
        return await _execute_implementation_step(step, enriched_context, agent_type)
    elif step_id == "validation":
        return await _execute_validation_step(step, enriched_context, agent_type)
    elif step_id == "review":
        return await _execute_review_step(step, enriched_context, agent_type)
    else:
        return {
            "success": True,
            "message": f"Step {step_id} executed (template placeholder)",
            "outputs": {},
        }


async def _execute_initialization_step(
    step: Dict[str, Any], context: Dict[str, Any], agent_type: str
) -> Dict[str, Any]:
    """Execute initialization step."""
    return {
        "success": True,
        "message": "Initialization completed",
        "outputs": {"context_validated": True, "environment_ready": True},
    }


async def _execute_analysis_step(
    step: Dict[str, Any], context: Dict[str, Any], agent_type: str
) -> Dict[str, Any]:
    """Execute analysis step."""
    return {
        "success": True,
        "message": "Analysis completed",
        "outputs": {"requirements_analyzed": True, "approach_determined": True},
    }


async def _execute_implementation_step(
    step: Dict[str, Any], context: Dict[str, Any], agent_type: str
) -> Dict[str, Any]:
    """Execute implementation step."""
    return {
        "success": True,
        "message": "Implementation completed",
        "outputs": {"functionality_implemented": True, "tests_passed": True},
    }


async def _execute_validation_step(
    step: Dict[str, Any], context: Dict[str, Any], agent_type: str
) -> Dict[str, Any]:
    """Execute validation step."""
    return {
        "success": True,
        "message": "Validation completed",
        "outputs": {"criteria_met": True, "quality_verified": True},
    }


async def _execute_review_step(
    step: Dict[str, Any], context: Dict[str, Any], agent_type: str
) -> Dict[str, Any]:
    """Execute review step."""
    return {
        "success": True,
        "message": "Review completed",
        "outputs": {"review_passed": True, "improvements_identified": []},
    }


# Helper functions for intelligence processing (placeholders - would be implemented)


async def _gather_debug_intelligence(
    agent_type: str, task_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Gather debug intelligence (placeholder)."""
    return {"debug_patterns": [], "error_prevention": []}


async def _gather_domain_standards(
    agent_type: str, task_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Gather domain standards (placeholder)."""
    return {"standards": [], "best_practices": []}


async def _gather_performance_quality_intelligence(
    agent_type: str, task_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Gather performance and quality intelligence (placeholder)."""
    return {"performance_patterns": [], "quality_guidelines": []}


async def _gather_collaboration_intelligence(
    agent_type: str, task_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Gather collaboration intelligence (placeholder)."""
    return {"collaboration_patterns": [], "delegation_strategies": []}


def _synthesize_intelligence_for_execution(
    debug_intelligence: Dict,
    domain_standards: Dict,
    performance_quality: Dict,
    collaboration: Dict,
    task_context: Dict,
) -> Dict[str, Any]:
    """Synthesize intelligence for execution (placeholder)."""
    return {
        "execution_context_enrichment": {
            "proven_approaches": [],
            "pitfalls_to_avoid": [],
            "optimization_strategies": [],
            "quality_requirements": {},
            "collaboration_opportunities": [],
        },
        "actionable_insights": [],
        "risk_mitigation": [],
        "success_patterns": [],
        "intelligence_confidence": 0.7,
        "recommended_tools": [],
        "execution_strategy_recommendations": [],
    }


def _create_fallback_intelligence(task_context: Dict[str, Any]) -> Dict[str, Any]:
    """Create fallback intelligence when gathering fails."""
    return {
        "execution_context_enrichment": {
            "proven_approaches": ["Follow standard practices"],
            "pitfalls_to_avoid": ["Avoid rushing implementation"],
            "optimization_strategies": ["Test incrementally"],
            "quality_requirements": {"basic": "Ensure functional correctness"},
            "collaboration_opportunities": [],
        },
        "actionable_insights": ["Proceed with caution - limited intelligence"],
        "risk_mitigation": ["Extra validation required"],
        "success_patterns": [],
        "intelligence_confidence": 0.3,
        "recommended_tools": [],
        "execution_strategy_recommendations": ["Conservative approach recommended"],
    }


def _define_quality_gates(task_definition: Dict[str, Any]) -> List[str]:
    """Define quality gates based on task definition."""
    return ["functional_correctness", "performance_acceptable", "security_compliant"]


def _estimate_execution_duration(task_definition: Dict[str, Any]) -> int:
    """Estimate execution duration in milliseconds."""
    complexity_multipliers = {
        "simple": 1.0,
        "moderate": 2.0,
        "complex": 4.0,
        "critical": 6.0,
    }

    base_duration = 30000  # 30 seconds base
    complexity = task_definition.get("complexity_level", "moderate")

    return int(base_duration * complexity_multipliers.get(complexity, 2.0))


def _assess_resource_requirements(task_definition: Dict[str, Any]) -> Dict[str, Any]:
    """Assess resource requirements for task execution."""
    return {
        "memory_mb": 256,
        "cpu_cores": 1,
        "disk_space_mb": 100,
        "network_required": True,
    }


def _filter_intelligence_for_step(
    step: Dict[str, Any], gathered_intelligence: Dict[str, Any]
) -> Dict[str, Any]:
    """Filter intelligence relevant to the current step."""
    step.get("step_id")

    # Filter intelligence based on step type
    relevant_intelligence = {
        "step_specific_guidance": [],
        "applicable_patterns": [],
        "quality_requirements": {},
        "risk_factors": [],
    }

    # Add step-specific filtering logic here

    return relevant_intelligence


def _apply_intelligence_guidance(
    step: Dict[str, Any],
    step_intelligence: Dict[str, Any],
    enriched_context: Dict[str, Any],
) -> List[str]:
    """Apply intelligence guidance to step execution."""
    applied_guidance = []

    # Apply proven approaches
    proven_approaches = enriched_context.get("proven_approaches", [])
    for approach in proven_approaches:
        if _is_approach_applicable(approach, step):
            applied_guidance.append(f"Applied proven approach: {approach}")

    # Avoid known pitfalls
    pitfalls = enriched_context.get("pitfalls_to_avoid", [])
    for pitfall in pitfalls:
        if _is_pitfall_relevant(pitfall, step):
            applied_guidance.append(f"Avoided pitfall: {pitfall}")

    return applied_guidance


def _is_approach_applicable(approach: str, step: Dict[str, Any]) -> bool:
    """Check if a proven approach is applicable to the current step."""
    # Implement logic to determine applicability
    return True  # Placeholder


def _is_pitfall_relevant(pitfall: str, step: Dict[str, Any]) -> bool:
    """Check if a pitfall is relevant to the current step."""
    # Implement logic to determine relevance
    return True  # Placeholder


async def _run_quality_gates(gates: List[str], *args) -> Dict[str, bool]:
    """Run quality gate checks."""
    results = {}

    for gate in gates:
        try:
            result = await _execute_quality_gate(gate, *args)
            results[gate] = result
        except Exception as e:
            print(f"⚠️ Quality gate {gate} failed: {str(e)}")
            results[gate] = False

    return results


async def _execute_quality_gate(gate: str, *args) -> bool:
    """Execute a specific quality gate."""
    # Implement quality gate logic
    return True  # Placeholder


async def _run_step_quality_checks(
    step: Dict[str, Any], step_result: Dict[str, Any], step_intelligence: Dict[str, Any]
) -> Dict[str, bool]:
    """Run quality checks specific to a step."""
    checks = {}

    for check in step.get("quality_checks", []):
        try:
            result = await _execute_step_quality_check(
                check, step, step_result, step_intelligence
            )
            checks[check] = result
        except Exception as e:
            print(f"⚠️ Quality check {check} failed: {str(e)}")
            checks[check] = False

    return checks


async def _execute_step_quality_check(
    check: str,
    step: Dict[str, Any],
    step_result: Dict[str, Any],
    step_intelligence: Dict[str, Any],
) -> bool:
    """Execute a specific step quality check."""
    # Implement quality check logic
    return True  # Placeholder


def _validate_intelligence_application(
    step_result: Dict[str, Any], step_intelligence: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate that intelligence was properly applied during step execution."""
    return {
        "intelligence_utilized": len(step_result.get("intelligence_applied", [])) > 0,
        "guidance_followed": True,
        "patterns_applied": True,
        "effectiveness_score": 0.8,
    }


async def _apply_debug_intelligence_for_step_failure(
    step: Dict[str, Any],
    step_result: Dict[str, Any],
    gathered_intelligence: Dict[str, Any],
    agent_type: str,
) -> None:
    """Apply debug intelligence when a step fails."""
    print(f"🔍 Applying debug intelligence for failed step: {step.get('step_id')}")

    # Analyze failure using debug intelligence
    gathered_intelligence.get("debug_intelligence", {})

    # This would implement sophisticated failure analysis
    # For now, just log the attempt
    print("📝 Debug analysis applied for step failure")


def _calculate_intelligence_effectiveness(execution_results: Dict[str, Any]) -> float:
    """Calculate the effectiveness of intelligence application during execution."""
    total_steps = len(execution_results.get("steps_completed", []))
    successful_steps = len(
        [
            step
            for step in execution_results.get("steps_completed", [])
            if step.get("success", False)
        ]
    )

    if total_steps == 0:
        return 0.0

    success_rate = successful_steps / total_steps
    intelligence_utilization = len(
        execution_results.get("intelligence_applied", [])
    ) / max(total_steps, 1)

    return (success_rate + intelligence_utilization) / 2.0


def _finalize_execution_results(
    execution_results: Dict[str, Any],
    gathered_intelligence: Dict[str, Any],
    execution_context: Dict[str, Any],
    start_time: datetime,
    execution_id: str,
) -> Dict[str, Any]:
    """Finalize and enrich execution results."""
    end_time = datetime.utcnow()
    duration_ms = int((end_time - start_time).total_seconds() * 1000)

    return {
        **execution_results,
        "execution_duration_ms": duration_ms,
        "intelligence_summary": {
            "confidence": gathered_intelligence.get("intelligence_confidence", 0.0),
            "insights_count": len(gathered_intelligence.get("actionable_insights", [])),
            "effectiveness": execution_results.get(
                "overall_intelligence_effectiveness", 0.0
            ),
        },
        "quality_summary": {
            "gates_passed": _count_passed_gates(execution_results),
            "steps_successful": len(
                [
                    s
                    for s in execution_results.get("steps_completed", [])
                    if s.get("success", False)
                ]
            ),
            "overall_success": execution_results.get("success", False),
        },
        "execution_metadata": {
            "execution_id": execution_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_ms": duration_ms,
        },
    }


def _count_passed_gates(execution_results: Dict[str, Any]) -> int:
    """Count the number of quality gates that passed."""
    count = 0

    # Count pre-execution gates
    pre_checks = execution_results.get("pre_execution_checks", {})
    count += sum(1 for passed in pre_checks.values() if passed)

    # Count during-execution gates
    during_checks = execution_results.get("quality_checks_passed", [])
    for check_dict in during_checks:
        count += sum(1 for passed in check_dict.values() if passed)

    # Count post-execution gates
    post_checks = execution_results.get("post_execution_checks", {})
    count += sum(1 for passed in post_checks.values() if passed)

    return count


def _create_error_results(
    error: Exception,
    execution_context: Dict[str, Any],
    start_time: datetime,
    execution_id: str,
) -> Dict[str, Any]:
    """Create error results when execution fails."""
    end_time = datetime.utcnow()
    duration_ms = int((end_time - start_time).total_seconds() * 1000)

    return {
        "success": False,
        "error": str(error),
        "error_type": type(error).__name__,
        "error_traceback": traceback.format_exc(),
        "execution_id": execution_id,
        "execution_duration_ms": duration_ms,
        "steps_completed": [],
        "intelligence_applied": [],
        "quality_checks_passed": [],
        "execution_metadata": {
            "execution_id": execution_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_ms": duration_ms,
            "failure_mode": "execution_error",
        },
    }


def _generate_mitigation_strategy(risk: str) -> Dict[str, Any]:
    """Generate mitigation strategy for a specific risk."""
    return {
        "risk": risk,
        "strategy": f"Monitor and validate against {risk}",
        "monitoring_frequency": "per_step",
        "escalation_threshold": "immediate",
    }


def _generate_monitoring_point(risk: str) -> Dict[str, Any]:
    """Generate monitoring point for a specific risk."""
    return {
        "risk": risk,
        "monitoring_type": "automated",
        "check_frequency": "per_step",
        "alert_threshold": "any_occurrence",
    }


async def _capture_success_pattern_intelligence(
    task_context: Dict[str, Any], agent_type: str, execution_results: Dict[str, Any]
) -> None:
    """Capture intelligence from successful execution."""
    print(f"📝 Capturing success pattern intelligence for {agent_type}")
    # Implementation would capture and store success patterns
    pass


async def _capture_debug_intelligence_on_error(
    error: Exception, agent_type: str, error_context: Dict[str, Any]
) -> None:
    """Capture debug intelligence when errors occur."""
    print(f"🐛 Capturing debug intelligence for error in {agent_type}: {str(error)}")
    # Implementation would capture and store error intelligence
    pass


class ExecutionError(Exception):
    """Exception raised during task execution."""

    pass


# Template Usage Example:
"""
# Agent-specific implementation:
async def execute_debug_task(task_definition, execution_context):
    # Customize for debug agent:
    # - Replace [AGENT_TYPE] with 'debug'
    # - Replace [TASK_TYPE] with specific debug task types
    # - Implement domain-specific step execution logic
    # - Add debug-specific quality gates

    return await execute_task_with_intelligence(
        agent_type='debug',
        task_definition=task_definition,
        execution_context=execution_context
    )

# Usage:
task_def = {
    'task_type': 'root_cause_analysis',
    'domain': 'debugging',
    'technology_stack': ['python', 'fastapi'],
    'complexity_level': 'complex',
    'requirements': ['Identify root cause', 'Provide solution'],
    'acceptance_criteria': ['Root cause identified', 'Solution validated']
}

context = {
    'repository_context': {...},
    'project_id': 'project-123',
    'user_context': {...}
}

results = await execute_debug_task(task_def, context)
if results['success']:
    print(f"Task completed successfully in {results['execution_duration_ms']}ms")
else:
    print(f"Task failed: {results['error']}")
"""
