"""
Haystack Adapter Effect Node

Adapts Haystack RAG pipelines for the ONEX architecture.
Provides standardized interface for Haystack document ingestion, indexing, and retrieval.
Supports feature flag-based A/B testing against custom RAG orchestration.
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from omnibase_core.node import NodeOmniAgentEffect
from haystack import Pipeline, Document
from haystack.components.embedders import OpenAIDocumentEmbedder, OpenAITextEmbedder
from haystack.components.writers import DocumentWriter
from haystack.components.retrievers import QdrantEmbeddingRetriever
from haystack.components.generators import OpenAIGenerator
from haystack.components.builders import PromptBuilder
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore

from .models import (
    ModelHaystackAdapterInput,
    ModelHaystackAdapterOutput,
    ModelHaystackAdapterConfig,
)


class HaystackAdapterEffect(NodeOmniAgentEffect[
    ModelHaystackAdapterInput,
    ModelHaystackAdapterOutput,
    ModelHaystackAdapterConfig
]):
    """
    Effect node that adapts Haystack RAG for ONEX.

    Handles:
    - Document ingestion and indexing
    - Semantic search and retrieval
    - RAG query with answer generation
    - Document deletion

    Uses Haystack 2.x pipelines with Qdrant for vector storage.
    """

    def __init__(self, config: ModelHaystackAdapterConfig):
        """Initialize Haystack adapter with configuration."""
        super().__init__(config)
        self.config = config

        # Initialize document store
        self._document_store: Optional[QdrantDocumentStore] = None

        # Pipelines
        self._indexing_pipeline: Optional[Pipeline] = None
        self._query_pipeline: Optional[Pipeline] = None
        self._search_pipeline: Optional[Pipeline] = None

    async def initialize(self):
        """Initialize Haystack pipelines and document store."""
        # Initialize Qdrant document store
        self._document_store = QdrantDocumentStore(
            url=self.config.qdrant_url,
            index=self.config.collection_name,
            embedding_dim=1536,  # OpenAI embedding dimension
            recreate_index=False,
        )

        # Create indexing pipeline
        self._indexing_pipeline = Pipeline()
        self._indexing_pipeline.add_component(
            "embedder",
            OpenAIDocumentEmbedder(model=self.config.embedding_model)
        )
        self._indexing_pipeline.add_component(
            "writer",
            DocumentWriter(document_store=self._document_store)
        )
        self._indexing_pipeline.connect("embedder", "writer")

        # Create search pipeline (retrieval only)
        self._search_pipeline = Pipeline()
        self._search_pipeline.add_component(
            "embedder",
            OpenAITextEmbedder(model=self.config.embedding_model)
        )
        self._search_pipeline.add_component(
            "retriever",
            QdrantEmbeddingRetriever(
                document_store=self._document_store,
                top_k=self.config.default_top_k
            )
        )
        self._search_pipeline.connect("embedder.embedding", "retriever.query_embedding")

        # Create RAG query pipeline (retrieval + generation)
        prompt_template = """
        You are a helpful AI assistant. Answer the question based on the provided context.
        If the context doesn't contain enough information, say so clearly.

        Context:
        {% for doc in documents %}
        {{ doc.content }}
        ---
        {% endfor %}

        Question: {{ question }}

        Answer:
        """

        self._query_pipeline = Pipeline()
        self._query_pipeline.add_component(
            "embedder",
            OpenAITextEmbedder(model=self.config.embedding_model)
        )
        self._query_pipeline.add_component(
            "retriever",
            QdrantEmbeddingRetriever(
                document_store=self._document_store,
                top_k=self.config.default_top_k
            )
        )
        self._query_pipeline.add_component(
            "prompt_builder",
            PromptBuilder(template=prompt_template)
        )
        self._query_pipeline.add_component(
            "generator",
            OpenAIGenerator(
                model=self.config.llm_model,
                generation_kwargs={
                    "temperature": self.config.llm_temperature,
                    "max_tokens": self.config.llm_max_tokens,
                }
            )
        )

        # Connect components
        self._query_pipeline.connect("embedder.embedding", "retriever.query_embedding")
        self._query_pipeline.connect("retriever.documents", "prompt_builder.documents")
        self._query_pipeline.connect("prompt_builder.prompt", "generator.prompt")

    async def shutdown(self):
        """Shutdown Haystack pipelines and connections."""
        # Clean up resources
        self._document_store = None
        self._indexing_pipeline = None
        self._query_pipeline = None
        self._search_pipeline = None

    async def process(self, input_data: ModelHaystackAdapterInput) -> ModelHaystackAdapterOutput:
        """
        Process Haystack adapter operation.

        Routes to appropriate handler based on operation type:
        - index_document: Index a document
        - query: RAG query with generation
        - search: Retrieval only
        - delete_document: Delete a document
        """
        start_time = time.time()

        try:
            # Route to operation handler
            if input_data.operation == "index_document":
                result = await self._index_document(input_data)
            elif input_data.operation == "query":
                result = await self._query(input_data)
            elif input_data.operation == "search":
                result = await self._search(input_data)
            elif input_data.operation == "delete_document":
                result = await self._delete_document(input_data)
            else:
                latency_ms = (time.time() - start_time) * 1000
                return ModelHaystackAdapterOutput(
                    success=False,
                    operation=input_data.operation,
                    latency_ms=latency_ms,
                    error=f"Unknown operation: {input_data.operation}",
                )

            # Add total latency
            result.latency_ms = (time.time() - start_time) * 1000
            return result

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return ModelHaystackAdapterOutput(
                success=False,
                operation=input_data.operation,
                latency_ms=latency_ms,
                error=str(e),
            )

    async def _index_document(self, input_data: ModelHaystackAdapterInput) -> ModelHaystackAdapterOutput:
        """Index a document in Haystack."""
        if not input_data.document_content:
            return ModelHaystackAdapterOutput(
                success=False,
                operation="index_document",
                latency_ms=0,
                error="document_content is required for index_document operation",
            )

        # Create Haystack document
        doc = Document(
            content=input_data.document_content,
            id=input_data.document_id,
            meta=input_data.metadata or {},
        )

        # Run indexing pipeline
        result = self._indexing_pipeline.run({
            "embedder": {"documents": [doc]}
        })

        return ModelHaystackAdapterOutput(
            success=True,
            operation="index_document",
            document_id=input_data.document_id,
            indexed=True,
            latency_ms=0,  # Will be set by caller
            metadata={"documents_written": result.get("writer", {}).get("documents_written", 0)},
        )

    async def _query(self, input_data: ModelHaystackAdapterInput) -> ModelHaystackAdapterOutput:
        """Execute RAG query with retrieval and generation."""
        if not input_data.query:
            return ModelHaystackAdapterOutput(
                success=False,
                operation="query",
                latency_ms=0,
                error="query is required for query operation",
            )

        retrieval_start = time.time()

        # Run RAG pipeline
        result = self._query_pipeline.run({
            "embedder": {"text": input_data.query},
            "prompt_builder": {"question": input_data.query},
        })

        retrieval_latency = (time.time() - retrieval_start) * 1000

        generation_start = time.time()
        # Extract results
        documents = result.get("retriever", {}).get("documents", [])
        replies = result.get("generator", {}).get("replies", [])
        answer = replies[0] if replies else None

        generation_latency = (time.time() - generation_start) * 1000

        # Format retrieved documents
        retrieved_docs = [
            {
                "id": doc.id,
                "content": doc.content,
                "score": doc.score,
                "metadata": doc.meta,
            }
            for doc in documents
        ]

        return ModelHaystackAdapterOutput(
            success=True,
            operation="query",
            query=input_data.query,
            answer=answer,
            retrieved_documents=retrieved_docs,
            latency_ms=0,  # Will be set by caller
            retrieval_latency_ms=retrieval_latency,
            generation_latency_ms=generation_latency,
            metadata={
                "num_documents_retrieved": len(documents),
                "generation_model": self.config.llm_model,
            },
        )

    async def _search(self, input_data: ModelHaystackAdapterInput) -> ModelHaystackAdapterOutput:
        """Execute semantic search without generation."""
        if not input_data.query:
            return ModelHaystackAdapterOutput(
                success=False,
                operation="search",
                latency_ms=0,
                error="query is required for search operation",
            )

        # Run search pipeline
        result = self._search_pipeline.run({
            "embedder": {"text": input_data.query},
        })

        # Extract documents
        documents = result.get("retriever", {}).get("documents", [])

        # Format retrieved documents
        retrieved_docs = [
            {
                "id": doc.id,
                "content": doc.content,
                "score": doc.score,
                "metadata": doc.meta,
            }
            for doc in documents
        ]

        return ModelHaystackAdapterOutput(
            success=True,
            operation="search",
            query=input_data.query,
            retrieved_documents=retrieved_docs,
            latency_ms=0,  # Will be set by caller
            metadata={"num_documents_retrieved": len(documents)},
        )

    async def _delete_document(self, input_data: ModelHaystackAdapterInput) -> ModelHaystackAdapterOutput:
        """Delete a document from Haystack."""
        if not input_data.document_id:
            return ModelHaystackAdapterOutput(
                success=False,
                operation="delete_document",
                latency_ms=0,
                error="document_id is required for delete_document operation",
            )

        # Delete from document store
        self._document_store.delete_documents([input_data.document_id])

        return ModelHaystackAdapterOutput(
            success=True,
            operation="delete_document",
            document_id=input_data.document_id,
            deleted=True,
            latency_ms=0,  # Will be set by caller
        )
