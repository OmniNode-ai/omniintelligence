"""
ONEX Effect Node: Qdrant Vector Update

Updates vector payloads and optionally regenerates embeddings for existing
points in Qdrant collections.
"""

import logging
import time
from typing import Optional

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from ..base.node_base_effect import NodeBaseEffect
from ..contracts.qdrant_contracts import (
    ModelContractQdrantUpdateEffect,
    ModelQdrantUpdateResult,
)

logger = logging.getLogger(__name__)


class NodeQdrantUpdateEffect(NodeBaseEffect):
    """
    Updates a vector's payload and/or embedding in a Qdrant collection.

    Supports:
    - Metadata-only updates (no re-embedding)
    - Full updates with new embedding generation
    - Idempotent upsert operations
    """

    OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"

    def __init__(
        self,
        qdrant_client: AsyncQdrantClient,
        openai_client: AsyncOpenAI,
    ):
        """
        Initialize the update effect node.

        Args:
            qdrant_client: Async Qdrant client instance
            openai_client: Async OpenAI client instance
        """
        super().__init__()
        self.qdrant_client = qdrant_client
        self.openai_client = openai_client

    async def _generate_new_embedding(self, text: str) -> list[float]:
        """
        Generate new embedding for updated text.

        Args:
            text: Text to generate embedding for

        Returns:
            New embedding vector
        """
        start_time = time.perf_counter()
        embedding_response = await self.openai_client.embeddings.create(
            input=[text], model=self.OPENAI_EMBEDDING_MODEL
        )
        new_vector = embedding_response.data[0].embedding
        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.debug(f"Generated new embedding in {duration_ms:.2f}ms")
        self._record_metric("embedding_generation_ms", duration_ms)

        return new_vector

    async def execute_effect(
        self, contract: ModelContractQdrantUpdateEffect
    ) -> ModelQdrantUpdateResult:
        """
        Execute vector update operation.

        Payload Preservation Behavior:
        - If only payload provided: Updates payload using set_payload (safe)
        - If text_for_embedding + payload provided: Upserts with both
        - If only text_for_embedding provided: Fetches existing payload first,
          then upserts with new vector + preserved payload (prevents data loss)
        - If point doesn't exist: Creates new point with empty payload

        This ensures existing payload metadata is never accidentally cleared
        when regenerating embeddings.

        Args:
            contract: Update effect contract with point ID and update data

        Returns:
            Update result with status and performance metrics

        Raises:
            Exception: If update operation fails
        """
        logger.info(
            f"Executing Qdrant update effect for point '{contract.point_id}' "
            f"in collection '{contract.collection_name}'"
        )
        start_time = time.perf_counter()

        async with self.transaction_manager.begin():
            try:
                new_vector: Optional[list[float]] = None

                # Generate new embedding if text provided
                if contract.text_for_embedding:
                    logger.debug(
                        f"Generating new embedding for point '{contract.point_id}'"
                    )
                    new_vector = await self._generate_new_embedding(
                        contract.text_for_embedding
                    )

                # Perform update based on what's being updated
                update_start_time = time.perf_counter()

                if new_vector is not None:
                    # Update with new vector - use upsert
                    # CRITICAL: Preserve existing payload if not provided to prevent data loss
                    payload_to_use = contract.payload
                    if payload_to_use is None:
                        # Fetch existing payload to prevent overwriting with None
                        logger.debug(
                            f"Fetching existing payload for point '{contract.point_id}' "
                            "to preserve metadata during vector update"
                        )
                        existing_points = await self.qdrant_client.retrieve(
                            collection_name=contract.collection_name,
                            ids=[contract.point_id],
                            with_payload=True,
                        )
                        if existing_points and len(existing_points) > 0:
                            payload_to_use = existing_points[0].payload
                            logger.debug(
                                f"Preserved existing payload with {len(payload_to_use or {})} fields"
                            )
                        else:
                            # Point doesn't exist yet, use empty payload
                            payload_to_use = {}
                            logger.debug(
                                "Point not found, using empty payload for new point"
                            )

                    point_to_upsert = models.PointStruct(
                        id=contract.point_id,
                        vector=new_vector,
                        payload=payload_to_use,
                    )
                    update_result = await self.qdrant_client.upsert(
                        collection_name=contract.collection_name,
                        points=[point_to_upsert],
                        wait=True,  # Ensure operation completes before returning
                    )
                elif contract.payload is not None:
                    # Update only payload - use set_payload
                    update_result = await self.qdrant_client.set_payload(
                        collection_name=contract.collection_name,
                        payload=contract.payload,
                        points=[contract.point_id],
                        wait=True,
                    )
                else:
                    # Nothing to update
                    raise ValueError(
                        "Either text_for_embedding or payload must be provided"
                    )

                update_duration_ms = (time.perf_counter() - update_start_time) * 1000

                total_duration_ms = (time.perf_counter() - start_time) * 1000

                logger.info(
                    f"Successfully updated point '{contract.point_id}' in {total_duration_ms:.2f}ms. "
                    f"Status: {update_result.status.name}"
                )

                self._record_metric("update_duration_ms", update_duration_ms)
                self._record_metric("total_duration_ms", total_duration_ms)
                self._record_metric("regenerated_embedding", new_vector is not None)

                return ModelQdrantUpdateResult(
                    point_id=contract.point_id,
                    status=update_result.status.name,
                    operation_time_ms=total_duration_ms,
                )

            except Exception as e:
                logger.error(
                    f"Error during Qdrant update for point '{contract.point_id}': {e}",
                    exc_info=True,
                )
                raise
