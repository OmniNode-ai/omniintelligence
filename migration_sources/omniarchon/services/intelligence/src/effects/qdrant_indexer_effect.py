"""
Qdrant Indexer Effect Node

Handles vector indexing in Qdrant for semantic file search.
Implements batch indexing with configurable batch sizes.

ONEX Pattern: Effect (Database I/O)
Performance Target: <50ms per batch (100 files)
"""

import asyncio
import hashlib
import logging
import time
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from src.effects.base_effect import BaseEffect
from src.models.effect_result import EffectResult

logger = logging.getLogger(__name__)


class QdrantIndexerEffect(BaseEffect):
    """
    Effect node for indexing files in Qdrant vector database.

    Features:
    - Batch indexing (default: 100 points per batch)
    - Automatic collection creation
    - Deterministic point IDs (BLAKE2b hash of file path)
    - Configurable vector dimensions (default: 1536 for OpenAI embeddings)

    Examples:
        Single file indexing:
        >>> effect = QdrantIndexerEffect(qdrant_url="http://qdrant:6333")
        >>> result = await effect.execute({
        ...     "file_info": {"absolute_path": "/path/to/file.py", ...},
        ...     "embedding": [0.1, 0.2, ..., 0.9],  # 1536-dim vector
        ...     "collection_name": "archon_vectors"
        ... })

        Batch indexing:
        >>> result = await effect.execute({
        ...     "files": [
        ...         (file_info_1, embedding_1),
        ...         (file_info_2, embedding_2),
        ...         ...
        ...     ],
        ...     "collection_name": "archon_vectors",
        ...     "batch_size": 100
        ... })
    """

    def __init__(
        self,
        qdrant_url: str = "http://archon-qdrant:6333",
        vector_size: Optional[int] = None,
        distance: Distance = Distance.COSINE,
        batch_size: int = 100,
        **kwargs,
    ):
        """
        Initialize QdrantIndexerEffect.

        Args:
            qdrant_url: Qdrant service URL
            vector_size: Embedding vector dimensions (reads from EMBEDDING_DIMENSIONS env if not provided)
            distance: Distance metric (COSINE, DOT, EUCLID)
            batch_size: Batch size for indexing
            **kwargs: Additional base effect parameters
        """
        import os

        super().__init__(
            max_retries=3,
            retry_delay_ms=100.0,
            retry_backoff=2.0,
            **kwargs,
        )

        self.qdrant_url = qdrant_url
        # Read from environment if not explicitly provided
        self.vector_size = (
            vector_size
            if vector_size is not None
            else int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
        )
        self.distance = distance
        self.batch_size = batch_size
        self.client: Optional[QdrantClient] = None

        logger.debug(
            f"QdrantIndexerEffect initialized: url={qdrant_url}, "
            f"vector_size={vector_size}, batch_size={batch_size}"
        )

    def get_effect_name(self) -> str:
        """Get effect identifier."""
        return "QdrantIndexerEffect"

    def _initialize_client(self) -> None:
        """Initialize Qdrant client if not already initialized."""
        if not self.client:
            self.client = QdrantClient(url=self.qdrant_url)
            logger.debug("Qdrant client initialized")

    def _ensure_collection_exists(self, collection_name: str) -> None:
        """
        Ensure collection exists, create if not.

        Args:
            collection_name: Name of collection to check/create
        """
        try:
            self.client.get_collection(collection_name)
            logger.debug(f"Collection '{collection_name}' exists")
        except Exception:
            # Collection doesn't exist, create it
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=self.distance,
                ),
            )
            logger.info(
                f"✅ Created Qdrant collection: {collection_name} "
                f"(size={self.vector_size}, distance={self.distance.name})"
            )

    def _detect_language(
        self, file_extension: Optional[str] = None, file_path: Optional[str] = None
    ) -> str:
        """
        Detect programming language from file extension.

        Args:
            file_extension: File extension (e.g., "py", ".py")
            file_path: Full file path (used if extension not provided)

        Returns:
            Language name (e.g., "python", "javascript", "unknown")
        """
        if file_extension:
            ext = file_extension.lower().lstrip(".")
        elif file_path:
            ext = file_path.split(".")[-1].lower() if "." in file_path else ""
        else:
            return "unknown"

        language_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "tsx": "typescript",
            "jsx": "javascript",
            "java": "java",
            "cpp": "cpp",
            "c": "c",
            "go": "go",
            "rs": "rust",
            "rb": "ruby",
            "php": "php",
            "swift": "swift",
            "kt": "kotlin",
            "cs": "csharp",
            "md": "markdown",
            "txt": "text",
            "yaml": "yaml",
            "yml": "yaml",
            "json": "json",
            "toml": "toml",
            "sh": "bash",
            "sql": "sql",
        }
        return language_map.get(ext, ext or "unknown")

    async def execute(self, input_data: Dict[str, Any]) -> EffectResult:
        """
        Index files in Qdrant vector database.

        Input data format (batch):
        {
            "files": [
                (file_info_dict, embedding_vector),
                ...
            ],
            "collection_name": str,
            "project_name": str,
            "project_root": str,
            "batch_size": int (optional)
        }

        OR single file:
        {
            "file_info": file_info_dict,
            "embedding": embedding_vector,
            "collection_name": str,
            "project_name": str,
            "project_root": str
        }

        Args:
            input_data: File data, embeddings, and configuration

        Returns:
            EffectResult with indexing statistics
        """
        start_time = time.perf_counter()
        errors = []
        warnings = []
        indexed_count = 0

        try:
            # Initialize client
            self._initialize_client()

            # Extract parameters
            collection_name = input_data.get("collection_name", "archon_vectors")
            project_name = input_data.get("project_name")
            project_root = input_data.get("project_root")
            batch_size = input_data.get("batch_size", self.batch_size)

            # Ensure collection exists
            self._ensure_collection_exists(collection_name)

            # Handle single file or batch
            files = input_data.get("files")
            if not files:
                # Single file mode
                file_info = input_data.get("file_info")
                embedding = input_data.get("embedding")
                if file_info and embedding:
                    files = [(file_info, embedding)]
                else:
                    return EffectResult(
                        success=False,
                        items_processed=0,
                        duration_ms=(time.perf_counter() - start_time) * 1000,
                        errors=[
                            "No files provided (need 'files' or 'file_info' + 'embedding')"
                        ],
                    )

            # Process in batches
            total_files = len(files)
            for i in range(0, total_files, batch_size):
                batch = files[i : i + batch_size]
                batch_num = i // batch_size + 1

                try:
                    # Prepare points
                    points = []
                    for file_info, embedding in batch:
                        point = self._create_point(
                            file_info=file_info,
                            embedding=embedding,
                            project_name=project_name,
                            project_root=project_root,
                        )
                        if point:
                            points.append(point)

                    # Batch upsert (offload to thread to avoid blocking event loop)
                    if points:
                        await asyncio.to_thread(
                            self.client.upsert,
                            collection_name=collection_name,
                            points=points,
                            wait=True,
                        )

                        indexed_count += len(points)
                        logger.debug(
                            f"Batch {batch_num}: Indexed {len(points)} points in Qdrant"
                        )

                except Exception as e:
                    error_msg = f"Batch {batch_num} indexing failed: {e}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

            # Calculate results
            duration_ms = (time.perf_counter() - start_time) * 1000
            success = indexed_count > 0  # Partial success allowed

            logger.info(
                f"QdrantIndexerEffect: {indexed_count}/{total_files} files indexed "
                f"in {duration_ms:.1f}ms"
            )

            return EffectResult(
                success=success,
                items_processed=indexed_count,
                duration_ms=duration_ms,
                errors=errors,
                warnings=warnings,
                metadata={
                    "total_attempted": total_files,
                    "collection_name": collection_name,
                    "batch_size": batch_size,
                    "batches_processed": (total_files + batch_size - 1) // batch_size,
                },
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"QdrantIndexerEffect failed: {e}", exc_info=True)

            return EffectResult(
                success=False,
                items_processed=indexed_count,
                duration_ms=duration_ms,
                errors=[f"QdrantIndexerEffect failed: {e}"],
                warnings=warnings,
            )

    def _create_point(
        self,
        file_info: Dict[str, Any],
        embedding: List[float],
        project_name: Optional[str] = None,
        project_root: Optional[str] = None,
    ) -> Optional[PointStruct]:
        """
        Create Qdrant point from file info and embedding.

        Args:
            file_info: File metadata dictionary
            embedding: Embedding vector
            project_name: Project identifier
            project_root: Project root path

        Returns:
            PointStruct or None if creation failed
        """
        try:
            # Extract required fields
            absolute_path = file_info.get("absolute_path") or file_info.get("file_path")
            if not absolute_path:
                logger.warning("File info missing absolute_path")
                return None

            # Calculate relative path
            relative_path = file_info.get("relative_path")
            if not relative_path and project_root:
                relative_path = absolute_path.replace(project_root, "").lstrip("/")

            # Generate stable 64-bit int ID from file path (deterministic)
            point_id = int(
                hashlib.blake2b(absolute_path.encode(), digest_size=8).hexdigest(), 16
            )

            # Build payload
            metadata = file_info.get("metadata", {})
            payload = {
                "absolute_path": absolute_path,
                "relative_path": relative_path or "",
                "project_name": project_name or file_info.get("project_name", ""),
                "project_root": project_root or file_info.get("project_root", ""),
                "document_id": file_info.get("document_id"),
                "language": self._detect_language(
                    metadata.get("file_extension"), absolute_path
                ),
                "quality_score": (
                    metadata.get("quality_score") or file_info.get("quality_score", 0.0)
                ),
                "onex_compliance": (
                    metadata.get("onex_compliance")
                    or file_info.get("onex_compliance", 0.0)
                ),
                "onex_type": (metadata.get("onex_type") or file_info.get("onex_type")),
                "concepts": metadata.get("concepts") or file_info.get("concepts", []),
                "themes": metadata.get("themes") or file_info.get("themes", []),
                "indexed_at": datetime.now(UTC).isoformat(),
            }

            # Create point
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload,
            )

            return point

        except Exception as e:
            logger.warning(f"Failed to create point for {file_info}: {e}")
            return None

    async def index_file(
        self,
        file_info: Dict[str, Any],
        embedding: List[float],
        collection_name: str = "archon_vectors",
    ) -> bool:
        """
        Index single file in Qdrant.

        Convenience method for single file indexing.

        Args:
            file_info: File metadata
            embedding: Embedding vector
            collection_name: Collection name

        Returns:
            True if successful, False otherwise
        """
        result = await self.execute(
            {
                "file_info": file_info,
                "embedding": embedding,
                "collection_name": collection_name,
            }
        )

        return result.success and result.items_processed > 0

    async def batch_index(
        self,
        files: List[Tuple[Dict[str, Any], List[float]]],
        collection_name: str = "archon_vectors",
        project_name: Optional[str] = None,
        project_root: Optional[str] = None,
    ) -> int:
        """
        Batch index multiple files.

        Convenience method for batch indexing.

        Args:
            files: List of (file_info, embedding) tuples
            collection_name: Collection name
            project_name: Project identifier
            project_root: Project root path

        Returns:
            Number of files successfully indexed
        """
        result = await self.execute(
            {
                "files": files,
                "collection_name": collection_name,
                "project_name": project_name,
                "project_root": project_root,
            }
        )

        return result.items_processed

    async def cleanup(self) -> None:
        """Close Qdrant client connection."""
        if self.client:
            try:
                self.client.close()
                self.client = None
                logger.debug("Qdrant client closed")
            except Exception as e:
                logger.warning(f"Error closing Qdrant client: {e}")


__all__ = ["QdrantIndexerEffect"]
