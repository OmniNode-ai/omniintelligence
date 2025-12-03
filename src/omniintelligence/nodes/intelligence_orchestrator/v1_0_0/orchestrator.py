"""
Unified Intelligence Orchestrator

ONEX-compliant declarative orchestrator for intelligence operations.
Routes operations via EnumOperationType to appropriate workflow definitions.

Architecture:
    - Inherits from NodeOrchestratorDeclarative (action-emission pattern)
    - Orchestrators plan, they don't execute
    - Emits ModelAction objects for downstream nodes
    - Remains deterministic, stateless, replayable
"""

from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from omnibase_core.enums.enum_workflow_execution import EnumExecutionMode
from omnibase_core.models.container.model_onex_container import ModelONEXContainer
from omnibase_core.models.contracts.subcontracts.model_coordination_rules import (
    ModelCoordinationRules,
)
from omnibase_core.models.contracts.subcontracts.model_execution_graph import (
    ModelExecutionGraph,
)
from omnibase_core.models.contracts.subcontracts.model_workflow_definition import (
    ModelWorkflowDefinition,
)
from omnibase_core.models.contracts.subcontracts.model_workflow_definition_metadata import (
    ModelWorkflowDefinitionMetadata,
)
from omnibase_core.models.primitives.model_semver import ModelSemVer
from omnibase_core.nodes.node_orchestrator_declarative import NodeOrchestratorDeclarative

from omniintelligence.enums import EnumIntentType, EnumOperationType
from omniintelligence.models import (
    ModelIntent,
    ModelOrchestratorInput,
    ModelOrchestratorOutput,
)


# Workflow contract directory relative to this file
_WORKFLOWS_DIR = Path(__file__).parent / "contracts" / "workflows"


