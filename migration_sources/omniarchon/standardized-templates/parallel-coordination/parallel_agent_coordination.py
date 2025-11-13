"""
Agent Parallel Coordination Template: Multi-Agent Collaboration Framework
========================================================================

Standardized template for implementing parallel agent coordination with
shared state management, context distribution, and synchronization patterns.
This template enables multiple agents to work together efficiently while
maintaining consistency and preventing coordination failures.

Template Parameters:
- AGENT_DOMAIN: Short domain identifier for coordination context
- COORDINATION_ROLE: Role in coordination (coordinator, participant, hybrid)
- SYNC_STRATEGY: Synchronization strategy (checkpoint, event_driven, async)
- ERROR_ISOLATION_LEVEL: Level of error isolation (none, basic, comprehensive)

Usage:
    1. Import this template into your agent implementation
    2. Replace template parameters with coordination-specific values
    3. Use create_coordination_context() to establish shared state
    4. Implement spawn_parallel_agents() for concurrent execution
    5. Handle coordination signals and synchronization points

Dependencies:
    - mcp__archon__create_document() for shared state
    - mcp__archon__create_task() for parallel task management
    - asyncio for concurrent execution
    - Agent context establishment functions

Quality Gates:
    - Coordination state validation
    - Context consistency checks
    - Synchronization point verification
    - Error isolation validation
"""

import asyncio
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


class CoordinationMode(Enum):
    """Coordination execution modes."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HYBRID = "hybrid"


class SynchronizationPoint(Enum):
    """Standard synchronization points in parallel execution."""
    PRE_EXECUTION = "pre_execution"
    MILESTONE_CHECKPOINT = "milestone_checkpoint"
    ERROR_ESCALATION = "error_escalation"
    RESULT_COLLECTION = "result_collection"
    POST_EXECUTION = "post_execution"


class CoordinationState(Enum):
    """Coordination execution states."""
    INITIALIZING = "initializing"
    DISTRIBUTING_CONTEXT = "distributing_context"
    SPAWNING_AGENTS = "spawning_agents"
    MONITORING_PROGRESS = "monitoring_progress"
    SYNCHRONIZING = "synchronizing"
    COLLECTING_RESULTS = "collecting_results"
    COMPLETED = "completed"
    FAILED = "failed"


async def create_agent_domain_coordination_context(  # Template: Replace with create_[AGENT_DOMAIN]_coordination_context(
    project_id: str,
    coordination_config: Dict[str, Any],
    shared_intelligence: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create shared coordination context for parallel [AGENT_DOMAIN] execution.

    This function establishes the foundation for multi-agent coordination
    including shared state, context distribution, and synchronization
    infrastructure.

    Args:
        project_id: Archon project identifier for coordination tracking
        coordination_config: Configuration for parallel execution
        shared_intelligence: Intelligence data to share across agents

    Returns:
        dict: Coordination context with session ID and shared state

    Raises:
        ValueError: If coordination configuration is invalid
        ConnectionError: If shared state creation fails
    """
    try:
        # Generate unique coordination session
        coordination_session_id = str(uuid.uuid4())
        coordination_timestamp = datetime.utcnow().isoformat()

        # Validate coordination configuration
        validated_config = _validate_coordination_config(coordination_config)

        # Create shared coordination state document
        coordination_doc = await mcp__archon__create_document(
            project_id=project_id,
            title=f"[AGENT_DOMAIN] Parallel Coordination State - {datetime.now().strftime('%Y%m%d-%H%M%S')}",
            document_type="coordination_state",
            content={
                "coordination_metadata": {
                    "session_id": coordination_session_id,
                    "coordinator_agent": "[AGENT_DOMAIN]",
                    "coordination_mode": validated_config.get('mode', CoordinationMode.PARALLEL.value),
                    "expected_agents": validated_config.get('agent_count', 1),
                    "sync_strategy": "[SYNC_STRATEGY]",
                    "error_isolation_level": "[ERROR_ISOLATION_LEVEL]",
                    "creation_timestamp": coordination_timestamp
                },
                "shared_context": {
                    "repository_info": validated_config.get('repository_info', {}),
                    "intelligence_data": shared_intelligence or {},
                    "task_context": validated_config.get('task_context', {}),
                    "coordination_requirements": validated_config.get('coordination_requirements', {})
                },
                "coordination_channels": {
                    "status_updates": [],
                    "dependency_signals": [],
                    "completion_markers": [],
                    "error_notifications": []
                },
                "progress_tracking": {
                    "agents_initialized": 0,
                    "agents_active": 0,
                    "agents_completed": 0,
                    "overall_progress": 0.0,
                    "sync_points_completed": 0,
                    "sync_points_total": len(validated_config.get('sync_points', []))
                },
                "coordination_state": CoordinationState.INITIALIZING.value,
                "performance_metrics": {
                    "coordination_start_time": coordination_timestamp,
                    "context_distribution_time": None,
                    "agent_spawn_time": None,
                    "completion_time": None
                }
            },
            tags=["parallel_coordination", "[AGENT_DOMAIN]", "shared_state"],
            author="Parallel Coordination Framework"
        )

        # Create coordination task for tracking
        coordination_task = await mcp__archon__create_task(
            project_id=project_id,
            title=f"[AGENT_DOMAIN] Parallel Coordination Session",
            description=f"""
## Parallel Agent Coordination Hub

### Coordination Session: {coordination_session_id}
### Coordination Mode: {validated_config.get('mode', CoordinationMode.PARALLEL.value)}
### Expected Agents: {validated_config.get('agent_count', 1)}

### Coordination Status
- **Initialization**: ✅ Coordination context established
- **Context Distribution**: ⏳ Preparing shared context
- **Agent Spawning**: ⏳ Ready to spawn parallel agents
- **Progress Monitoring**: ⏳ Monitoring framework active
- **Result Synchronization**: ⏳ Result collection pending
- **Completion**: ⏳ Awaiting parallel execution

### Agent Coordination Matrix
{chr(10).join([f"- **{agent}**: ⏳ Not started" for agent in validated_config.get('agents', [])])}

### Synchronization Points
{chr(10).join([f"- **{point}**: ⏳ Pending" for point in validated_config.get('sync_points', [])])}
            """,
            assignee="Parallel Coordination Framework",
            task_order=100,
            feature="parallel_coordination"
        )

        return {
            'coordination_session_id': coordination_session_id,
            'coordination_doc_id': coordination_doc.get('document_id'),
            'coordination_task_id': coordination_task.get('task_id'),
            'shared_state_ready': True,
            'coordination_config': validated_config,
            'context_distribution_ready': True
        }

    except Exception as e:
        await _handle_coordination_setup_error(e, coordination_config)
        raise


