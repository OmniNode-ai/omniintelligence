"""
Hybrid Search Strategy

Implements hybrid search combining vector similarity search with keyword search
for improved recall and precision in document and code example retrieval.

Strategy combines:
1. Vector/semantic search for conceptual matches
2. Keyword search for exact term matches
3. Score boosting for results appearing in both searches
4. Intelligent result merging with preference ordering
"""

from typing import Any

from server.config.logfire_config import get_logger, safe_span
from server.services.embeddings.embedding_service import create_embedding
from server.services.search.keyword_extractor import (
    build_search_terms,
    extract_keywords,
)
from supabase import Client

logger = get_logger(__name__)


class HybridSearchStrategy:
    """Strategy class implementing hybrid search combining vector and keyword search"""

    def __init__(self, supabase_client: Client, base_strategy):
        self.supabase_client = supabase_client
        self.base_strategy = base_strategy

    async def keyword_search(
        self,
        query: str,
        match_count: int,
        table_name: str = "documents",
        filter_metadata: dict | None = None,
        select_fields: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform intelligent keyword search using extracted keywords.

        This method extracts keywords from the query and searches for documents
        containing any of those keywords, ranking results by the number of matches.

        Args:
            query: The search query text
            match_count: Number of results to return
            table_name: The table to search (documents, archon_crawled_pages, or archon_code_examples)
            filter_metadata: Optional metadata filters
            select_fields: Optional specific fields to select (default: all)

        Returns:
            List of matching documents ranked by keyword relevance
        """
        try:
            # Extract keywords from the query
            keywords = extract_keywords(query, min_length=2, max_keywords=8)

            if not keywords:
                # Fallback to original query if no keywords extracted
                keywords = [query]

            logger.debug(f"Extracted keywords from '{query}': {keywords}")

            # Build search terms including variations
            search_terms = build_search_terms(keywords)[:12]  # Limit total search terms

            # For now, we'll search for documents containing ANY of the keywords
            # and then rank them by how many keywords they contain
            all_results = []
            seen_ids = set()

            # Search for each keyword individually to get better coverage
            for keyword in search_terms[:6]:  # Limit to avoid too many queries
                # Build the query with appropriate fields
                if select_fields:
                    query_builder = self.supabase_client.from_(table_name).select(
                        select_fields
                    )
                else:
                    query_builder = self.supabase_client.from_(table_name).select("*")

                # Add keyword search condition with wildcards
                search_pattern = f"%{keyword}%"

                # Handle different search patterns based on table
                if table_name == "archon_code_examples":
                    # Search both content and summary for code examples
                    query_builder = query_builder.or_(
                        f"content.ilike.{search_pattern},summary.ilike.{search_pattern}"
                    )
                else:
                    query_builder = query_builder.ilike("content", search_pattern)

                # Add metadata filters if provided
                if filter_metadata:
                    if "source" in filter_metadata and table_name in [
                        "documents",
                        "crawled_pages",
                    ]:
                        query_builder = query_builder.eq(
                            "source_id", filter_metadata["source"]
                        )
                    elif "source_id" in filter_metadata:
                        query_builder = query_builder.eq(
                            "source_id", filter_metadata["source_id"]
                        )

                # Execute query with limit
                response = query_builder.limit(match_count * 2).execute()

                if response.data:
                    for result in response.data:
                        result_id = result.get("id")
                        if result_id and result_id not in seen_ids:
                            # Count how many keywords match in this result
                            content = result.get("content", "").lower()
                            summary = (
                                result.get("summary", "").lower()
                                if table_name == "archon_code_examples"
                                else ""
                            )
                            combined_text = f"{content} {summary}"

                            # Count keyword matches
                            match_score = sum(
                                1 for kw in keywords if kw.lower() in combined_text
                            )

                            # Add match score to result
                            result["keyword_match_score"] = match_score
                            result["matched_keyword"] = keyword

                            all_results.append(result)
                            seen_ids.add(result_id)

            # Sort results by keyword match score (descending)
            all_results.sort(
                key=lambda x: x.get("keyword_match_score", 0), reverse=True
            )

            # Return top N results
            final_results = all_results[:match_count]

            logger.debug(
                f"Keyword search found {len(final_results)} results from {len(all_results)} total matches"
            )

            return final_results

        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []

    async def search_documents_hybrid(
        self,
        query: str,
        query_embedding: list[float],
        match_count: int,
        filter_metadata: dict | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform hybrid search on archon_crawled_pages table combining vector and keyword search.

        Args:
            query: Original search query text
            query_embedding: Pre-computed query embedding
            match_count: Number of results to return
            filter_metadata: Optional metadata filter dict

        Returns:
            List of matching documents with boosted scores for dual matches
        """
        with safe_span("hybrid_search_documents") as span:
            try:
                # 1. Get vector search results using base strategy
                vector_results = await self.base_strategy.vector_search(
                    query_embedding=query_embedding,
                    match_count=match_count * 2,  # Get more for filtering
                    filter_metadata=filter_metadata,
                    table_rpc="match_archon_crawled_pages",
                )

                # 2. Get keyword search results
                keyword_results = await self.keyword_search(
                    query=query,
                    match_count=match_count * 2,
                    table_name="archon_crawled_pages",
                    filter_metadata=filter_metadata,
                    select_fields="id, url, chunk_number, content, metadata, source_id",
                )

                # 3. Combine and merge results intelligently
                combined_results = self._merge_search_results(
                    vector_results, keyword_results, match_count
                )

                span.set_attribute("vector_results_count", len(vector_results))
                span.set_attribute("keyword_results_count", len(keyword_results))
                span.set_attribute("final_results_count", len(combined_results))

                logger.debug(
                    f"Hybrid document search: {len(vector_results)} vector + {len(keyword_results)} keyword → {len(combined_results)} final"
                )

                return combined_results

            except Exception as e:
                logger.error(f"Hybrid document search failed: {e}")
                span.set_attribute("error", str(e))
                return []

    async def search_code_examples_hybrid(
        self,
        query: str,
        match_count: int,
        filter_metadata: dict | None = None,
        source_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform hybrid search on archon_code_examples table combining vector and keyword search.

        Args:
            query: Search query text
            match_count: Number of results to return
            filter_metadata: Optional metadata filter dict
            source_id: Optional source ID to filter results

        Returns:
            List of matching code examples with boosted scores for dual matches
        """
        with safe_span("hybrid_search_code_examples") as span:
            try:
                # Create query embedding (no enhancement needed)
                query_embedding = await create_embedding(query)

                if not query_embedding:
                    logger.error("Failed to create embedding for code example query")
                    return []

                # 1. Get vector search results using base strategy
                combined_filter = filter_metadata or {}
                if source_id:
                    combined_filter["source"] = source_id

                vector_results = await self.base_strategy.vector_search(
                    query_embedding=query_embedding,
                    match_count=match_count * 2,
                    filter_metadata=combined_filter,
                    table_rpc="match_archon_code_examples",
                )

                # 2. Get keyword search results
                keyword_filter = filter_metadata or {}
                if source_id:
                    keyword_filter["source_id"] = source_id

                keyword_results = await self.keyword_search(
                    query=query,
                    match_count=match_count * 2,
                    table_name="archon_code_examples",
                    filter_metadata=keyword_filter,
                    select_fields="id, url, chunk_number, content, summary, metadata, source_id",
                )

                # 3. Combine and merge results intelligently
                combined_results = self._merge_search_results(
                    vector_results, keyword_results, match_count
                )

                span.set_attribute("vector_results_count", len(vector_results))
                span.set_attribute("keyword_results_count", len(keyword_results))
                span.set_attribute("final_results_count", len(combined_results))

                logger.debug(
                    f"Hybrid code search: {len(vector_results)} vector + {len(keyword_results)} keyword → {len(combined_results)} final"
                )

                return combined_results

            except Exception as e:
                logger.error(f"Hybrid code example search failed: {e}")
                span.set_attribute("error", str(e))
                return []

    def _merge_search_results(
        self,
        vector_results: list[dict[str, Any]],
        keyword_results: list[dict[str, Any]],
        match_count: int,
    ) -> list[dict[str, Any]]:
        """
        Intelligently merge vector and keyword search results with preference ordering.

        Priority order:
        1. Results appearing in BOTH searches (highest relevance) - get score boost
        2. Vector-only results (semantic matches)
        3. Keyword-only results (exact term matches)

        Args:
            vector_results: Results from vector/semantic search
            keyword_results: Results from keyword search
            match_count: Maximum number of final results to return

        Returns:
            Merged and prioritized list of results
        """
        seen_ids: set[str] = set()
        combined_results: list[dict[str, Any]] = []

        # Create lookup for vector results by ID for efficient matching
        vector_lookup = {r.get("id"): r for r in vector_results if r.get("id")}

        # Phase 1: Add items that appear in BOTH searches (boost their scores)
        for keyword_result in keyword_results:
            result_id = keyword_result.get("id")
            if result_id and result_id in vector_lookup and result_id not in seen_ids:
                vector_result = vector_lookup[result_id]
                # Boost similarity score for dual matches (cap at 1.0)
                boosted_similarity = min(1.0, vector_result.get("similarity", 0) * 1.2)
                vector_result["similarity"] = boosted_similarity
                vector_result["match_type"] = "hybrid"  # Mark as hybrid match

                combined_results.append(vector_result)
                seen_ids.add(result_id)

        # Phase 2: Add remaining vector results (semantic matches without exact keywords)
        for vector_result in vector_results:
            result_id = vector_result.get("id")
            if (
                result_id
                and result_id not in seen_ids
                and len(combined_results) < match_count
            ):
                vector_result["match_type"] = "vector"
                combined_results.append(vector_result)
                seen_ids.add(result_id)

        # Phase 3: Add pure keyword matches if we need more results
        for keyword_result in keyword_results:
            result_id = keyword_result.get("id")
            if (
                result_id
                and result_id not in seen_ids
                and len(combined_results) < match_count
            ):
                # Convert keyword result to match vector result format
                # Use keyword match score to influence similarity score
                keyword_score = keyword_result.get("keyword_match_score", 1)
                # Scale keyword score to similarity range (0.3 to 0.7 based on matches)
                scaled_similarity = min(0.7, 0.3 + (keyword_score * 0.1))

                standardized_result = {
                    "id": keyword_result["id"],
                    "url": keyword_result["url"],
                    "chunk_number": keyword_result["chunk_number"],
                    "content": keyword_result["content"],
                    "metadata": keyword_result["metadata"],
                    "source_id": keyword_result["source_id"],
                    "similarity": scaled_similarity,
                    "match_type": "keyword",
                    "keyword_match_score": keyword_score,
                }

                # Include summary if present (for code examples)
                if "summary" in keyword_result:
                    standardized_result["summary"] = keyword_result["summary"]

                combined_results.append(standardized_result)
                seen_ids.add(result_id)

        # Return only up to the requested match count
        final_results = combined_results[:match_count]

        logger.debug(
            f"Merge stats - Hybrid: {sum(1 for r in final_results if r.get('match_type') == 'hybrid')}, "
            f"Vector: {sum(1 for r in final_results if r.get('match_type') == 'vector')}, "
            f"Keyword: {sum(1 for r in final_results if r.get('match_type') == 'keyword')}"
        )

        return final_results
