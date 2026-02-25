# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""NodeScoringReducerCompute — deterministic gate + shaped reward evaluation.

This node implements the core objective-function evaluation unit described in
the OMN-2361 design doc (Section 6).

It is a COMPUTE node: pure, deterministic, zero I/O, zero side effects.

Pipeline:
    1. Stage 1 — Hard gates: all gates in ObjectiveSpec must pass.
       Any single gate failure → failed EvaluationResult, ScoreVector.zero().
    2. Stage 2 — Shaped reward: weighted terms contributing to ScoreVector
       dimensions. minimize-direction terms invert the evidence value.

Public API:
    ``evaluate_run(evidence, spec) -> EvaluationResult``

Replay invariant: identical inputs → bit-identical outputs (enforced by tests).

Does NOT:
    - Read from or write to any database
    - Produce Kafka events
    - Access the filesystem
    - Maintain state between calls

Related:
    - OMN-2537: Core data models (ObjectiveSpec, ScoreVector, EvidenceBundle)
    - OMN-2361: Objective Functions and Reward Architecture epic
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_scoring_reducer_compute.handlers.handler_scoring import (
    evaluate_run,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_scoring_input import (
    ModelScoringInput,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_scoring_output import (
    ModelScoringOutput,
)


class NodeScoringReducerCompute(NodeCompute[ModelScoringInput, ModelScoringOutput]):
    """Pure COMPUTE node for objective-function evaluation.

    Evaluates an EvidenceBundle against an ObjectiveSpec in two stages:
      1. Hard gates — all must pass for the run to be considered valid.
      2. Shaped reward — weighted ScoreVector computation (only on gate pass).

    This node is a thin declarative shell. All computation is delegated to
    ``evaluate_run`` in the handler module.

    Example:
        ```python
        from omniintelligence.nodes.node_scoring_reducer_compute.handlers import (
            evaluate_run,
        )

        result = evaluate_run(evidence=bundle, spec=objective_spec)
        if result.passed:
            print(f"Score: {result.score_vector}")
        else:
            print(f"Failed gates: {result.failures}")
        ```
    """

    async def compute(self, input_data: ModelScoringInput) -> ModelScoringOutput:
        """Evaluate evidence against objective spec.

        Delegates entirely to the pure ``evaluate_run`` handler.
        """
        result = evaluate_run(
            evidence=input_data.evidence,
            spec=input_data.spec,
        )
        return ModelScoringOutput(
            result=result,
            objective_id=input_data.spec.objective_id,
            objective_version=input_data.spec.version,
            run_id=input_data.evidence.run_id,
        )


__all__ = ["NodeScoringReducerCompute"]
