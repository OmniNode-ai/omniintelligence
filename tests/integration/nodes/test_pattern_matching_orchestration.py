# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Integration tests for pattern_matching_compute with pattern_storage_effect.

Tests the orchestration layer that wires pattern_storage_effect (storage) to
pattern_matching_compute (matching). This verifies the end-to-end flow:

    1. Seed patterns via pattern_storage_effect handlers
    2. Enrich stored patterns with keywords/category (simulating full DB row)
    3. Convert stored patterns → ModelPatternRecord
    4. Pass patterns to pattern_matching_compute handler
    5. Verify matches with correct confidence scores and metadata

Test Coverage:
    TC1: Keyword overlap matching
    TC2: Regex matching (validate operation)
    TC3: Category filtering
    TC4: Empty pattern library

Reference:
    - OMN-1921: Integration test for pattern matching orchestration
    - OMN-1424: pattern_matching_compute node implementation
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from omniintelligence.nodes.node_pattern_matching_compute.handlers.handler_compute import (
    handle_pattern_matching_compute,
)
from omniintelligence.nodes.node_pattern_matching_compute.models.model_pattern_matching_input import (
    ModelPatternContext,
    ModelPatternMatchingInput,
    ModelPatternRecord,
)
from omniintelligence.nodes.node_pattern_matching_compute.models.model_pattern_matching_output import (
    ModelPatternMatchingOutput,
)
from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_store_pattern import (
    handle_store_pattern,
)
from omniintelligence.testing import (
    MockPatternStore,
    create_valid_pattern_input,
)

# =============================================================================
# Orchestration Helpers
# =============================================================================


async def seed_pattern(
    store: MockPatternStore,
    *,
    signature: str,
    domain: str = "design_patterns",
    confidence: float = 0.9,
    keywords: list[str] | None = None,
    category: str | None = None,
) -> UUID:
    """Seed a pattern into the store with optional keywords and category.

    Stores via handle_store_pattern (the real storage handler) and then
    enriches the stored dict with keywords and category. In production,
    these fields exist on the full learned_patterns table row
    (ModelLearnedPatternRow) but are not part of the storage input model.

    Args:
        store: MockPatternStore to seed into.
        signature: Pattern signature text or regex.
        domain: Pattern domain identifier.
        confidence: Confidence score (>= 0.5).
        keywords: Optional keyword list for keyword overlap matching.
        category: Optional category for filtering.

    Returns:
        UUID of the seeded pattern.
    """
    pattern_id = uuid4()
    input_data = create_valid_pattern_input(
        pattern_id=pattern_id,
        signature=signature,
        signature_hash=f"hash_{pattern_id.hex[:12]}",
        domain=domain,
        confidence=confidence,
    )
    await handle_store_pattern(input_data, pattern_store=store, conn=None)

    # Enrich stored pattern with fields from the full learned_patterns row.
    # In production, the orchestrator queries the DB which returns the
    # complete ModelLearnedPatternRow including keywords and category.
    if keywords is not None:
        store.patterns[pattern_id]["keywords"] = keywords
    if category is not None:
        store.patterns[pattern_id]["category"] = category

    return pattern_id


def convert_stored_to_pattern_records(
    store: MockPatternStore,
) -> list[ModelPatternRecord]:
    """Convert stored patterns from MockPatternStore to ModelPatternRecord.

    This simulates the orchestration layer that:
        1. Fetches patterns from pattern_storage_effect (or the learned_patterns table)
        2. Converts ModelLearnedPatternRow → ModelPatternRecord

    In production, an orchestrator node performs this conversion before
    passing patterns to the compute node.

    Args:
        store: MockPatternStore with stored patterns.

    Returns:
        List of ModelPatternRecord suitable for pattern_matching_compute input.
    """
    records = []
    for pattern_id, stored in store.patterns.items():
        records.append(
            ModelPatternRecord(
                pattern_id=str(pattern_id),
                signature=stored.get("signature", ""),
                domain=stored.get("domain", ""),
                keywords=stored.get("keywords"),
                status=stored.get("state", "candidate")
                if isinstance(stored.get("state"), str)
                else stored.get("state", "candidate").value
                if stored.get("state")
                else "candidate",
                confidence=stored.get("confidence"),
                category=stored.get("category"),
            )
        )
    return records


