# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""NodePlanReviewerMultiCompute — thin shell for multi-LLM plan review.

This node follows the ONEX thin-shell pattern: it contains no logic,
no error handling beyond what the framework provides, no logging.
All computation is delegated to ``handle_plan_reviewer_multi_compute``.

Usage (direct handler invocation — recommended for callers)::

    from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers import (
        handle_plan_reviewer_multi_compute,
    )
    from omniintelligence.nodes.node_plan_reviewer_multi_compute.models import (
        ModelPlanReviewerMultiCommand,
        EnumReviewStrategy,
    )

    output = await handle_plan_reviewer_multi_compute(
        command=ModelPlanReviewerMultiCommand(
            plan_text="## Plan\\n1. Step one\\n2. Step two",
            strategy=EnumReviewStrategy.S4_INDEPENDENT_MERGE,
            run_id="OMN-1234",
        ),
        model_callers={...},
        db_conn=pool_conn,
    )

Ticket: OMN-3290
"""

from __future__ import annotations

from omnibase_core.models.container.model_onex_container import ModelONEXContainer
from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.handler_confidence_scorer import (
    ProtocolDBConnection,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.handler_plan_reviewer_multi_compute import (
    ModelCaller,
    handle_plan_reviewer_multi_compute,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.strategies.handler_sequential_critique import (
    CriticCaller,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_reviewer_multi_input import (
    ModelPlanReviewerMultiCommand,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_reviewer_multi_output import (
    ModelPlanReviewerMultiOutput,
)


class NodePlanReviewerMultiCompute(
    NodeCompute[ModelPlanReviewerMultiCommand, ModelPlanReviewerMultiOutput]
):
    """Thin shell for the multi-LLM plan reviewer compute node.

    Delegates all logic to ``handle_plan_reviewer_multi_compute``.
    Model callers and the optional DB connection are injected at
    construction time via ``set_model_callers`` / ``set_db_conn``.

    Attributes:
        _model_callers: Mapping of model ID → LLM caller callable.
            Injected before calling ``compute``.
        _db_conn: Optional asyncpg-compatible connection for audit writes.
        _critic_caller: Optional S3 critic callable.

    Example::

        node = NodePlanReviewerMultiCompute(container)
        node.set_model_callers({
            EnumReviewModel.QWEN3_CODER: my_qwen_caller,
            EnumReviewModel.DEEPSEEK_R1: my_deepseek_caller,
            EnumReviewModel.GEMINI_FLASH: my_gemini_caller,
            EnumReviewModel.GLM_4: my_glm_caller,
        })
        node.set_db_conn(pool_conn)
        output = await node.compute(command)
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        """Initialise the node shell with injected callers placeholder."""
        super().__init__(container)
        self._model_callers: dict[EnumReviewModel, ModelCaller] = {}
        self._db_conn: ProtocolDBConnection | None = None
        self._critic_caller: CriticCaller | None = None

    def set_model_callers(self, callers: dict[EnumReviewModel, ModelCaller]) -> None:
        """Inject the per-model LLM caller map.

        Args:
            callers: Mapping of ``EnumReviewModel`` → async callable.
        """
        self._model_callers = callers

    def set_db_conn(self, conn: ProtocolDBConnection | None) -> None:
        """Inject the optional DB connection for audit writes.

        Args:
            conn: asyncpg-compatible connection, or ``None`` to skip DB.
        """
        self._db_conn = conn

    def set_critic_caller(self, critic: CriticCaller | None) -> None:
        """Inject the S3 critic caller.

        Args:
            critic: Async callable for S3 sequential_critique, or ``None``.
        """
        self._critic_caller = critic

    async def compute(
        self, input_data: ModelPlanReviewerMultiCommand
    ) -> ModelPlanReviewerMultiOutput:
        """Run the multi-LLM plan review.

        Thin delegation — all logic lives in the handler.

        Args:
            input_data: Frozen command with plan text, strategy, and options.

        Returns:
            ``ModelPlanReviewerMultiOutput`` with findings and DB status.
        """
        return await handle_plan_reviewer_multi_compute(
            command=input_data,
            model_callers=self._model_callers,
            db_conn=self._db_conn,
            critic_caller=self._critic_caller,
        )


__all__ = ["NodePlanReviewerMultiCompute"]
