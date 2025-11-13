"""
Document Chunking Utility

Handles automatic chunking of large documents to prevent embedding service errors.
Uses tiktoken for accurate token counting and semantic chunking for logical splits.
"""

import logging
from typing import List, Optional

import tiktoken
from semchunk import chunkerify

logger = logging.getLogger(__name__)


class DocumentChunker:
    """
    Chunks large documents into smaller pieces for embedding.

    Features:
    - Accurate token counting using tiktoken
    - Semantic chunking that respects logical boundaries
    - Configurable chunk size with safety margins
    - Metadata tracking for chunk reconstruction
    """

    def __init__(
        self,
        max_tokens: int = 7500,
        chunk_overlap: int = 100,
        encoding_name: str = "cl100k_base",
    ):
        """
        Initialize document chunker.

        Args:
            max_tokens: Maximum tokens per chunk (default: 7500, safe for 8192 limit)
            chunk_overlap: Number of tokens to overlap between chunks (default: 100)
            encoding_name: Tiktoken encoding to use (default: cl100k_base for GPT-3.5/4)
        """
        self.max_tokens = max_tokens
        self.chunk_overlap = chunk_overlap
        self.encoding_name = encoding_name
        self.tokenizer = tiktoken.get_encoding(encoding_name)

        logger.info(
            f"DocumentChunker initialized with max_tokens={max_tokens}, "
            f"chunk_overlap={chunk_overlap}, encoding={encoding_name}"
        )

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens in text
        """
        return len(self.tokenizer.encode(text))

    def needs_chunking(self, text: str) -> bool:
        """
        Check if text needs chunking based on token count.

        Args:
            text: Text to check

        Returns:
            True if text exceeds max_tokens and needs chunking
        """
        token_count = self.count_tokens(text)
        needs_chunk = token_count > self.max_tokens

        if needs_chunk:
            logger.info(
                f"Document needs chunking: {token_count} tokens > {self.max_tokens} max"
            )

        return needs_chunk

    def chunk_document(
        self, content: str, document_id: Optional[str] = None
    ) -> List[dict]:
        """
        Chunk document into smaller pieces respecting token limits.

        Uses semchunk for semantic chunking that respects logical boundaries
        (paragraphs, sentences) while staying within token limits.

        Args:
            content: Document content to chunk
            document_id: Optional document ID for logging

        Returns:
            List of dictionaries with structure:
            [
                {
                    "chunk_text": str,      # Chunk content
                    "chunk_index": int,     # 0-based chunk index
                    "total_chunks": int,    # Total chunk count
                    "token_count": int,     # Tokens in this chunk
                },
                ...
            ]
        """
        try:
            # Check if chunking is needed
            total_tokens = self.count_tokens(content)

            if not self.needs_chunking(content):
                logger.debug(
                    f"Document {document_id or 'unknown'} does not need chunking: "
                    f"{total_tokens} tokens <= {self.max_tokens} max"
                )
                return [
                    {
                        "chunk_text": content,
                        "chunk_index": 0,
                        "total_chunks": 1,
                        "token_count": total_tokens,
                    }
                ]

            logger.info(
                f"📄 [CHUNKING] Document {document_id or 'unknown'} exceeds token limit "
                f"({total_tokens} tokens), splitting into chunks (max={self.max_tokens})"
            )

            # Use semchunk for semantic chunking
            # Create a chunker function that respects our token limits
            chunker = chunkerify(
                self.tokenizer,
                chunk_size=self.max_tokens,
                # Note: semchunk uses chunk_size as max, so we don't need to adjust
            )

            # Split the content using semchunk
            chunk_texts = chunker(content)

            # Create chunk dictionaries with metadata
            chunks = []

            for i, chunk_text in enumerate(chunk_texts):
                token_count = self.count_tokens(chunk_text)

                chunk = {
                    "chunk_text": chunk_text,
                    "chunk_index": i,
                    "total_chunks": len(chunk_texts),
                    "token_count": token_count,
                }
                chunks.append(chunk)

                logger.debug(
                    f"📄 [CHUNKING] Created chunk {i+1}/{len(chunk_texts)}: "
                    f"{token_count} tokens"
                )

            logger.info(
                f"✅ [CHUNKING] Document {document_id or 'unknown'} split into "
                f"{len(chunks)} chunks (avg {total_tokens // len(chunks)} tokens/chunk)"
            )

            return chunks

        except Exception as e:
            logger.error(
                f"❌ [CHUNKING] Failed to chunk document {document_id or 'unknown'}: {e}. "
                "Falling back to single chunk."
            )
            # Fallback: return entire document as single chunk
            return [
                {
                    "chunk_text": content,
                    "chunk_index": 0,
                    "total_chunks": 1,
                    "token_count": self.count_tokens(content),
                }
            ]

    def get_chunk_metadata(self, chunk: dict, original_document_id: str) -> dict:
        """
        Generate metadata for a document chunk for Qdrant storage.

        Args:
            chunk: Chunk dictionary from chunk_document()
            original_document_id: ID of the original document

        Returns:
            Dictionary of metadata for Qdrant
        """
        return {
            "chunk_index": chunk["chunk_index"],
            "total_chunks": chunk["total_chunks"],
            "is_chunk": True,
            "parent_document_id": original_document_id,
            "chunk_token_count": chunk["token_count"],
        }
