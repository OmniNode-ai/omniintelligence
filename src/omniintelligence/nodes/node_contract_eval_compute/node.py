# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node NodeContractEvalCompute — two-layer contract LLM judge.

Compute node. Orchestrates hard validators (schema, trace_coverage,
reference_integrity) followed by LLM soft evaluation (DeepSeek-R1 judge).

Both layers always run independently. eval_passed is False when schema
validation fails regardless of LLM judge scores.

This node follows the ONEX declarative pattern:
    - DECLARATIVE compute driven by contract.yaml
    - Handler dispatch defined in contract.yaml handler_routing
    - Thin shell — all logic in handler_contract_eval

Does NOT:
    - Perform direct LLM calls (judge_caller is injected)
    - Perform any file I/O
    - Manage http connections

Related:
    - OMN-4024: This node implementation
    - OMN-4023: Hard validators (handlers/validators.py)
    - OMN-4016: Bloom eval framework parent epic
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute


class NodeContractEvalCompute(NodeCompute):  # type: ignore[type-arg]
    """Declarative compute node for two-layer contract evaluation.

    This node is a pure declarative shell. All handler dispatch is defined
    in contract.yaml via ``handler_routing``. The node itself contains NO
    custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - evaluate_contract: run hard validators then LLM judge

    Example:
        ```python
        from omniintelligence.nodes.node_contract_eval_compute.handlers.handler_contract_eval import (
            handle_contract_evaluation,
        )
        from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
            ModelEvalScenario,
        )
        from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
            EnumFailureMode,
        )
        import asyncio
        from uuid import uuid4

        scenario = ModelEvalScenario(
            spec_id=uuid4(),
            failure_mode=EnumFailureMode.REQUIREMENT_OMISSION,
            input_text="Generate a contract for a Kafka consumer node.",
            context={},
        )

        async def mock_judge(prompt, output, indicators):
            return {
                "metamorphic_stability_score": 0.9,
                "compliance_theater_risk": 0.1,
                "ambiguity_flags": [],
                "invented_requirements": [],
                "missing_acceptance_criteria": [],
            }

        result = asyncio.run(
            handle_contract_evaluation(
                contract_dict={
                    "node_type": "COMPUTE_GENERIC",
                    "contract_id": "test-001",
                    "title": "Test Contract",
                    "description": "A test contract.",
                    "io": {},
                    "environment_variables": [],
                },
                scenario=scenario,
                ticket_requirements=["A test contract"],
                judge_caller=mock_judge,
            )
        )
        assert result.schema_pass is True
        ```
    """

    # Pure declarative shell — all behavior defined in contract.yaml


__all__ = ["NodeContractEvalCompute"]
