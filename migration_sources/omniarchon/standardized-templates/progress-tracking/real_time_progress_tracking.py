"""
Agent Progress Tracking Template: Real-Time Progress Monitoring
=============================================================

Standardized template for implementing comprehensive real-time progress tracking
across all agents. This template provides consistent progress monitoring patterns
that integrate with Archon MCP for transparent task execution visibility.

Template Parameters:
- AGENT_DOMAIN: Short domain identifier (e.g., debug, api_design, testing)
- AGENT_TITLE: Human-readable agent title for progress messages
- PHASE_DEFINITIONS: Agent-specific execution phases list
- PROGRESS_DETAIL_LEVEL: Level of detail for progress reporting (basic, standard, detailed)

Usage:
    1. Import this template into your agent implementation
    2. Replace template parameters with agent-specific values
    3. Call track_agent_progress() at each major execution phase
    4. Use progress phase constants for consistency
    5. Implement custom progress detail functions as needed

Dependencies:
    - mcp__archon__update_task() function
    - datetime module for timestamps
    - Agent task ID from context establishment

Quality Gates:
    - Progress phase validation
    - Progress percentage validation (0-100)
    - Execution time tracking
    - Error state handling
"""

import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class ProgressPhase(Enum):
    """Standardized progress phases across all agents."""
    INITIALIZATION = "initialization"
    INTELLIGENCE_GATHERING = "intelligence_gathering"
    PARALLEL_COORDINATION = "parallel_coordination"
    PLANNING = "planning"
    EXECUTION = "execution"
    COORDINATION_MONITORING = "coordination_monitoring"
    VALIDATION = "validation"
    COMPLETION = "completion"


class ProgressStatus(Enum):
    """Progress status indicators."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


def track_agent_domain_progress(  # Template: Replace with track_[AGENT_DOMAIN]_progress(
    task_id: Optional[str],
    phase: Union[ProgressPhase, str],
    progress_data: Dict[str, Any],
    execution_context: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Track real-time progress for [AGENT_TITLE].

    This function implements the standardized Phase 3 progress tracking
    pattern from the Archon MCP Integration Framework. It provides
    consistent progress monitoring across all agent types.

    Args:
        task_id: Archon task identifier (None for local-only mode)
        phase: Current execution phase (ProgressPhase enum or string)
        progress_data: Phase-specific progress information
        execution_context: Additional execution context for detailed reporting

    Returns:
        bool: True if progress was successfully tracked, False otherwise

    Raises:
        ValueError: If progress data is invalid or incomplete
        ConnectionError: If Archon MCP connection fails
    """
    if not task_id:
        # Local-only mode - log progress without Archon integration
        _log_local_progress(phase, progress_data)
        return True

    try:
        # Validate progress data
        validated_progress = _validate_progress_data(progress_data, phase)

        # Build comprehensive progress description
        progress_description = _build_progress_description(
            phase, validated_progress, execution_context
        )

        # Determine task status based on phase and progress
        task_status = _determine_task_status(phase, validated_progress)

        # Update Archon task with current progress
        mcp__archon__update_task(
            task_id=task_id,
            status=task_status,
            description=progress_description
        )

        # Log successful progress update
        _log_progress_update(task_id, phase, validated_progress)

        return True

    except Exception as e:
        _handle_progress_tracking_error(e, task_id, phase, progress_data)
        return False


def _validate_progress_data(progress_data: Dict[str, Any], phase: Union[ProgressPhase, str]) -> Dict[str, Any]:
    """Validate and normalize progress data."""
    validated_data = progress_data.copy()

    # Ensure required fields
    validated_data.setdefault('current_step', f'Executing {phase}')
    validated_data.setdefault('completed', [])
    validated_data.setdefault('next_actions', [])
    validated_data.setdefault('progress_percentage', 0)
    validated_data.setdefault('execution_start_time', datetime.utcnow().isoformat())

    # Validate progress percentage
    progress_pct = validated_data.get('progress_percentage', 0)
    if not isinstance(progress_pct, (int, float)) or not (0 <= progress_pct <= 100):
        validated_data['progress_percentage'] = 0

    # Normalize phase
    if isinstance(phase, ProgressPhase):
        validated_data['phase_name'] = phase.value
    else:
        validated_data['phase_name'] = str(phase)

    return validated_data


