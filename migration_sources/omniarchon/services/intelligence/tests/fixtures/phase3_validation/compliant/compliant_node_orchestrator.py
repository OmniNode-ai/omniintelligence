"""
Perfect ONEX Orchestrator Node Example

This fixture provides a fully compliant Orchestrator node implementation
for testing validation logic.

ONEX Compliance:
- Naming: NodeWorkflowCoordinatorOrchestrator (suffix-based)
- File: node_workflow_coordinator_orchestrator.py
- Method: async def execute_orchestration(self, contract: ModelContractOrchestrator)
- Contract: ModelContractOrchestrator with proper structure
- Purpose: Workflow coordination, dependency management
"""

from typing import Any, Dict, List
from uuid import uuid4

# ============================================================================
# Compliant Contract
# ============================================================================


class ModelContractBase:
    """Base contract for ONEX nodes."""

    def __init__(self, name: str, version: str, description: str, node_type: str):
        self.name = name
        self.version = version
        self.description = description
        self.node_type = node_type


class ModelContractOrchestrator(ModelContractBase):
    """Contract for Orchestrator nodes."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        workflow_steps: List[Dict[str, Any]],
        dependency_graph: Dict[str, List[str]],
        parallelization_enabled: bool = True,
    ):
        super().__init__(name, version, description, "orchestrator")
        self.workflow_steps = workflow_steps
        self.dependency_graph = dependency_graph
        self.parallelization_enabled = parallelization_enabled


class ModelResult:
    """Standard result model."""

    def __init__(self, success: bool, data: Any = None, error: str = None):
        self.success = success
        self.data = data
        self.error = error


# ============================================================================
# Compliant Orchestrator Node
# ============================================================================


class NodeWorkflowCoordinatorOrchestrator:
    """
    ONEX-Compliant Orchestrator Node for workflow coordination.

    This node handles:
    - Workflow step coordination
    - Dependency resolution
    - Parallel execution management
    - Proper naming convention (suffix: Orchestrator)
    - Method signature (execute_orchestration)
    """

    def __init__(self, node_registry=None, execution_engine=None):
        self.node_registry = node_registry or {}
        self.execution_engine = execution_engine
        self._execution_history: List[Dict[str, Any]] = []

    async def execute_orchestration(
        self, contract: ModelContractOrchestrator
    ) -> ModelResult:
        """
        Execute workflow orchestration with dependency management.

        Args:
            contract: Orchestrator contract with workflow details

        Returns:
            ModelResult with workflow execution results
        """
        try:
            # Validate contract
            if not isinstance(contract, ModelContractOrchestrator):
                return ModelResult(success=False, error="Invalid contract type")

            if not contract.workflow_steps:
                return ModelResult(success=False, error="No workflow steps defined")

            # Validate dependency graph
            if not self._validate_dependencies(
                contract.dependency_graph, contract.workflow_steps
            ):
                return ModelResult(success=False, error="Invalid dependency graph")

            # Build execution plan
            execution_plan = await self._build_execution_plan(
                contract.workflow_steps, contract.dependency_graph
            )

            # Execute workflow
            results = await self._execute_workflow(
                execution_plan, contract.parallelization_enabled
            )

            return ModelResult(
                success=True,
                data={
                    "workflow_id": str(uuid4()),
                    "steps_executed": len(results),
                    "results": results,
                    "execution_plan": execution_plan,
                },
            )

        except Exception as e:
            return ModelResult(
                success=False, error=f"Orchestration execution failed: {str(e)}"
            )

    def _validate_dependencies(
        self,
        dependency_graph: Dict[str, List[str]],
        workflow_steps: List[Dict[str, Any]],
    ) -> bool:
        """Validate that dependency graph is valid."""
        step_names = {step["name"] for step in workflow_steps}

        # Check all dependencies exist
        for step_name, dependencies in dependency_graph.items():
            if step_name not in step_names:
                return False
            for dep in dependencies:
                if dep not in step_names:
                    return False

        # Check for circular dependencies
        return not self._has_circular_dependencies(dependency_graph)

    def _has_circular_dependencies(self, graph: Dict[str, List[str]]) -> bool:
        """Check for circular dependencies in the graph."""
        visited = set()
        rec_stack = set()

        def visit(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if visit(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                if visit(node):
                    return True

        return False

    async def _build_execution_plan(
        self,
        workflow_steps: List[Dict[str, Any]],
        dependency_graph: Dict[str, List[str]],
    ) -> List[List[str]]:
        """
        Build execution plan with parallel batches.

        Returns:
            List of execution batches (parallel groups)
        """
        # Topological sort with parallel batching
        in_degree = {step["name"]: 0 for step in workflow_steps}
        for dependencies in dependency_graph.values():
            for dep in dependencies:
                in_degree[dep] = in_degree.get(dep, 0) + 1

        execution_plan = []
        remaining_steps = {step["name"] for step in workflow_steps}

        while remaining_steps:
            # Find steps with no dependencies (can execute in parallel)
            ready_steps = [
                step for step in remaining_steps if in_degree.get(step, 0) == 0
            ]

            if not ready_steps:
                # Circular dependency or invalid graph
                break

            execution_plan.append(ready_steps)

            # Update in-degrees
            for step in ready_steps:
                remaining_steps.remove(step)
                for dependent in dependency_graph.get(step, []):
                    in_degree[dependent] -= 1

        return execution_plan

    async def _execute_workflow(
        self, execution_plan: List[List[str]], parallelization_enabled: bool
    ) -> List[Dict[str, Any]]:
        """
        Execute workflow according to execution plan.

        Args:
            execution_plan: List of parallel execution batches
            parallelization_enabled: Whether to execute steps in parallel

        Returns:
            List of execution results
        """
        results = []

        for batch in execution_plan:
            if parallelization_enabled and len(batch) > 1:
                # Execute batch in parallel
                batch_results = await self._execute_parallel_batch(batch)
            else:
                # Execute batch sequentially
                batch_results = await self._execute_sequential_batch(batch)

            results.extend(batch_results)

        return results

    async def _execute_parallel_batch(self, batch: List[str]) -> List[Dict[str, Any]]:
        """Execute a batch of steps in parallel."""
        # Simulated parallel execution
        return [
            {
                "step_name": step,
                "status": "completed",
                "execution_id": str(uuid4()),
                "parallel": True,
            }
            for step in batch
        ]

    async def _execute_sequential_batch(self, batch: List[str]) -> List[Dict[str, Any]]:
        """Execute a batch of steps sequentially."""
        results = []
        for step in batch:
            results.append(
                {
                    "step_name": step,
                    "status": "completed",
                    "execution_id": str(uuid4()),
                    "parallel": False,
                }
            )
        return results


# ============================================================================
# Test Fixture Code Strings
# ============================================================================

COMPLIANT_ORCHESTRATOR_NODE_CODE = '''
class NodeWorkflowCoordinatorOrchestrator:
    """ONEX-Compliant Orchestrator Node for workflow coordination."""

    async def execute_orchestration(self, contract: ModelContractOrchestrator) -> ModelResult:
        """Execute workflow orchestration with dependency management."""
        try:
            # Validate dependencies
            if not self._validate_dependencies(contract.dependency_graph, contract.workflow_steps):
                return ModelResult(success=False, error="Invalid dependencies")

            # Build execution plan
            execution_plan = await self._build_execution_plan(
                contract.workflow_steps, contract.dependency_graph
            )

            # Execute workflow
            results = await self._execute_workflow(
                execution_plan, contract.parallelization_enabled
            )

            return ModelResult(success=True, data=results)
        except Exception as e:
            return ModelResult(success=False, error=str(e))
'''

COMPLIANT_ORCHESTRATOR_CONTRACT_CODE = '''
class ModelContractOrchestrator(ModelContractBase):
    """Contract for Orchestrator nodes."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        workflow_steps: list,
        dependency_graph: dict,
        parallelization_enabled: bool = True,
    ):
        super().__init__(name, version, description, "orchestrator")
        self.workflow_steps = workflow_steps
        self.dependency_graph = dependency_graph
        self.parallelization_enabled = parallelization_enabled
'''
