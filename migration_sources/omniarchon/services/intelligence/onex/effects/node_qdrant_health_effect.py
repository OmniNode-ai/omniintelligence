"""
ONEX Effect Node: Qdrant Collection Health

Retrieves health status and statistics for Qdrant collections including
vector counts, indexing status, and configuration details.
"""

import logging
import time
from typing import List

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import CollectionInfo

from ..base.node_base_effect import NodeBaseEffect
from ..contracts.qdrant_contracts import (
    ModelContractQdrantHealthEffect,
    ModelQdrantCollectionInfo,
    ModelQdrantHealthResult,
)

logger = logging.getLogger(__name__)


class NodeQdrantHealthEffect(NodeBaseEffect):
    """
    Retrieves health and statistics for Qdrant collections.

    Provides:
    - Service availability check
    - Collection statistics (point counts, indexing status)
    - Configuration details
    - Performance metrics
    """

    def __init__(self, qdrant_client: AsyncQdrantClient):
        """
        Initialize the health check effect node.

        Args:
            qdrant_client: Async Qdrant client instance
        """
        super().__init__()
        self.qdrant_client = qdrant_client

    async def _get_collection_info(self, name: str) -> ModelQdrantCollectionInfo:
        """
        Fetch and parse info for a single collection.

        Args:
            name: Collection name

        Returns:
            Collection information model

        Raises:
            Exception: If collection info retrieval fails
        """
        info: CollectionInfo = await self.qdrant_client.get_collection(
            collection_name=name
        )

        return ModelQdrantCollectionInfo(
            name=name,
            points_count=info.points_count or 0,
            vectors_count=info.vectors_count or 0,
            indexed_vectors_count=info.indexed_vectors_count or 0,
            configuration=info.config.model_dump() if info.config else {},
        )

    async def execute_effect(
        self, contract: ModelContractQdrantHealthEffect
    ) -> ModelQdrantHealthResult:
        """
        Execute health check operation.

        Args:
            contract: Health check contract specifying collection(s) to check

        Returns:
            Health result with service status and collection information

        Note:
            Returns service_ok=False instead of raising on failure to allow
            graceful degradation in health check scenarios.
        """
        logger.info("Executing Qdrant health effect")
        start_time = time.perf_counter()

        collections_info: List[ModelQdrantCollectionInfo] = []
        service_ok = False

        async with self.transaction_manager.begin():
            try:
                if contract.collection_name:
                    # Get info for a single collection
                    logger.debug(
                        f"Checking health for collection '{contract.collection_name}'"
                    )
                    info = await self._get_collection_info(contract.collection_name)
                    collections_info.append(info)
                else:
                    # Get info for all collections
                    logger.debug("Checking health for all collections")
                    collections_response = await self.qdrant_client.get_collections()

                    for collection in collections_response.collections:
                        info = await self._get_collection_info(collection.name)
                        collections_info.append(info)

                service_ok = True
                total_duration_ms = (time.perf_counter() - start_time) * 1000

                logger.info(
                    f"Qdrant health check successful in {total_duration_ms:.2f}ms. "
                    f"Found info for {len(collections_info)} collection(s)."
                )

                self._record_metric("health_check_duration_ms", total_duration_ms)
                self._record_metric("collections_checked", len(collections_info))

            except Exception as e:
                logger.error(f"Error during Qdrant health check: {e}", exc_info=True)
                # Don't re-raise; return failure status in result
                total_duration_ms = (time.perf_counter() - start_time) * 1000
                return ModelQdrantHealthResult(
                    service_ok=False, collections=[], response_time_ms=total_duration_ms
                )

        return ModelQdrantHealthResult(
            service_ok=service_ok,
            collections=collections_info,
            response_time_ms=total_duration_ms,
        )