def _build_progress_description(
    phase: Union[ProgressPhase, str],
    progress_data: Dict[str, Any],
    execution_context: Optional[Dict[str, Any]] = None
) -> str:
    """Build comprehensive progress description for Archon task."""

    # Calculate execution duration
    start_time_str = progress_data.get('execution_start_time', datetime.utcnow().isoformat())
    try:
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        duration = datetime.utcnow() - start_time.replace(tzinfo=None)
        duration_str = str(duration).split('.')[0]  # Remove microseconds
    except:
        duration_str = "Unknown"

    # Build main progress description
    description = f"""
## Current Progress: {progress_data.get('phase_name', phase)} ({progress_data.get('progress_percentage', 0)}%)

### Execution Duration
{duration_str}

### Completed Steps
{chr(10).join([f"✅ {step}" for step in progress_data.get('completed', [])])}

### Current Step
🔄 {progress_data.get('current_step', 'Processing...')}

### Next Actions
{chr(10).join([f"⏳ {action}" for action in progress_data.get('next_actions', [])])}

### Intelligence Integration Status
- Orchestrated Research: {progress_data.get('services_successful', 0)} of 3 backend services
- RAG Patterns Applied: {len(progress_data.get('rag_patterns', []))} patterns
- Vector Insights: {len(progress_data.get('vector_insights', []))} semantic matches
- Knowledge Relationships: {len(progress_data.get('knowledge_relationships', []))} connections
- Synthesis Confidence: {progress_data.get('confidence_score', 0.0):.2f}
- Research Duration: {progress_data.get('research_duration_ms', 0)}ms
- Quality Gates Status: {progress_data.get('quality_checks', 'Pending')}
"""

    # Add parallel coordination status if applicable
    if progress_data.get('parallel_coordination_active'):
        description += f"""
### Parallel Coordination Status
- Coordination Session: {progress_data.get('coordination_session_id', 'None')}
- Parallel Agents Active: {progress_data.get('parallel_agents_active', 0)}
- Agents Completed: {progress_data.get('parallel_agents_completed', 0)}
- Coordination Overhead: {progress_data.get('coordination_overhead_ms', 0)}ms
- Dependencies Resolved: {progress_data.get('dependencies_resolved', 0)}
- Sync Points Passed: {progress_data.get('sync_points_completed', 0)}/{progress_data.get('sync_points_total', 0)}
"""

    # Add detailed execution context if available
    if execution_context:
        description += _build_execution_context_section(execution_context)

    # Add error information if present
    if progress_data.get('errors') or progress_data.get('warnings'):
        description += f"""
### Issues and Warnings
{chr(10).join([f"❌ {error}" for error in progress_data.get('errors', [])])}
{chr(10).join([f"⚠️ {warning}" for warning in progress_data.get('warnings', [])])}
"""

    # Add performance metrics if available
    if progress_data.get('performance_metrics'):
        description += _build_performance_metrics_section(progress_data['performance_metrics'])

    return description


def _build_execution_context_section(execution_context: Dict[str, Any]) -> str:
    """Build execution context section for detailed progress reporting."""
    section = """
### Detailed Execution Context
"""

    # Repository information
    if repo_info := execution_context.get('repository_info'):
        section += f"""
**Repository Context:**
- Repository: {repo_info.get('name', 'Unknown')}
- Branch: {repo_info.get('branch', 'Unknown')}
- Commit: {repo_info.get('commit', 'Unknown')}
"""

    # Task context
    if task_context := execution_context.get('task_context'):
        section += f"""
**Task Context:**
- Domain: {task_context.get('domain', 'Unknown')}
- Complexity Level: {task_context.get('complexity_level', 'Unknown')}
- Technology Stack: {', '.join(task_context.get('technology_stack', []))}
"""

    # Tools and resources used
    if tools_used := execution_context.get('tools_used'):
        section += f"""
**Tools and Resources:**
{chr(10).join([f"- {tool}" for tool in tools_used])}
"""

    return section