async def orchestrate_pattern_matching(
    code_snippet: str,
    store: MockPatternStore,
    *,
    operation: str = "match",
    min_confidence: float = 0.1,
    max_results: int = 10,
    pattern_categories: list[str] | None = None,
    correlation_id: UUID | None = None,
) -> ModelPatternMatchingOutput:
    """Orchestrate pattern matching by wiring storage to compute.

    Demonstrates the full orchestration pattern:
        storage → convert → compute

    This helper function simulates what a NodePatternMatchingOrchestrator
    would do in production:
        1. Fetch patterns from storage (via pattern_storage_effect)
        2. Convert to ModelPatternRecord format
        3. Call pattern_matching_compute handler

    Args:
        code_snippet: Code to match against patterns.
        store: MockPatternStore containing seeded patterns.
        operation: Matching operation type ("match", "validate", etc.).
        min_confidence: Minimum confidence threshold for matches.
        max_results: Maximum number of matches to return.
        pattern_categories: Optional category filter list.
        correlation_id: Correlation ID for distributed tracing.

    Returns:
        ModelPatternMatchingOutput with matching results.
    """
    # Step 1: Fetch and convert patterns from storage
    pattern_records = convert_stored_to_pattern_records(store)

    # Step 2: Build compute input
    context = ModelPatternContext(
        min_confidence=min_confidence,
        max_results=max_results,
        pattern_categories=pattern_categories or [],
        correlation_id=correlation_id,
    )

    input_data = ModelPatternMatchingInput(
        code_snippet=code_snippet,
        patterns=pattern_records,
        operation=operation,
        context=context,
    )

    # Step 3: Call compute handler
    return handle_pattern_matching_compute(input_data)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_pattern_store() -> MockPatternStore:
    """Provide a fresh mock pattern store for each test."""
    return MockPatternStore()


@pytest.fixture
def correlation_id() -> UUID:
    """Provide a fixed correlation ID for tracing tests."""
    return UUID("550e8400-e29b-41d4-a716-446655440000")