class IntelligenceOrchestrator(NodeOrchestratorDeclarative):
    """
    Unified declarative orchestrator for ALL intelligence operations.

    Handles operations via operation_type enum:
    - DOCUMENT_INGESTION: Vectorization + Entity extraction + Graph storage
    - PATTERN_LEARNING: 4-phase pattern learning
    - QUALITY_ASSESSMENT: Quality scoring + ONEX compliance
    - SEMANTIC_ANALYSIS: Semantic analysis
    - RELATIONSHIP_DETECTION: Relationship detection

    Uses YAML workflow contracts for declarative orchestration.
    Emits ModelAction objects for downstream node execution.
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        """
        Initialize intelligence orchestrator.

        Args:
            container: ONEX container for dependency injection
        """
        super().__init__(container)
        self._workflow_cache: dict[EnumOperationType, ModelWorkflowDefinition] = {}

    def _load_workflow_definition(
        self, operation_type: EnumOperationType
    ) -> ModelWorkflowDefinition:
        """
        Load workflow definition for an operation type.

        Args:
            operation_type: The operation type to load workflow for

        Returns:
            ModelWorkflowDefinition for the operation

        Raises:
            FileNotFoundError: If workflow contract not found
            ValueError: If workflow contract is invalid
        """
        # Check cache first
        if operation_type in self._workflow_cache:
            return self._workflow_cache[operation_type]

        # Map operation type to workflow file
        workflow_files = {
            EnumOperationType.DOCUMENT_INGESTION: "document_ingestion.yaml",
            EnumOperationType.PATTERN_LEARNING: "pattern_learning.yaml",
            EnumOperationType.QUALITY_ASSESSMENT: "quality_assessment.yaml",
            EnumOperationType.SEMANTIC_ANALYSIS: "semantic_analysis.yaml",
            EnumOperationType.RELATIONSHIP_DETECTION: "relationship_detection.yaml",
        }

        workflow_file = workflow_files.get(operation_type)
        if not workflow_file:
            raise ValueError(f"No workflow defined for operation type: {operation_type}")

        workflow_path = _WORKFLOWS_DIR / workflow_file
        if not workflow_path.exists():
            raise FileNotFoundError(f"Workflow contract not found: {workflow_path}")

        # Load YAML
        with open(workflow_path) as f:
            raw_config = yaml.safe_load(f)

        # Convert to ModelWorkflowDefinition
        workflow_def = self._parse_workflow_contract(raw_config, operation_type)

        # Cache and return
        self._workflow_cache[operation_type] = workflow_def
        return workflow_def

    def _parse_workflow_contract(
        self,
        raw_config: dict[str, Any],
        operation_type: EnumOperationType,
    ) -> ModelWorkflowDefinition:
        """
        Parse raw YAML config into ModelWorkflowDefinition.

        Converts legacy LlamaIndex-style workflow YAML to declarative format.

        Args:
            raw_config: Raw YAML configuration dict
            operation_type: Operation type for context

        Returns:
            ModelWorkflowDefinition for workflow execution
        """
        # Extract version info
        version_info = raw_config.get("version", {"major": 1, "minor": 0, "patch": 0})
        semver = ModelSemVer(
            major=version_info.get("major", 1),
            minor=version_info.get("minor", 0),
            patch=version_info.get("patch", 0),
        )

        # Determine execution mode from workflow type
        workflow_type = raw_config.get("workflow_type", "sequential")
        if "parallel" in workflow_type.lower():
            execution_mode = "parallel"
        elif "batch" in workflow_type.lower():
            execution_mode = "batch"
        else:
            execution_mode = "sequential"

        # Extract timeout from performance settings
        performance = raw_config.get("performance", {})
        timeout_ms = performance.get("timeout_seconds", 600) * 1000

        # Create workflow metadata
        metadata = ModelWorkflowDefinitionMetadata(
            version=semver,
            workflow_name=raw_config.get("name", f"{operation_type.value}_workflow"),
            workflow_version=semver,
            description=raw_config.get("description", f"Workflow for {operation_type.value}"),
            execution_mode=execution_mode,
            timeout_ms=timeout_ms,
        )

        # Create execution graph (nodes extracted from steps)
        execution_graph = ModelExecutionGraph(
            version=semver,
            nodes=[],  # Nodes will be created from steps during execution
        )

        # Create coordination rules
        coordination_rules = ModelCoordinationRules(
            version=semver,
            parallel_execution_allowed=(execution_mode == "parallel"),
            synchronization_points=[],
        )

        return ModelWorkflowDefinition(
            version=semver,
            workflow_metadata=metadata,
            execution_graph=execution_graph,
            coordination_rules=coordination_rules,
        )

    def _extract_steps_from_config(
        self,
        raw_config: dict[str, Any],
        input_data: ModelOrchestratorInput,
    ) -> list[dict[str, Any]]:
        """
        Extract workflow steps from raw YAML config.

        Converts legacy step definitions to ModelWorkflowStep-compatible dicts.

        Args:
            raw_config: Raw YAML configuration dict
            input_data: Orchestrator input data

        Returns:
            List of step configuration dicts for workflow execution
        """
        steps_config: list[dict[str, Any]] = []
        raw_steps = raw_config.get("steps", [])

        for step in raw_steps:
            # Handle nested parallel steps
            if step.get("type") == "parallel" and "steps" in step:
                for sub_step in step["steps"]:
                    steps_config.append(
                        self._convert_step_to_config(sub_step, input_data.correlation_id)
                    )
            else:
                steps_config.append(
                    self._convert_step_to_config(step, input_data.correlation_id)
                )

        return steps_config

    def _convert_step_to_config(
        self,
        step: dict[str, Any],
        correlation_id: str,
    ) -> dict[str, Any]:
        """
        Convert a single step definition to ModelWorkflowStep-compatible dict.

        Args:
            step: Raw step definition from YAML
            correlation_id: Correlation ID for tracing

        Returns:
            Dict compatible with ModelWorkflowStep
        """
        step_id = uuid4()

        # Map legacy step types to ONEX step types
        step_type_map = {
            "validation": "compute",
            "intent": "orchestrator",
            "compute": "compute",
            "effect": "effect",
            "parallel": "orchestrator",
        }

        raw_type = step.get("type", "compute")
        step_type = step_type_map.get(raw_type, "compute")

        # Handle error action
        on_error = step.get("on_error", "continue")
        error_action = "stop" if on_error == "fail_immediately" else "continue"

        return {
            "step_id": step_id,
            "step_name": step.get("name", f"step_{step_id.hex[:8]}"),
            "step_type": step_type,
            "description": step.get("description", ""),
            "enabled": True,
            "timeout_ms": 60000,  # Default 60s per step
            "retry_count": 3,
            "error_action": error_action,
            "depends_on": [],  # Dependencies are resolved from YAML "depends_on"
            "correlation_id": correlation_id,
            "priority": 1,
        }

    async def process(
        self, input_data: ModelOrchestratorInput
    ) -> ModelOrchestratorOutput:
        """
        Process orchestration request using declarative workflow.

        Routes to appropriate workflow definition based on operation_type.
        Emits actions for downstream node execution.

        Args:
            input_data: Orchestrator input with operation type and payload

        Returns:
            ModelOrchestratorOutput with workflow results and emitted actions
        """
        workflow_id = f"wf_{uuid4().hex[:16]}"

        try:
            # Load workflow definition for operation type
            workflow_def = self._load_workflow_definition(input_data.operation_type)

            # Set workflow definition for parent class
            self.workflow_definition = workflow_def

            # Load raw config for step extraction
            workflow_files = {
                EnumOperationType.DOCUMENT_INGESTION: "document_ingestion.yaml",
                EnumOperationType.PATTERN_LEARNING: "pattern_learning.yaml",
                EnumOperationType.QUALITY_ASSESSMENT: "quality_assessment.yaml",
                EnumOperationType.SEMANTIC_ANALYSIS: "semantic_analysis.yaml",
                EnumOperationType.RELATIONSHIP_DETECTION: "relationship_detection.yaml",
            }
            workflow_path = _WORKFLOWS_DIR / workflow_files[input_data.operation_type]
            with open(workflow_path) as f:
                raw_config = yaml.safe_load(f)

            # Extract steps from config
            workflow_id_uuid = uuid4()
            steps_config = self._extract_steps_from_config(raw_config, input_data)

            # Create workflow steps from config
            workflow_steps = self.create_workflow_steps_from_config(steps_config)

            # Determine execution mode
            execution_mode = (
                EnumExecutionMode.PARALLEL
                if workflow_def.workflow_metadata.execution_mode == "parallel"
                else EnumExecutionMode.SEQUENTIAL
            )

            # Execute workflow using parent's declarative execution
            workflow_result = await self.execute_workflow_from_contract(
                workflow_def,
                workflow_steps,
                workflow_id_uuid,
                execution_mode=execution_mode,
            )

            # Convert actions to intents for the output model
            intents: list[ModelIntent] = []
            for action in workflow_result.actions_emitted:
                intent = ModelIntent(
                    intent_type=EnumIntentType.WORKFLOW_TRIGGER,
                    target=action.target_node_type,
                    payload={
                        "action_id": str(action.action_id),
                        "action_type": action.action_type.value,
                        "step_name": action.metadata.get("step_name", ""),
                        "workflow_id": str(workflow_id_uuid),
                    },
                    correlation_id=input_data.correlation_id,
                )
                intents.append(intent)

            return ModelOrchestratorOutput(
                success=workflow_result.execution_status.value == "completed",
                workflow_id=workflow_id,
                results={
                    "operation_type": input_data.operation_type.value,
                    "entity_id": input_data.entity_id,
                    "completed_steps": workflow_result.completed_steps,
                    "failed_steps": workflow_result.failed_steps,
                    "actions_emitted": len(workflow_result.actions_emitted),
                    "execution_time_ms": workflow_result.execution_time_ms,
                },
                intents=intents,
            )

        except FileNotFoundError as e:
            return ModelOrchestratorOutput(
                success=False,
                workflow_id=workflow_id,
                errors=[f"Workflow contract not found: {e}"],
            )

        except ValueError as e:
            return ModelOrchestratorOutput(
                success=False,
                workflow_id=workflow_id,
                errors=[f"Invalid operation type: {e}"],
            )

        except Exception as e:
            return ModelOrchestratorOutput(
                success=False,
                workflow_id=workflow_id,
                errors=[f"Workflow execution failed: {e!s}"],
            )