def _build_performance_metrics_section(performance_metrics: Dict[str, Any]) -> str:
    """Build performance metrics section for progress reporting."""
    return f"""
### Performance Metrics
- Memory Usage: {performance_metrics.get('memory_usage_mb', 'Unknown')} MB
- CPU Usage: {performance_metrics.get('cpu_usage_percent', 'Unknown')}%
- Network I/O: {performance_metrics.get('network_io_mb', 'Unknown')} MB
- Response Time: {performance_metrics.get('avg_response_time_ms', 'Unknown')} ms
- Throughput: {performance_metrics.get('operations_per_second', 'Unknown')} ops/sec
"""


def _determine_task_status(phase: Union[ProgressPhase, str], progress_data: Dict[str, Any]) -> str:
    """Determine appropriate Archon task status based on phase and progress."""

    # Handle phase as enum or string
    if isinstance(phase, ProgressPhase):
        phase_value = phase.value
    else:
        phase_value = str(phase).lower()

    # Check for error conditions
    if progress_data.get('errors') or progress_data.get('status') == 'failed':
        return "todo"  # Reset to todo for retry

    # Determine status based on phase
    if phase_value == ProgressPhase.COMPLETION.value:
        return "done"
    elif phase_value == ProgressPhase.VALIDATION.value and progress_data.get('progress_percentage', 0) >= 90:
        return "review"
    else:
        return "doing"


def _log_local_progress(phase: Union[ProgressPhase, str], progress_data: Dict[str, Any]) -> None:
    """Log progress in local-only mode when Archon MCP is unavailable."""
    phase_name = phase.value if isinstance(phase, ProgressPhase) else str(phase)
    progress_pct = progress_data.get('progress_percentage', 0)
    current_step = progress_data.get('current_step', 'Processing...')

    print(f"📊 [AGENT_TITLE] Progress: {phase_name.title()} ({progress_pct}%)")
    print(f"   Current: {current_step}")

    if completed := progress_data.get('completed'):
        print(f"   Completed: {len(completed)} steps")

    if next_actions := progress_data.get('next_actions'):
        print(f"   Next: {len(next_actions)} actions planned")


def _log_progress_update(task_id: str, phase: Union[ProgressPhase, str], progress_data: Dict[str, Any]) -> None:
    """Log successful progress update for debugging and monitoring."""
    phase_name = phase.value if isinstance(phase, ProgressPhase) else str(phase)
    progress_pct = progress_data.get('progress_percentage', 0)

    print(f"✅ Progress updated for task {task_id}: {phase_name} ({progress_pct}%)")


def _handle_progress_tracking_error(
    error: Exception,
    task_id: Optional[str],
    phase: Union[ProgressPhase, str],
    progress_data: Dict[str, Any]
) -> None:
    """Handle errors in progress tracking with graceful degradation."""
    phase_name = phase.value if isinstance(phase, ProgressPhase) else str(phase)

    print(f"⚠️ Progress tracking failed for {phase_name}: {str(error)}")
    print(f"   Task ID: {task_id}")
    print(f"   Falling back to local progress logging")

    # Fall back to local logging
    _log_local_progress(phase, progress_data)


# Standard progress tracking phases for different agent types
class [AGENT_DOMAIN]ProgressPhases:
    """Agent-specific progress phases for [AGENT_TITLE]."""

    # Customize these phases based on your agent's workflow
    PHASE_DEFINITIONS = [
        # Replace with agent-specific phases
        {"phase": ProgressPhase.INITIALIZATION, "weight": 10, "description": "Setting up agent context"},
        {"phase": ProgressPhase.INTELLIGENCE_GATHERING, "weight": 20, "description": "Gathering domain intelligence"},
        {"phase": ProgressPhase.PLANNING, "weight": 15, "description": "Planning execution strategy"},
        {"phase": ProgressPhase.EXECUTION, "weight": 40, "description": "Executing primary tasks"},
        {"phase": ProgressPhase.VALIDATION, "weight": 10, "description": "Validating results"},
        {"phase": ProgressPhase.COMPLETION, "weight": 5, "description": "Finalizing and cleanup"}
    ]

    @classmethod
    def calculate_overall_progress(cls, current_phase: ProgressPhase, phase_progress: float = 0.0) -> float:
        """Calculate overall progress percentage based on current phase and phase progress."""
        total_weight = sum(phase_def["weight"] for phase_def in cls.PHASE_DEFINITIONS)
        completed_weight = 0

        for phase_def in cls.PHASE_DEFINITIONS:
            if phase_def["phase"] == current_phase:
                # Add partial progress for current phase
                completed_weight += phase_def["weight"] * (phase_progress / 100.0)
                break
            else:
                # Add full weight for completed phases
                completed_weight += phase_def["weight"]

        return min((completed_weight / total_weight) * 100, 100)


