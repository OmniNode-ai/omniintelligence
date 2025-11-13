"""
ONEX Effect Node: Qdrant Semantic Search

Performs high-performance semantic similarity search in Qdrant with <100ms
response time for 10K vectors.
"""

import logging
import time
from typing import Optional

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from ..base.node_base_effect import NodeBaseEffect
from ..contracts.qdrant_contracts import (
    ModelContractQdrantSearchEffect,
    ModelQdrantHit,
    ModelQdrantSearchResult,
)

logger = logging.getLogger(__name__)


class NodeQdrantSearchEffect(NodeBaseEffect):
    """
    Performs semantic vector search in a Qdrant collection.

    Performance Targets:
    - <100ms search latency for 10K vectors
    - Configurable HNSW search parameters for speed/accuracy trade-off
    - Support for filters and score thresholds
    """

    OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"

    def __init__(
        self,
        qdrant_client: AsyncQdrantClient,
        openai_client: AsyncOpenAI,
    ):
        """
        Initialize the search effect node.

        Args:
            qdrant_client: Async Qdrant client instance
            openai_client: Async OpenAI client instance
        """
        super().__init__()
        self.qdrant_client = qdrant_client
        self.openai_client = openai_client

    async def _get_query_embedding(self, query_text: str) -> list[float]:
        """
        Generate embedding for query text.

        Args:
            query_text: Text to generate embedding for

        Returns:
            Query embedding vector
        """
        start_time = time.perf_counter()
        embedding_response = await self.openai_client.embeddings.create(
            input=[query_text], model=self.OPENAI_EMBEDDING_MODEL
        )
        query_vector = embedding_response.data[0].embedding
        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.debug(f"Generated query embedding in {duration_ms:.2f}ms")
        self._record_metric("embedding_generation_ms", duration_ms)

        return query_vector

    async def execute_effect(
        self, contract: ModelContractQdrantSearchEffect
    ) -> ModelQdrantSearchResult:
        """
        Execute semantic similarity search in Qdrant.

        Args:
            contract: Search effect contract with query text and parameters

        Returns:
            Search results with hits and performance metrics

        Raises:
            Exception: If search operation fails
        """
        logger.info(
            f"Executing Qdrant search effect for collection '{contract.collection_name}' "
            f"with query: '{contract.query_text[:50]}...'"
        )
        start_time = time.perf_counter()

        async with self.transaction_manager.begin():
            try:
                # 1. Generate query embedding
                query_vector = await self._get_query_embedding(contract.query_text)

                # 2. Construct search parameters
                search_params: Optional[models.SearchParams] = None
                if contract.search_params and "hnsw_ef" in contract.search_params:
                    search_params = models.SearchParams(
                        hnsw_ef=contract.search_params["hnsw_ef"]
                    )

                # 3. Construct filters if provided
                query_filter: Optional[models.Filter] = None
                if contract.filters:
                    # Convert dict filters to Qdrant Filter model
                    # This is a simplified version - extend as needed
                    query_filter = models.Filter(**contract.filters)

                # 4. Perform search
                search_start_time = time.perf_counter()
                search_result = await self.qdrant_client.search(
                    collection_name=contract.collection_name,
                    query_vector=query_vector,
                    query_filter=query_filter,
                    limit=contract.limit,
                    score_threshold=contract.score_threshold,
                    search_params=search_params,
                    with_payload=True,
                )
                search_duration_ms = (time.perf_counter() - search_start_time) * 1000

                # 5. Format results
                hits = [
                    ModelQdrantHit(
                        id=point.id, score=point.score, payload=point.payload
                    )
                    for point in search_result
                ]

                total_duration_ms = (time.perf_counter() - start_time) * 1000

                logger.info(
                    f"Qdrant search completed in {total_duration_ms:.2f}ms "
                    f"(search: {search_duration_ms:.2f}ms), found {len(hits)} results"
                )

                self._record_metric("search_duration_ms", search_duration_ms)
                self._record_metric("total_duration_ms", total_duration_ms)
                self._record_metric("results_count", len(hits))

                return ModelQdrantSearchResult(
                    hits=hits, search_time_ms=total_duration_ms, total_results=len(hits)
                )

            except Exception as e:
                logger.error(
                    f"Error during Qdrant search on collection '{contract.collection_name}': {e}",
                    exc_info=True,
                )
                raise
