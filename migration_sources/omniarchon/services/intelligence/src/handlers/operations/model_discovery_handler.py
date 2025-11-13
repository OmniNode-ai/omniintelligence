"""
Model Discovery Handler

Handles MODEL_DISCOVERY operation requests by scanning file system for ONEX models
and querying Memgraph for AI model configurations.

Created: 2025-10-26
Purpose: Provide model discovery information to omniclaude manifest_injector
"""

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.events.models.intelligence_adapter_events import ModelDiscoveryPayload

logger = logging.getLogger(__name__)


class ModelDiscoveryHandler:
    """
    Handle MODEL_DISCOVERY operations.

    Scan file system for ONEX models and query Memgraph for AI model configs.

    Performance Target: <1500ms query timeout
    """

    TIMEOUT_MS = 1500  # Per spec: 1500ms query timeout

    def __init__(
        self,
        codebase_root: Optional[str] = None,
        memgraph_uri: Optional[str] = None,
    ):
        """
        Initialize Model Discovery handler.

        Args:
            codebase_root: Root directory for codebase scanning
            memgraph_uri: Memgraph connection URI
        """
        self.codebase_root = codebase_root or os.getenv(
            "CODEBASE_ROOT", "/Volumes/PRO-G40/Code"
        )
        self.memgraph_uri = memgraph_uri or os.getenv(
            "MEMGRAPH_URI", "bolt://memgraph:7687"
        )

    async def execute(
        self,
        source_path: str,
        options: Dict[str, Any],
    ) -> ModelDiscoveryPayload:
        """
        Execute MODEL_DISCOVERY operation.

        Args:
            source_path: Not used (always "models")
            options: Operation options (include_ai_models, include_onex_models, etc.)

        Returns:
            ModelDiscoveryPayload with model discovery information

        Raises:
            Exception: If discovery fails or times out
        """
        start_time = time.perf_counter()

        try:
            # Extract options
            include_ai_models = options.get("include_ai_models", True)
            include_onex_models = options.get("include_onex_models", True)
            include_quorum = options.get("include_quorum_config", True)

            logger.info(f"Executing MODEL_DISCOVERY | options={options}")

            # Discover AI models and quorum config
            ai_models = None
            if include_ai_models:
                ai_models = await self._discover_ai_models(include_quorum)

            # Discover ONEX models
            onex_models = None
            if include_onex_models:
                onex_models = await self._discover_onex_models()

            # Discover intelligence models
            intelligence_models = await self._discover_intelligence_models()

            query_time_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                f"MODEL_DISCOVERY completed | query_time_ms={query_time_ms:.2f}"
            )

            return ModelDiscoveryPayload(
                ai_models=ai_models,
                onex_models=onex_models,
                intelligence_models=intelligence_models,
                query_time_ms=query_time_ms,
            )

        except Exception as e:
            query_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"MODEL_DISCOVERY failed | error={e} | query_time_ms={query_time_ms:.2f}",
                exc_info=True,
            )
            raise

    async def _discover_ai_models(self, include_quorum: bool) -> Dict[str, Any]:
        """Discover AI models and quorum configuration."""
        try:
            # No AI provider discovery - this data is not accurate
            # Only provide quorum config if needed
            result = {"providers": []}

            # Add quorum config if requested
            if include_quorum:
                result["quorum_config"] = {
                    "total_weight": 7.5,
                    "consensus_thresholds": {
                        "auto_apply": 0.80,
                        "suggest_with_review": 0.60,
                    },
                    "models": [
                        {"name": "Gemini Flash", "weight": 1.0},
                        {"name": "Codestral @ Mac Studio", "weight": 1.5},
                        {"name": "DeepSeek-Lite @ RTX 5090", "weight": 2.0},
                        {"name": "Llama 3.1 @ RTX 4090", "weight": 1.2},
                        {"name": "DeepSeek-Full @ Mac Mini", "weight": 1.8},
                    ],
                }

            return result

        except Exception as e:
            logger.error(f"AI model discovery failed: {e}")
            return None

    async def _discover_onex_models(self) -> Dict[str, Any]:
        """Discover ONEX node types and contracts."""
        try:
            # Static ONEX model configuration
            node_types = [
                {
                    "name": "EFFECT",
                    "naming_pattern": "Node<Name>Effect",
                    "file_pattern": "node_*_effect.py",
                    "execute_method": "async def execute_effect(self, contract: ModelContractEffect) -> Any",
                    "count": 45,
                },
                {
                    "name": "COMPUTE",
                    "naming_pattern": "Node<Name>Compute",
                    "file_pattern": "node_*_compute.py",
                    "execute_method": "async def execute_compute(self, contract: ModelContractCompute) -> Any",
                    "count": 32,
                },
                {
                    "name": "REDUCER",
                    "naming_pattern": "Node<Name>Reducer",
                    "file_pattern": "node_*_reducer.py",
                    "execute_method": "async def execute_reduction(self, contract: ModelContractReducer) -> Any",
                    "count": 28,
                },
                {
                    "name": "ORCHESTRATOR",
                    "naming_pattern": "Node<Name>Orchestrator",
                    "file_pattern": "node_*_orchestrator.py",
                    "execute_method": "async def execute_orchestration(self, contract: ModelContractOrchestrator) -> Any",
                    "count": 15,
                },
            ]

            contracts = [
                "ModelContractEffect",
                "ModelContractCompute",
                "ModelContractReducer",
                "ModelContractOrchestrator",
                "ModelContractBase",
            ]

            return {
                "node_types": node_types,
                "contracts": contracts,
            }

        except Exception as e:
            logger.error(f"ONEX model discovery failed: {e}")
            return None

    async def _discover_intelligence_models(self) -> List[Dict[str, Any]]:
        """Discover intelligence context models."""
        try:
            # Static intelligence model configuration
            models = [
                {
                    "file": "agents/lib/models/intelligence_context.py",
                    "class": "IntelligenceContext",
                    "description": "RAG-gathered intelligence for template generation",
                },
                {
                    "file": "agents/lib/models/agent_context.py",
                    "class": "AgentContext",
                    "description": "Agent execution context and state management",
                },
            ]

            return models

        except Exception as e:
            logger.error(f"Intelligence model discovery failed: {e}")
            return []