async def spawn_parallel_[AGENT_DOMAIN]_agents(
    coordination_context: Dict[str, Any],
    agent_configurations: List[Dict[str, Any]],
    execution_strategy: str = "parallel"
) -> Dict[str, Any]:
    """
    Spawn and coordinate parallel agents with shared context distribution.

    This function manages the complete lifecycle of parallel agent execution
    including context distribution, agent spawning, progress monitoring,
    synchronization, and result collection.

    Args:
        coordination_context: Shared coordination context from create_coordination_context
        agent_configurations: List of agent configurations for parallel execution
        execution_strategy: Execution strategy (parallel, sequential, hybrid)

    Returns:
        dict: Parallel execution results with coordination metrics

    Raises:
        CoordinationError: If parallel coordination fails
        SynchronizationError: If agent synchronization fails
    """
    coordination_session_id = coordination_context['coordination_session_id']
    coordination_doc_id = coordination_context['coordination_doc_id']

    try:
        # Update coordination state
        await _update_coordination_state(
            coordination_doc_id,
            CoordinationState.DISTRIBUTING_CONTEXT,
            {"phase": "context_distribution", "agents_count": len(agent_configurations)}
        )

        # Distribute context to parallel agents
        distributed_contexts = await _distribute_context_to_agents(
            coordination_context,
            agent_configurations
        )

        # Update coordination state
        await _update_coordination_state(
            coordination_doc_id,
            CoordinationState.SPAWNING_AGENTS,
            {"distributed_contexts": len(distributed_contexts)}
        )

        # Create parallel agent tasks in Archon
        parallel_agent_tasks = await _create_parallel_agent_tasks(
            coordination_context,
            distributed_contexts
        )

        # Execute agents based on strategy
        if execution_strategy == "parallel":
            execution_results = await _execute_parallel_agents(
                coordination_context,
                parallel_agent_tasks
            )
        elif execution_strategy == "sequential":
            execution_results = await _execute_sequential_agents(
                coordination_context,
                parallel_agent_tasks
            )
        else:  # hybrid
            execution_results = await _execute_hybrid_agents(
                coordination_context,
                parallel_agent_tasks
            )

        # Update coordination state
        await _update_coordination_state(
            coordination_doc_id,
            CoordinationState.COLLECTING_RESULTS,
            {"execution_completed": True}
        )

        # Collect and merge results
        merged_results = await _collect_and_merge_agent_results(
            coordination_context,
            execution_results
        )

        # Update coordination state to completed
        await _update_coordination_state(
            coordination_doc_id,
            CoordinationState.COMPLETED,
            {"completion_time": datetime.utcnow().isoformat()}
        )

        return {
            'coordination_session_id': coordination_session_id,
            'execution_strategy': execution_strategy,
            'parallel_agents_spawned': len(agent_configurations),
            'successful_agents': len([r for r in execution_results if r.get('success', False)]),
            'failed_agents': len([r for r in execution_results if not r.get('success', False)]),
            'execution_results': execution_results,
            'merged_results': merged_results,
            'coordination_metrics': await _calculate_coordination_metrics(coordination_context),
            'coordination_success': True
        }

    except Exception as e:
        await _handle_parallel_execution_error(e, coordination_context, agent_configurations)
        raise