# Convenience functions for common progress tracking patterns
def track_initialization_progress(task_id: Optional[str], step: str, completed_steps: List[str]) -> bool:
    """Track progress during agent initialization phase."""
    return track_[AGENT_DOMAIN]_progress(
        task_id=task_id,
        phase=ProgressPhase.INITIALIZATION,
        progress_data={
            'current_step': step,
            'completed': completed_steps,
            'progress_percentage': len(completed_steps) * 20  # Assuming 5 init steps
        }
    )


def track_execution_progress(
    task_id: Optional[str],
    step: str,
    completed_steps: List[str],
    total_steps: int,
    execution_metrics: Optional[Dict[str, Any]] = None
) -> bool:
    """Track progress during main execution phase."""
    progress_percentage = (len(completed_steps) / total_steps) * 100 if total_steps > 0 else 0

    progress_data = {
        'current_step': step,
        'completed': completed_steps,
        'progress_percentage': progress_percentage,
        'total_steps': total_steps
    }

    if execution_metrics:
        progress_data.update(execution_metrics)

    return track_[AGENT_DOMAIN]_progress(
        task_id=task_id,
        phase=ProgressPhase.EXECUTION,
        progress_data=progress_data
    )


def track_completion_progress(
    task_id: Optional[str],
    final_status: str,
    results_summary: Dict[str, Any],
    knowledge_captured: bool = False
) -> bool:
    """Track progress during completion phase."""
    return track_[AGENT_DOMAIN]_progress(
        task_id=task_id,
        phase=ProgressPhase.COMPLETION,
        progress_data={
            'current_step': 'Finalizing execution',
            'completed': ['Primary execution', 'Quality validation', 'Results compilation'],
            'progress_percentage': 100,
            'final_status': final_status,
            'results_summary': results_summary,
            'knowledge_captured': knowledge_captured
        }
    )


# Template Usage Example:
"""
# Basic usage in agent implementation:
def execute_[AGENT_DOMAIN]_task(task_id, task_context):
    # Phase 1: Initialization
    track_initialization_progress(task_id, "Setting up context", ["Repository detected"])

    # Phase 2: Intelligence Gathering
    track_[AGENT_DOMAIN]_progress(task_id, ProgressPhase.INTELLIGENCE_GATHERING, {
        'current_step': 'Gathering domain intelligence',
        'completed': ['Context established'],
        'next_actions': ['RAG query', 'Pattern analysis'],
        'progress_percentage': 25
    })

    # Phase 3: Execution with progress updates
    for i, step in enumerate(execution_steps):
        track_execution_progress(task_id, f"Executing {step}", completed_steps[:i], len(execution_steps))
        # Execute step...
        completed_steps.append(step)

    # Phase 4: Completion
    track_completion_progress(task_id, "completed", results_summary, True)

# Advanced usage with parallel coordination:
def execute_parallel_[AGENT_DOMAIN]_task(task_id, coordination_context):
    track_[AGENT_DOMAIN]_progress(task_id, ProgressPhase.PARALLEL_COORDINATION, {
        'current_step': 'Coordinating with parallel agents',
        'parallel_coordination_active': True,
        'coordination_session_id': coordination_context['session_id'],
        'parallel_agents_active': len(coordination_context['agents']),
        'sync_points_total': coordination_context['sync_points'],
        'progress_percentage': 30
    })
"""