# =============================================================================
# TC1: Keyword Overlap Matching
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestKeywordOverlapMatching:
    """TC1: Verify keyword overlap matching via storage → compute orchestration.

    Setup:
        Seed 3 patterns with distinct keyword sets via pattern_storage_effect:
        - singleton: ["singleton", "instance"]
        - factory: ["factory", "create"]
        - observer: ["observer", "subscribe"]

    Input:
        Singleton class code containing _instance and get_instance identifiers.

    Expected:
        - Singleton pattern matches with highest confidence
        - algorithm_used == "keyword_overlap"
    """

    async def test_singleton_pattern_matches_highest(
        self,
        mock_pattern_store: MockPatternStore,
        correlation_id: UUID,
    ) -> None:
        """Singleton keywords should produce highest overlap with singleton code."""
        # Seed patterns via storage handler, then enrich with keywords
        await seed_pattern(
            mock_pattern_store,
            signature="Singleton pattern with instance management",
            domain="design_patterns",
            keywords=["singleton", "instance"],
            confidence=0.9,
            category="design_pattern",
        )
        await seed_pattern(
            mock_pattern_store,
            signature="Factory pattern with create methods",
            domain="design_patterns",
            keywords=["factory", "create"],
            confidence=0.85,
            category="design_pattern",
        )
        await seed_pattern(
            mock_pattern_store,
            signature="Observer pattern with subscribe methods",
            domain="design_patterns",
            keywords=["observer", "subscribe"],
            confidence=0.8,
            category="design_pattern",
        )

        code = """\
class Singleton:
    _instance = None
    @classmethod
    def get_instance(cls):
        return cls._instance
"""

        result = await orchestrate_pattern_matching(
            code_snippet=code,
            store=mock_pattern_store,
            operation="match",
            min_confidence=0.01,
            correlation_id=correlation_id,
        )

        assert result.success is True
        assert len(result.matches) > 0

        # Singleton pattern should have highest confidence (sorted descending)
        best_match = result.matches[0]
        assert best_match.algorithm_used == "keyword_overlap"
        assert best_match.confidence > 0

        # "singleton" and "instance" keywords overlap with code identifiers
        assert (
            "singleton" in best_match.pattern_name.lower()
            or "instance" in best_match.pattern_name.lower()
        )

        # Verify metadata
        assert result.metadata is not None
        assert result.metadata.patterns_analyzed == 3
        assert result.metadata.status == "completed"

    async def test_no_matching_keywords_returns_empty(
        self,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Code with no keyword overlap should produce no matches above threshold."""
        await seed_pattern(
            mock_pattern_store,
            signature="Database connection pooling infrastructure",
            domain="infrastructure",
            keywords=["database", "connection", "pooling"],
            confidence=0.9,
        )

        # Code with completely unrelated identifiers
        code = "x = 42"

        result = await orchestrate_pattern_matching(
            code_snippet=code,
            store=mock_pattern_store,
            operation="match",
            min_confidence=0.3,
        )

        assert result.success is True
        assert len(result.matches) == 0


# =============================================================================
# TC2: Regex Matching (validate operation)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestRegexMatching:
    """TC2: Verify regex matching via the validate operation.

    Setup:
        Seed pattern with regex signature: def\\s+\\w+\\s*\\(.*\\)\\s*->

    Input:
        Function with type annotation: def calculate(x: int) -> int

    Expected:
        - Pattern matches with confidence 1.0
        - algorithm_used == "regex_match"
    """

    async def test_regex_signature_matches_with_full_confidence(
        self,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Regex signature should match typed function with confidence 1.0."""
        await seed_pattern(
            mock_pattern_store,
            signature=r"def\s+\w+\s*\(.*\)\s*->",
            domain="code_structure",
            keywords=["typed", "function"],
            confidence=0.95,
            category="code_quality",
        )

        code = """\
def calculate(x: int) -> int:
    return x * 2
"""

        result = await orchestrate_pattern_matching(
            code_snippet=code,
            store=mock_pattern_store,
            operation="validate",
            min_confidence=0.5,
        )

        assert result.success is True
        assert len(result.matches) == 1

        match = result.matches[0]
        assert match.confidence == 1.0
        assert match.algorithm_used == "regex_match"
        assert match.match_reason == "Pattern signature matches code structure"

    async def test_regex_no_match_returns_empty(
        self,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Non-matching regex should produce no results."""
        await seed_pattern(
            mock_pattern_store,
            signature=r"class\s+\w+\s*\(metaclass=ABCMeta\)",
            domain="code_structure",
            confidence=0.9,
        )

        # Code without metaclass usage
        code = "def simple_function(): pass"

        result = await orchestrate_pattern_matching(
            code_snippet=code,
            store=mock_pattern_store,
            operation="validate",
            min_confidence=0.5,
        )

        assert result.success is True
        assert len(result.matches) == 0


# =============================================================================
# TC3: Category Filtering
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestCategoryFiltering:
    """TC3: Verify pattern category filtering through orchestration.

    Setup:
        - Pattern A: category="design_pattern", keywords=["singleton", "instance"]
        - Pattern B: category="anti_pattern", keywords=["singleton", "instance"]

    Input:
        Singleton code with pattern_categories=["anti_pattern"]

    Expected:
        - Only Pattern B (anti_pattern) appears in results
    """

    async def test_filter_by_anti_pattern_category(
        self,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Only anti_pattern category patterns should appear when filtered."""
        # Seed a design pattern
        await seed_pattern(
            mock_pattern_store,
            signature="Singleton design pattern",
            domain="patterns",
            keywords=["singleton", "instance"],
            confidence=0.9,
            category="design_pattern",
        )

        # Seed an anti-pattern with the same keywords
        await seed_pattern(
            mock_pattern_store,
            signature="Singleton anti-pattern overuse",
            domain="patterns",
            keywords=["singleton", "instance"],
            confidence=0.85,
            category="anti_pattern",
        )

        code = """\
class Singleton:
    _instance = None
    @classmethod
    def get_instance(cls):
        return cls._instance
"""

        result = await orchestrate_pattern_matching(
            code_snippet=code,
            store=mock_pattern_store,
            operation="match",
            min_confidence=0.01,
            pattern_categories=["anti_pattern"],
        )

        assert result.success is True

        # Only anti_pattern category should be in results
        for match in result.matches:
            assert match.category == "anti_pattern"

        # Metadata should show only 1 pattern analyzed (the other was filtered)
        assert result.metadata is not None
        assert result.metadata.patterns_analyzed == 1

    async def test_empty_category_filter_includes_all(
        self,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Empty category filter should include all patterns."""
        for category in ["design_pattern", "anti_pattern", "code_smell"]:
            await seed_pattern(
                mock_pattern_store,
                signature="Pattern with shared vocabulary keywords",
                domain="patterns",
                keywords=["shared", "vocabulary", "pattern"],
                confidence=0.8,
                category=category,
            )

        code = "shared = vocabulary.pattern.matching"

        result = await orchestrate_pattern_matching(
            code_snippet=code,
            store=mock_pattern_store,
            operation="match",
            min_confidence=0.01,
            pattern_categories=[],  # Empty = all categories
        )

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.patterns_analyzed == 3


# =============================================================================
# TC4: Empty Pattern Library
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestEmptyPatternLibrary:
    """TC4: Verify behavior with empty or fully-filtered pattern library.

    Setup:
        No patterns in database (or all filtered out by category).

    Expected:
        - success=True, matches=[]
        - metadata.status == "no_patterns" (when library is empty)
    """

    async def test_empty_store_returns_no_patterns_status(
        self,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """Empty pattern store should return success with no_patterns status."""
        assert len(mock_pattern_store.patterns) == 0

        result = await orchestrate_pattern_matching(
            code_snippet="def hello(): return 'world'",
            store=mock_pattern_store,
            operation="match",
        )

        assert result.success is True
        assert result.matches == []
        assert result.metadata is not None
        assert result.metadata.status == "no_patterns"

    async def test_filtered_to_empty_returns_completed(
        self,
        mock_pattern_store: MockPatternStore,
    ) -> None:
        """All patterns filtered by category should return completed with no matches."""
        # Seed a pattern with a specific category
        await seed_pattern(
            mock_pattern_store,
            signature="Existing pattern",
            domain="patterns",
            keywords=["existing"],
            confidence=0.9,
            category="design_pattern",
        )

        # Filter for a nonexistent category
        result = await orchestrate_pattern_matching(
            code_snippet="existing pattern code",
            store=mock_pattern_store,
            operation="match",
            pattern_categories=["nonexistent_category"],
        )

        assert result.success is True
        assert result.matches == []
        assert result.metadata is not None
        # Patterns existed but were all filtered out, so 0 analyzed
        assert result.metadata.patterns_analyzed == 0


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "TestCategoryFiltering",
    "TestEmptyPatternLibrary",
    "TestKeywordOverlapMatching",
    "TestRegexMatching",
    "convert_stored_to_pattern_records",
    "orchestrate_pattern_matching",
    "seed_pattern",
]