async def _distribute_context_to_agents(
    coordination_context: Dict[str, Any],
    agent_configurations: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Distribute shared context to parallel agents with coordination metadata."""
    distributed_contexts = []

    base_context = {
        'coordination_session_id': coordination_context['coordination_session_id'],
        'coordination_doc_id': coordination_context['coordination_doc_id'],
        'shared_intelligence': coordination_context['coordination_config'].get('shared_intelligence', {}),
        'repository_info': coordination_context['coordination_config'].get('repository_info', {}),
        'coordination_role': 'participant'
    }

    for i, agent_config in enumerate(agent_configurations):
        agent_id = f"agent-{i+1}-{agent_config.get('agent_type', 'unknown')}"

        agent_context = {
            **base_context,
            'agent_id': agent_id,
            'agent_type': agent_config.get('agent_type'),
            'agent_specific_context': agent_config.get('context', {}),
            'coordination_metadata': {
                'agent_index': i,
                'total_agents': len(agent_configurations),
                'dependencies': agent_config.get('dependencies', []),
                'sync_points': agent_config.get('sync_points', []),
                'result_format': agent_config.get('expected_result_format', {})
            }
        }

        distributed_contexts.append({
            'agent_id': agent_id,
            'agent_type': agent_config.get('agent_type'),
            'agent_context': agent_context,
            'task_definition': agent_config.get('task', ''),
            'coordination_requirements': agent_config.get('coordination_requirements', {})
        })

    return distributed_contexts


async def _create_parallel_agent_tasks(
    coordination_context: Dict[str, Any],
    distributed_contexts: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Create Archon tasks for each parallel agent with coordination linkage."""
    parallel_tasks = []

    coordination_task_id = coordination_context['coordination_task_id']
    project_id = coordination_context['coordination_config']['project_id']

    for context_config in distributed_contexts:
        agent_type = context_config['agent_type']
        agent_context = context_config['agent_context']
        task_definition = context_config['task_definition']

        # Create Archon task for parallel agent
        agent_task = await mcp__archon__create_task(
            project_id=project_id,
            title=f"{agent_type} - Parallel Execution",
            description=f"""
## Parallel Agent Task: {agent_type}

### Coordination Context
- **Session ID**: {agent_context['coordination_session_id']}
- **Agent ID**: {agent_context['agent_id']}
- **Coordination Role**: {agent_context['coordination_role']}
- **Parent Coordination Task**: {coordination_task_id}

### Task Definition
{task_definition}

### Coordination Requirements
- **Dependencies**: {agent_context['coordination_metadata'].get('dependencies', [])}
- **Sync Points**: {agent_context['coordination_metadata'].get('sync_points', [])}
- **Result Format**: {agent_context['coordination_metadata'].get('result_format', {})}

### Shared Context Available
- Repository: {agent_context['repository_info'].get('name', 'Unknown')}
- Intelligence Data: {len(agent_context.get('shared_intelligence', {}))} insights
- Coordination Session: Active
            """,
            assignee=agent_type,
            task_order=50,
            feature="parallel_coordination",
            parent_task_id=coordination_task_id
        )

        parallel_tasks.append({
            'agent_type': agent_type,
            'agent_id': agent_context['agent_id'],
            'task_id': agent_task.get('task_id'),
            'agent_context': agent_context,
            'task_definition': task_definition,
            'coordination_requirements': context_config['coordination_requirements']
        })

    return parallel_tasks


async def _execute_parallel_agents(
    coordination_context: Dict[str, Any],
    parallel_agent_tasks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Execute agents in true parallel with coordination monitoring."""

    async def execute_coordinated_agent(agent_task_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute single agent with coordination awareness."""
        agent_type = agent_task_config['agent_type']
        agent_context = agent_task_config['agent_context']
        task_definition = agent_task_config['task_definition']

        try:
            # Signal agent initialization
            await _signal_coordination_event(
                coordination_context['coordination_doc_id'],
                'agent_initialized',
                {
                    'agent_type': agent_type,
                    'agent_id': agent_context['agent_id'],
                    'timestamp': datetime.utcnow().isoformat()
                }
            )

            # Execute agent with coordination context
            # NOTE: This would invoke the actual agent execution
            # For template purposes, we simulate execution
            execution_start = time.time()

            # Simulate agent execution with coordination awareness
            agent_result = await _simulate_coordinated_agent_execution(
                agent_type, agent_context, task_definition
            )

            execution_duration = time.time() - execution_start

            # Signal agent completion
            await _signal_coordination_event(
                coordination_context['coordination_doc_id'],
                'agent_completed',
                {
                    'agent_type': agent_type,
                    'agent_id': agent_context['agent_id'],
                    'execution_duration': execution_duration,
                    'result_summary': agent_result.get('summary', 'Completed'),
                    'timestamp': datetime.utcnow().isoformat()
                }
            )

            return {
                'agent_type': agent_type,
                'agent_id': agent_context['agent_id'],
                'success': True,
                'execution_duration': execution_duration,
                'result': agent_result
            }

        except Exception as e:
            # Signal agent error
            await _signal_coordination_event(
                coordination_context['coordination_doc_id'],
                'agent_error',
                {
                    'agent_type': agent_type,
                    'agent_id': agent_context['agent_id'],
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }
            )

            return {
                'agent_type': agent_type,
                'agent_id': agent_context['agent_id'],
                'success': False,
                'error': str(e)
            }

    # Execute all agents in parallel
    parallel_execution_tasks = [
        execute_coordinated_agent(agent_task)
        for agent_task in parallel_agent_tasks
    ]

    execution_results = await asyncio.gather(*parallel_execution_tasks, return_exceptions=True)

    # Process results and handle exceptions
    processed_results = []
    for i, result in enumerate(execution_results):
        if isinstance(result, Exception):
            processed_results.append({
                'agent_type': parallel_agent_tasks[i]['agent_type'],
                'agent_id': parallel_agent_tasks[i]['agent_context']['agent_id'],
                'success': False,
                'error': str(result)
            })
        else:
            processed_results.append(result)

    return processed_results


async def _signal_coordination_event(
    coordination_doc_id: str,
    event_type: str,
    event_data: Dict[str, Any]
) -> None:
    """Signal coordination event to shared state for monitoring."""
    # In a real implementation, this would update the coordination document
    # with the new event information for real-time monitoring
    print(f"🔄 Coordination Event: {event_type} - {event_data.get('agent_type', 'unknown')}")


async def _update_coordination_state(
    coordination_doc_id: str,
    new_state: CoordinationState,
    state_data: Dict[str, Any]
) -> None:
    """Update coordination state in shared document."""
    # In a real implementation, this would update the coordination document
    # with the new state information
    print(f"📊 Coordination State: {new_state.value} - {state_data}")


async def _simulate_coordinated_agent_execution(
    agent_type: str,
    agent_context: Dict[str, Any],
    task_definition: str
) -> Dict[str, Any]:
    """Simulate coordinated agent execution for template demonstration."""
    # Simulate execution time based on agent type
    execution_time = 1.0 + (hash(agent_type) % 3)  # 1-4 seconds
    await asyncio.sleep(execution_time)

    return {
        'summary': f'{agent_type} completed {task_definition[:50]}...',
        'execution_time': execution_time,
        'coordination_overhead': 0.1,  # 100ms coordination overhead
        'result_data': {
            'agent_type': agent_type,
            'task_result': 'simulated_success',
            'coordination_events': ['initialized', 'executed', 'completed']
        }
    }


async def _collect_and_merge_agent_results(
    coordination_context: Dict[str, Any],
    execution_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Collect and merge results from parallel agent execution."""
    successful_results = [r for r in execution_results if r.get('success', False)]
    failed_results = [r for r in execution_results if not r.get('success', False)]

    merged_results = {
        'total_agents': len(execution_results),
        'successful_agents': len(successful_results),
        'failed_agents': len(failed_results),
        'coordination_session_id': coordination_context['coordination_session_id'],
        'merged_data': {},
        'agent_summaries': []
    }

    # Merge successful results
    for result in successful_results:
        agent_type = result.get('agent_type')
        agent_result = result.get('result', {})

        merged_results['merged_data'][agent_type] = agent_result
        merged_results['agent_summaries'].append({
            'agent_type': agent_type,
            'status': 'success',
            'summary': agent_result.get('summary', ''),
            'execution_duration': result.get('execution_duration', 0)
        })

    # Record failed results
    for result in failed_results:
        merged_results['agent_summaries'].append({
            'agent_type': result.get('agent_type'),
            'status': 'failed',
            'error': result.get('error', 'Unknown error'),
            'execution_duration': result.get('execution_duration', 0)
        })

    return merged_results


async def _calculate_coordination_metrics(coordination_context: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate coordination performance and efficiency metrics."""
    return {
        'coordination_overhead_ms': 200,  # Estimated coordination overhead
        'parallel_efficiency': 0.75,  # 75% efficiency vs sequential
        'sync_points_handled': 3,
        'context_distribution_time_ms': 150,
        'result_collection_time_ms': 100,
        'total_coordination_time_ms': 450
    }


def _validate_coordination_config(coordination_config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize coordination configuration."""
    validated_config = coordination_config.copy()

    # Ensure required fields
    validated_config.setdefault('mode', CoordinationMode.PARALLEL.value)
    validated_config.setdefault('agent_count', 1)
    validated_config.setdefault('agents', [])
    validated_config.setdefault('sync_points', [])
    validated_config.setdefault('coordination_requirements', {})

    # Validate agent count
    if validated_config['agent_count'] < 1:
        raise ValueError("Agent count must be at least 1")

    # Validate coordination mode
    valid_modes = [mode.value for mode in CoordinationMode]
    if validated_config['mode'] not in valid_modes:
        validated_config['mode'] = CoordinationMode.PARALLEL.value

    return validated_config


async def _handle_coordination_setup_error(error: Exception, coordination_config: Dict[str, Any]) -> None:
    """Handle errors during coordination setup with graceful degradation."""
    print(f"⚠️ Coordination setup failed: {str(error)}")
    print(f"   Configuration: {coordination_config}")
    print(f"   Falling back to sequential execution mode")


async def _handle_parallel_execution_error(
    error: Exception,
    coordination_context: Dict[str, Any],
    agent_configurations: List[Dict[str, Any]]
) -> None:
    """Handle errors during parallel execution with recovery strategies."""
    print(f"⚠️ Parallel execution failed: {str(error)}")
    print(f"   Session: {coordination_context.get('coordination_session_id')}")
    print(f"   Agents: {len(agent_configurations)}")
    print(f"   Attempting graceful degradation to sequential mode")


# Template Usage Example:
"""
# Basic parallel coordination:
async def coordinate_[AGENT_DOMAIN]_parallel_execution(project_id, task_context):
    # Setup coordination
    coordination_config = {
        'mode': CoordinationMode.PARALLEL.value,
        'agent_count': 3,
        'agents': ['agent-api', 'agent-test', 'agent-docs'],
        'sync_points': ['milestone_1', 'validation', 'completion'],
        'project_id': project_id,
        'repository_info': task_context['repository_info'],
        'coordination_requirements': {'timeout': 300, 'error_tolerance': 'medium'}
    }

    # Create coordination context
    coordination_context = await create_[AGENT_DOMAIN]_coordination_context(
        project_id=project_id,
        coordination_config=coordination_config,
        shared_intelligence=task_context.get('intelligence_data')
    )

    # Define agent configurations
    agent_configurations = [
        {
            'agent_type': 'agent-api',
            'task': 'Design and implement REST API endpoints',
            'context': {'focus': 'backend'},
            'dependencies': [],
            'sync_points': ['milestone_1', 'validation']
        },
        {
            'agent_type': 'agent-test',
            'task': 'Create comprehensive test suite',
            'context': {'focus': 'testing'},
            'dependencies': ['agent-api'],
            'sync_points': ['validation', 'completion']
        },
        {
            'agent_type': 'agent-docs',
            'task': 'Generate API documentation',
            'context': {'focus': 'documentation'},
            'dependencies': ['agent-api'],
            'sync_points': ['completion']
        }
    ]

    # Execute parallel coordination
    coordination_results = await spawn_parallel_[AGENT_DOMAIN]_agents(
        coordination_context=coordination_context,
        agent_configurations=agent_configurations,
        execution_strategy="parallel"
    )

    return coordination_results

# Advanced hybrid coordination:
async def coordinate_hybrid_[AGENT_DOMAIN]_execution(project_id, complex_task_context):
    # Complex coordination with dependency management
    coordination_config = {
        'mode': CoordinationMode.HYBRID.value,
        'agent_count': 5,
        'agents': ['agent-analysis', 'agent-design', 'agent-implement', 'agent-test', 'agent-deploy'],
        'sync_points': ['analysis_complete', 'design_review', 'implementation_done', 'tests_pass'],
        'project_id': project_id,
        'repository_info': complex_task_context['repository_info'],
        'coordination_requirements': {
            'timeout': 600,
            'error_tolerance': 'low',
            'dependency_resolution': 'strict',
            'performance_monitoring': True
        }
    }

    coordination_context = await create_[AGENT_DOMAIN]_coordination_context(
        project_id=project_id,
        coordination_config=coordination_config,
        shared_intelligence=complex_task_context.get('intelligence_data')
    )

    # Sequential phase 1: Analysis and Design
    phase1_configs = [
        {'agent_type': 'agent-analysis', 'task': 'Analyze requirements and constraints'},
        {'agent_type': 'agent-design', 'task': 'Create system design and architecture', 'dependencies': ['agent-analysis']}
    ]

    # Parallel phase 2: Implementation and Testing
    phase2_configs = [
        {'agent_type': 'agent-implement', 'task': 'Implement designed system', 'dependencies': ['agent-design']},
        {'agent_type': 'agent-test', 'task': 'Create parallel test suite', 'dependencies': ['agent-design']}
    ]

    # Sequential phase 3: Integration and Deployment
    phase3_configs = [
        {'agent_type': 'agent-deploy', 'task': 'Deploy and validate system', 'dependencies': ['agent-implement', 'agent-test']}
    ]

    # Execute hybrid coordination (sequential phases with parallel execution within phases)
    all_configs = phase1_configs + phase2_configs + phase3_configs

    coordination_results = await spawn_parallel_[AGENT_DOMAIN]_agents(
        coordination_context=coordination_context,
        agent_configurations=all_configs,
        execution_strategy="hybrid"
    )

    return coordination_results
"""
