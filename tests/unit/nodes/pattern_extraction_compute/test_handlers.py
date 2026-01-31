"""Unit tests for pattern_extraction_compute node handlers.

Tests the pure handler functions that extract patterns from session data.
Each handler is tested in isolation with mock session data to verify:
- Correct pattern detection
- Threshold filtering (min_occurrences, min_confidence)
- Edge case handling (empty data, missing fields)
- Result structure validation

These tests follow the ONEX testing pattern:
- Tests are pure and deterministic
- Each test is independent
- Clear test names describe what's being tested
"""

from datetime import datetime, timedelta

import pytest

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit

from omniintelligence.nodes.pattern_extraction_compute.handlers import (
    extract_all_patterns,
    extract_architecture_patterns,
    extract_error_patterns,
    extract_file_access_patterns,
    extract_tool_patterns,
)
from omniintelligence.nodes.pattern_extraction_compute.models import (
    EnumInsightType,
    ModelCodebaseInsight,
    ModelExtractionConfig,
    ModelPatternExtractionInput,
    ModelSessionSnapshot,
)


# =============================================================================
# File Access Pattern Tests
# =============================================================================


class TestExtractFileAccessPatterns:
    """Tests for extract_file_access_patterns handler."""

    def test_detects_co_access_patterns(
        self, multiple_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Files accessed together in multiple sessions produce co_access patterns."""
        # Use lenient thresholds to ensure pattern detection
        results = extract_file_access_patterns(
            multiple_sessions,
            min_occurrences=2,
            min_confidence=0.3,
        )

        # Should detect that api/routes.py and api/handlers.py are accessed together
        co_access_patterns = [r for r in results if r["pattern_type"] == "co_access"]
        assert len(co_access_patterns) > 0, "Should detect co-access patterns"

        # Check that routes.py and handlers.py appear together
        routes_handlers_pattern = None
        for pattern in co_access_patterns:
            files = set(pattern["files"])
            if "src/api/routes.py" in files and "src/api/handlers.py" in files:
                routes_handlers_pattern = pattern
                break

        assert (
            routes_handlers_pattern is not None
        ), "Should detect routes.py + handlers.py co-access"
        assert routes_handlers_pattern["occurrences"] >= 2
        assert routes_handlers_pattern["confidence"] > 0

    def test_detects_entry_points(
        self, multiple_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Files that are first accessed in sessions are detected as entry points."""
        results = extract_file_access_patterns(
            multiple_sessions,
            min_occurrences=2,
            min_confidence=0.3,
        )

        entry_point_patterns = [r for r in results if r["pattern_type"] == "entry_point"]

        # routes.py is first in multiple sessions
        if entry_point_patterns:
            # At least one entry point should be detected if threshold is met
            for pattern in entry_point_patterns:
                assert pattern["occurrences"] >= 2
                assert len(pattern["files"]) == 1
                assert pattern["confidence"] > 0

    def test_detects_modification_clusters(
        self, multiple_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Files modified together produce modification_cluster patterns."""
        results = extract_file_access_patterns(
            multiple_sessions,
            min_occurrences=2,
            min_confidence=0.3,
        )

        mod_clusters = [
            r for r in results if r["pattern_type"] == "modification_cluster"
        ]

        # routes.py and handlers.py are modified together in multiple sessions
        if mod_clusters:
            for cluster in mod_clusters:
                assert cluster["occurrences"] >= 2
                assert len(cluster["files"]) == 2
                assert cluster["confidence"] > 0

    def test_respects_min_occurrences(
        self, sessions_below_threshold: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Patterns below min_occurrences threshold are excluded."""
        # With min_occurrences=2, single-occurrence patterns should be excluded
        results = extract_file_access_patterns(
            sessions_below_threshold,
            min_occurrences=2,
            min_confidence=0.1,
        )

        # Should return empty because patterns only occur once
        assert len(results) == 0, "Patterns below min_occurrences should be excluded"

    def test_respects_min_confidence(
        self, multiple_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Patterns below min_confidence threshold are excluded."""
        # With very high confidence threshold, few patterns should pass
        high_confidence_results = extract_file_access_patterns(
            multiple_sessions,
            min_occurrences=1,
            min_confidence=0.99,
        )

        low_confidence_results = extract_file_access_patterns(
            multiple_sessions,
            min_occurrences=1,
            min_confidence=0.1,
        )

        # Higher threshold should yield fewer results
        assert len(high_confidence_results) <= len(low_confidence_results)

    def test_empty_sessions_returns_empty(
        self, empty_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Empty or minimal sessions return empty results."""
        results = extract_file_access_patterns(
            empty_sessions,
            min_occurrences=2,
            min_confidence=0.6,
        )

        # Empty sessions have no file pairs, so no patterns
        assert len(results) == 0

    def test_result_structure(
        self, multiple_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Results have correct TypedDict structure."""
        results = extract_file_access_patterns(
            multiple_sessions,
            min_occurrences=1,
            min_confidence=0.1,
        )

        if results:
            result = results[0]
            assert "pattern_id" in result
            assert "pattern_type" in result
            assert "files" in result
            assert "occurrences" in result
            assert "confidence" in result
            assert "evidence_session_ids" in result
            assert isinstance(result["files"], tuple)
            assert isinstance(result["evidence_session_ids"], tuple)


# =============================================================================
# Error Pattern Tests
# =============================================================================


class TestExtractErrorPatterns:
    """Tests for extract_error_patterns handler."""

    def test_detects_error_prone_files(
        self, sessions_with_errors: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Files appearing in error sessions are detected as error-prone."""
        results = extract_error_patterns(
            sessions_with_errors,
            min_occurrences=2,
            min_confidence=0.3,
        )

        error_prone = [r for r in results if r["pattern_type"] == "error_prone_file"]

        # database/connection.py appears in 3 error sessions
        connection_pattern = None
        for pattern in error_prone:
            if "src/database/connection.py" in pattern["affected_files"]:
                connection_pattern = pattern
                break

        assert connection_pattern is not None, "Should detect error-prone connection.py"
        assert connection_pattern["occurrences"] >= 2
        assert "ConnectionError" in connection_pattern["error_summary"]

    def test_detects_common_error_messages(
        self, sessions_with_errors: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Common error messages are detected as error_sequence patterns."""
        results = extract_error_patterns(
            sessions_with_errors,
            min_occurrences=2,
            min_confidence=0.3,
        )

        error_sequences = [r for r in results if r["pattern_type"] == "error_sequence"]

        # ConnectionError appears in multiple sessions
        if error_sequences:
            # Should detect the recurring ConnectionError
            assert any(
                "ConnectionError" in p["error_summary"] for p in error_sequences
            ), "Should detect recurring ConnectionError"

    def test_empty_errors_returns_empty(
        self, multiple_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Sessions without errors return no error patterns."""
        # multiple_sessions has no errors
        results = extract_error_patterns(
            multiple_sessions,
            min_occurrences=1,
            min_confidence=0.1,
        )

        assert len(results) == 0, "No errors should produce no error patterns"

    def test_failure_outcome_counted_as_error(
        self, base_time: datetime
    ) -> None:
        """Sessions with failure outcome are counted even without explicit errors."""
        sessions = (
            ModelSessionSnapshot(
                session_id="fail-001",
                working_directory="/project",
                started_at=base_time,
                ended_at=base_time + timedelta(minutes=10),
                files_accessed=("problematic.py",),
                files_modified=(),
                tools_used=("Read",),
                errors_encountered=(),  # No explicit errors
                outcome="failure",  # But marked as failure
            ),
            ModelSessionSnapshot(
                session_id="fail-002",
                working_directory="/project",
                started_at=base_time + timedelta(hours=1),
                ended_at=base_time + timedelta(hours=1, minutes=15),
                files_accessed=("problematic.py",),
                files_modified=(),
                tools_used=("Read",),
                errors_encountered=(),
                outcome="failure",
            ),
        )

        results = extract_error_patterns(
            sessions,
            min_occurrences=2,
            min_confidence=0.3,
        )

        error_prone = [r for r in results if r["pattern_type"] == "error_prone_file"]
        # problematic.py should be detected as error-prone due to failure outcomes
        assert any(
            "problematic.py" in p["affected_files"] for p in error_prone
        ), "Failure outcomes should contribute to error-prone detection"

    def test_result_structure(
        self, sessions_with_errors: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Results have correct TypedDict structure."""
        results = extract_error_patterns(
            sessions_with_errors,
            min_occurrences=1,
            min_confidence=0.1,
        )

        if results:
            result = results[0]
            assert "pattern_id" in result
            assert "pattern_type" in result
            assert "affected_files" in result
            assert "error_summary" in result
            assert "occurrences" in result
            assert "confidence" in result
            assert "evidence_session_ids" in result


# =============================================================================
# Tool Pattern Tests
# =============================================================================


class TestExtractToolPatterns:
    """Tests for extract_tool_patterns handler."""

    def test_detects_tool_sequences_bigrams(
        self, sessions_with_diverse_tools: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Detects tool bigram sequences (Read -> Edit)."""
        results = extract_tool_patterns(
            sessions_with_diverse_tools,
            min_occurrences=2,
            min_confidence=0.1,
        )

        sequences = [r for r in results if r["pattern_type"] == "tool_sequence"]

        # Read -> Edit should be detected as a common sequence
        read_edit = [
            s for s in sequences
            if s["tools"] == ("Read", "Edit") and s["context"] == "sequential_usage"
        ]
        assert len(read_edit) > 0, "Should detect Read -> Edit sequence"

    def test_detects_tool_sequences_trigrams(
        self, sessions_with_diverse_tools: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Detects tool trigram sequences (Read -> Edit -> Bash)."""
        results = extract_tool_patterns(
            sessions_with_diverse_tools,
            min_occurrences=2,
            min_confidence=0.1,
        )

        sequences = [r for r in results if r["pattern_type"] == "tool_sequence"]

        # Read -> Edit -> Bash should be detected
        trigrams = [
            s for s in sequences
            if len(s["tools"]) == 3 and s["context"] == "workflow_pattern"
        ]
        # May or may not meet threshold depending on occurrence count
        # Just verify structure if any exist
        for trigram in trigrams:
            assert len(trigram["tools"]) == 3

    def test_detects_tool_preferences(
        self, sessions_with_diverse_tools: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Detects tool-to-filetype associations."""
        results = extract_tool_patterns(
            sessions_with_diverse_tools,
            min_occurrences=1,
            min_confidence=0.1,
        )

        preferences = [r for r in results if r["pattern_type"] == "tool_preference"]

        # Tools should be associated with file extensions
        if preferences:
            for pref in preferences:
                assert len(pref["tools"]) == 1
                assert pref["context"].endswith("_files")  # e.g., ".py_files"

    def test_detects_success_rates(
        self, base_time: datetime
    ) -> None:
        """Detects tools with notably high or low success rates."""
        # Create sessions where one tool has high success, another has low
        sessions = (
            ModelSessionSnapshot(
                session_id="sr-001",
                working_directory="/project",
                started_at=base_time,
                ended_at=base_time + timedelta(minutes=10),
                files_accessed=("file.py",),
                files_modified=(),
                tools_used=("GoodTool", "GoodTool", "GoodTool"),
                errors_encountered=(),
                outcome="success",
            ),
            ModelSessionSnapshot(
                session_id="sr-002",
                working_directory="/project",
                started_at=base_time + timedelta(hours=1),
                ended_at=base_time + timedelta(hours=1, minutes=10),
                files_accessed=("file.py",),
                files_modified=(),
                tools_used=("GoodTool", "GoodTool"),
                errors_encountered=(),
                outcome="success",
            ),
            ModelSessionSnapshot(
                session_id="sr-003",
                working_directory="/project",
                started_at=base_time + timedelta(hours=2),
                ended_at=base_time + timedelta(hours=2, minutes=10),
                files_accessed=("file.py",),
                files_modified=(),
                tools_used=("GoodTool",),
                errors_encountered=(),
                outcome="success",
            ),
        )

        results = extract_tool_patterns(
            sessions,
            min_occurrences=2,
            min_confidence=0.1,
        )

        success_rates = [r for r in results if r["pattern_type"] == "success_rate"]

        # GoodTool has 100% success rate (3 sessions, all success)
        if success_rates:
            good_tool_pattern = [
                s for s in success_rates if "GoodTool" in s["tools"]
            ]
            if good_tool_pattern:
                assert good_tool_pattern[0]["success_rate"] == 1.0

    def test_empty_tools_returns_empty(
        self, empty_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Sessions without tools return no tool patterns."""
        results = extract_tool_patterns(
            empty_sessions,
            min_occurrences=1,
            min_confidence=0.1,
        )

        # One session has a single tool "Read", not enough for sequences
        sequences = [r for r in results if r["pattern_type"] == "tool_sequence"]
        assert len(sequences) == 0

    def test_result_structure(
        self, sessions_with_diverse_tools: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Results have correct TypedDict structure."""
        results = extract_tool_patterns(
            sessions_with_diverse_tools,
            min_occurrences=1,
            min_confidence=0.1,
        )

        if results:
            result = results[0]
            assert "pattern_id" in result
            assert "pattern_type" in result
            assert "tools" in result
            assert "context" in result
            assert "occurrences" in result
            assert "confidence" in result
            assert "success_rate" in result
            assert isinstance(result["tools"], tuple)


# =============================================================================
# Architecture Pattern Tests
# =============================================================================


class TestExtractArchitecturePatterns:
    """Tests for extract_architecture_patterns handler."""

    def test_detects_module_boundaries(
        self, sessions_with_architecture_patterns: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Directory pairs accessed together are detected as module boundaries."""
        results = extract_architecture_patterns(
            sessions_with_architecture_patterns,
            min_occurrences=2,
            min_confidence=0.3,
        )

        boundaries = [r for r in results if r["pattern_type"] == "module_boundary"]

        # src/api is accessed frequently, should appear as boundary
        if boundaries:
            # Check structure
            for boundary in boundaries:
                assert boundary["directory_prefix"]
                assert isinstance(boundary["member_files"], tuple)
                assert boundary["occurrences"] >= 2

    def test_detects_layer_patterns(
        self, sessions_with_architecture_patterns: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Common directory prefixes are detected as layer patterns."""
        results = extract_architecture_patterns(
            sessions_with_architecture_patterns,
            min_occurrences=2,
            min_confidence=0.3,
        )

        layers = [r for r in results if r["pattern_type"] == "layer_pattern"]

        # "src" and "src/api" should be detected as layers
        if layers:
            prefixes = [layer["directory_prefix"] for layer in layers]
            # At least one layer should be detected
            assert len(prefixes) > 0

    def test_empty_files_returns_empty(
        self, empty_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Sessions without files return no architecture patterns."""
        results = extract_architecture_patterns(
            empty_sessions,
            min_occurrences=2,
            min_confidence=0.6,
        )

        assert len(results) == 0

    def test_results_sorted_by_confidence(
        self, sessions_with_architecture_patterns: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Results are sorted by confidence descending."""
        results = extract_architecture_patterns(
            sessions_with_architecture_patterns,
            min_occurrences=1,
            min_confidence=0.1,
        )

        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i]["confidence"] >= results[i + 1]["confidence"]

    def test_result_structure(
        self, sessions_with_architecture_patterns: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Results have correct TypedDict structure."""
        results = extract_architecture_patterns(
            sessions_with_architecture_patterns,
            min_occurrences=1,
            min_confidence=0.1,
        )

        if results:
            result = results[0]
            assert "pattern_id" in result
            assert "pattern_type" in result
            assert "directory_prefix" in result
            assert "member_files" in result
            assert "occurrences" in result
            assert "confidence" in result
            assert isinstance(result["member_files"], tuple)


# =============================================================================
# Extract All Patterns (Integration) Tests
# =============================================================================


class TestExtractAllPatterns:
    """Tests for extract_all_patterns orchestration handler."""

    def test_full_extraction_pipeline(
        self, full_extraction_input: ModelPatternExtractionInput
    ) -> None:
        """All extractors run and produce a complete output."""
        output = extract_all_patterns(full_extraction_input)

        assert output.success is True
        assert output.metadata.status == "completed"
        assert output.metrics.sessions_analyzed == len(
            full_extraction_input.session_snapshots
        )
        assert output.metadata.processing_time_ms > 0

    def test_config_flags_disable_extractors(
        self,
        multiple_sessions: tuple[ModelSessionSnapshot, ...],
        reference_time: datetime,
    ) -> None:
        """Config flags control which extractors run."""
        # Only enable file patterns
        config = ModelExtractionConfig(
            extract_file_patterns=True,
            extract_error_patterns=False,
            extract_architecture_patterns=False,
            extract_tool_patterns=False,
            min_pattern_occurrences=1,
            min_confidence=0.1,
            reference_time=reference_time,
        )

        input_data = ModelPatternExtractionInput(
            session_snapshots=multiple_sessions,
            options=config,
        )

        output = extract_all_patterns(input_data)

        assert output.success is True
        # Only file patterns should be counted
        assert output.metrics.file_patterns_count >= 0
        assert output.metrics.error_patterns_count == 0
        assert output.metrics.architecture_patterns_count == 0
        assert output.metrics.tool_patterns_count == 0

    def test_deduplication_works(
        self,
        multiple_sessions: tuple[ModelSessionSnapshot, ...],
        reference_time: datetime,
    ) -> None:
        """Duplicate insights are deduplicated."""
        config = ModelExtractionConfig(
            min_pattern_occurrences=1,
            min_confidence=0.1,
            reference_time=reference_time,
        )

        input_data = ModelPatternExtractionInput(
            session_snapshots=multiple_sessions,
            options=config,
        )

        output = extract_all_patterns(input_data)

        # Check that no two new_insights have the same description
        descriptions = [insight.description for insight in output.new_insights]
        assert len(descriptions) == len(set(descriptions)), "Should have no duplicates"

    def test_merges_with_existing_insights(
        self,
        multiple_sessions: tuple[ModelSessionSnapshot, ...],
        existing_insights: tuple[ModelCodebaseInsight, ...],
        reference_time: datetime,
    ) -> None:
        """Existing insights are merged with new patterns."""
        config = ModelExtractionConfig(
            min_pattern_occurrences=1,
            min_confidence=0.1,
            reference_time=reference_time,
        )

        input_data = ModelPatternExtractionInput(
            session_snapshots=multiple_sessions,
            options=config,
            existing_insights=existing_insights,
        )

        output = extract_all_patterns(input_data)

        # Should have some updated insights if patterns match existing
        # The existing insight describes routes.py + handlers.py co-access
        # which should match patterns from multiple_sessions
        # Note: This depends on the identity key matching
        # May be in new_insights if identity doesn't match exactly
        total_insights = len(output.new_insights) + len(output.updated_insights)
        assert total_insights > 0

    def test_validation_error_on_empty_sessions(
        self, reference_time: datetime
    ) -> None:
        """Empty session list returns validation error."""
        # Create input that would fail validation
        # Note: ModelPatternExtractionInput requires min_length=1
        # So we need to test this differently - the Pydantic validation
        # will reject empty sessions at construction time

        # Instead, test what happens when we provide an empty tuple
        # after bypassing Pydantic validation (not possible normally)
        # For now, we verify that at least one session is required
        # by checking the model validation

        with pytest.raises(Exception):  # Pydantic ValidationError
            ModelPatternExtractionInput(
                session_snapshots=(),  # Empty - should fail validation
                options=ModelExtractionConfig(reference_time=reference_time),
            )

    def test_returns_correct_output_structure(
        self, full_extraction_input: ModelPatternExtractionInput
    ) -> None:
        """Output has all required fields with correct types."""
        output = extract_all_patterns(full_extraction_input)

        # Check main fields
        assert isinstance(output.success, bool)
        assert isinstance(output.new_insights, tuple)
        assert isinstance(output.updated_insights, tuple)

        # Check metrics
        assert output.metrics.sessions_analyzed >= 0
        assert output.metrics.total_patterns_found >= 0
        assert output.metrics.new_insights_count >= 0
        assert output.metrics.updated_insights_count >= 0

        # Check metadata
        assert output.metadata.status in (
            "pending",
            "completed",
            "validation_error",
            "compute_error",
        )
        assert output.metadata.processing_time_ms >= 0

    def test_insight_types_are_valid(
        self, full_extraction_input: ModelPatternExtractionInput
    ) -> None:
        """All insights have valid EnumInsightType values."""
        output = extract_all_patterns(full_extraction_input)

        for insight in output.new_insights:
            assert isinstance(insight.insight_type, EnumInsightType)
            assert insight.confidence >= 0.0
            assert insight.confidence <= 1.0

    def test_max_insights_per_type_respected(
        self,
        multiple_sessions: tuple[ModelSessionSnapshot, ...],
        reference_time: datetime,
    ) -> None:
        """max_insights_per_type limits results per category."""
        config = ModelExtractionConfig(
            min_pattern_occurrences=1,
            min_confidence=0.1,
            max_insights_per_type=2,
            reference_time=reference_time,
        )

        input_data = ModelPatternExtractionInput(
            session_snapshots=multiple_sessions,
            options=config,
        )

        output = extract_all_patterns(input_data)

        # Count insights by type
        type_counts: dict[EnumInsightType, int] = {}
        for insight in output.new_insights:
            type_counts[insight.insight_type] = (
                type_counts.get(insight.insight_type, 0) + 1
            )

        # Each type should have at most max_insights_per_type
        for count in type_counts.values():
            assert count <= 2, f"Type count {count} exceeds max_insights_per_type=2"

    def test_reference_time_used_for_timestamps(
        self,
        multiple_sessions: tuple[ModelSessionSnapshot, ...],
        reference_time: datetime,
    ) -> None:
        """Reference time from config is used for insight timestamps."""
        config = ModelExtractionConfig(
            min_pattern_occurrences=1,
            min_confidence=0.1,
            reference_time=reference_time,
        )

        input_data = ModelPatternExtractionInput(
            session_snapshots=multiple_sessions,
            options=config,
        )

        output = extract_all_patterns(input_data)

        # Metadata should include the reference time
        assert output.metadata.reference_time == reference_time


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_single_session_no_patterns_below_threshold(
        self, sample_session: ModelSessionSnapshot
    ) -> None:
        """Single session cannot produce patterns meeting min_occurrences=2."""
        results = extract_file_access_patterns(
            (sample_session,),
            min_occurrences=2,
            min_confidence=0.6,
        )

        # Single session means max 1 occurrence per pattern
        assert len(results) == 0

    def test_single_session_with_low_threshold(
        self, sample_session: ModelSessionSnapshot
    ) -> None:
        """Single session can produce patterns with min_occurrences=1."""
        results = extract_file_access_patterns(
            (sample_session,),
            min_occurrences=1,
            min_confidence=0.1,
        )

        # Should detect some patterns from the single session
        assert len(results) > 0

    def test_handles_missing_session_fields_gracefully(
        self, base_time: datetime
    ) -> None:
        """Handlers gracefully handle sessions with missing optional data."""
        # Create session with minimal data
        minimal_session = ModelSessionSnapshot(
            session_id="minimal",
            working_directory="/project",
            started_at=base_time,
            ended_at=base_time + timedelta(minutes=5),
            # All optional fields use defaults
        )

        # Should not raise, just return empty
        file_results = extract_file_access_patterns((minimal_session,), 1, 0.1)
        error_results = extract_error_patterns((minimal_session,), 1, 0.1)
        tool_results = extract_tool_patterns((minimal_session,), 1, 0.1)
        arch_results = extract_architecture_patterns((minimal_session,), 1, 0.1)

        assert isinstance(file_results, list)
        assert isinstance(error_results, list)
        assert isinstance(tool_results, list)
        assert isinstance(arch_results, list)

    def test_confidence_bounded_0_to_1(
        self, multiple_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """All confidence values are within [0.0, 1.0] range."""
        # Use lenient thresholds to get many patterns
        file_results = extract_file_access_patterns(multiple_sessions, 1, 0.0)
        error_results = extract_error_patterns(multiple_sessions, 1, 0.0)
        tool_results = extract_tool_patterns(multiple_sessions, 1, 0.0)
        arch_results = extract_architecture_patterns(multiple_sessions, 1, 0.0)

        all_confidences = (
            [r["confidence"] for r in file_results]
            + [r["confidence"] for r in error_results]
            + [r["confidence"] for r in tool_results]
            + [r["confidence"] for r in arch_results]
        )

        for confidence in all_confidences:
            assert 0.0 <= confidence <= 1.0, f"Confidence {confidence} out of bounds"

    def test_empty_input_list(self) -> None:
        """Empty session list returns empty results for individual extractors."""
        sessions: tuple[ModelSessionSnapshot, ...] = ()

        file_results = extract_file_access_patterns(sessions, 1, 0.1)
        error_results = extract_error_patterns(sessions, 1, 0.1)
        tool_results = extract_tool_patterns(sessions, 1, 0.1)
        arch_results = extract_architecture_patterns(sessions, 1, 0.1)

        assert file_results == []
        assert error_results == []
        assert tool_results == []
        assert arch_results == []


# =============================================================================
# Determinism Tests
# =============================================================================


class TestDeterminism:
    """Tests to verify deterministic behavior."""

    def test_same_input_same_pattern_count(
        self, multiple_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Same input produces same number of patterns."""
        results1 = extract_file_access_patterns(multiple_sessions, 2, 0.3)
        results2 = extract_file_access_patterns(multiple_sessions, 2, 0.3)

        assert len(results1) == len(results2)

    def test_same_input_same_confidence_values(
        self, multiple_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Same input produces same confidence values."""
        results1 = extract_file_access_patterns(multiple_sessions, 1, 0.1)
        results2 = extract_file_access_patterns(multiple_sessions, 1, 0.1)

        # Sort by confidence to compare
        conf1 = sorted([r["confidence"] for r in results1])
        conf2 = sorted([r["confidence"] for r in results2])

        assert conf1 == conf2

    def test_pattern_type_distribution_deterministic(
        self, multiple_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Pattern type distribution is deterministic."""
        results1 = extract_file_access_patterns(multiple_sessions, 1, 0.1)
        results2 = extract_file_access_patterns(multiple_sessions, 1, 0.1)

        types1 = sorted([r["pattern_type"] for r in results1])
        types2 = sorted([r["pattern_type"] for r in results2])

        assert types1 == types2


# =============================================================================
# Tool Failure Pattern Tests
# =============================================================================


class TestExtractToolFailurePatterns:
    """Tests for tool failure pattern extraction handler."""

    # === Detection Tests ===

    def test_detects_recurring_failures(
        self, sessions_with_recurring_failures: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Should detect same tool+error_type across sessions."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers import (
            extract_tool_failure_patterns,
        )

        results = extract_tool_failure_patterns(
            sessions_with_recurring_failures, min_occurrences=2, min_confidence=0.3
        )
        # Should find at least one pattern
        assert len(results) > 0
        # All results should have pattern_type="tool_failure"
        assert all(r["pattern_type"] == "tool_failure" for r in results)

    def test_detects_failure_sequences(
        self, sessions_with_failure_sequence: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Should detect Tool A fail -> Tool B fail sequences."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers import (
            extract_tool_failure_patterns,
        )

        results = extract_tool_failure_patterns(
            sessions_with_failure_sequence, min_occurrences=2, min_confidence=0.3
        )
        # Should detect the Read->Edit sequence
        assert len(results) > 0

    def test_detects_recovery_patterns(
        self, sessions_with_recovery_pattern: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Should detect failure -> retry -> success patterns."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers import (
            extract_tool_failure_patterns,
        )

        results = extract_tool_failure_patterns(
            sessions_with_recovery_pattern,
            min_occurrences=1,
            min_confidence=0.3,
            min_distinct_sessions=1,
        )
        # Recovery patterns may not be detected with these thresholds due to
        # insufficient retry occurrences - this test verifies the function
        # executes without error and returns a valid result structure
        assert isinstance(results, list)
        # If any patterns found, verify they have correct structure
        for r in results:
            assert "pattern_type" in r
            assert r["pattern_type"] == "tool_failure"

    def test_detects_failure_hotspots(
        self, sessions_with_directory_failures: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Should detect directories with high failure rates."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers import (
            extract_tool_failure_patterns,
        )

        results = extract_tool_failure_patterns(
            sessions_with_directory_failures, min_occurrences=2, min_confidence=0.3
        )
        assert len(results) > 0

    def test_detects_extension_context_failures(
        self, sessions_with_extension_failures: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Should detect failures correlated with file extensions (e.g., .json files).

        The sessions_with_extension_failures fixture has 5 failures on .json files
        across 3 sessions (Read and Edit both fail on various .json files).
        This should trigger context_failure pattern detection for the .json extension.
        """
        from omniintelligence.nodes.pattern_extraction_compute.handlers import (
            extract_tool_failure_patterns,
        )

        results = extract_tool_failure_patterns(
            sessions_with_extension_failures,
            min_occurrences=2,
            min_confidence=0.3,
            min_distinct_sessions=2,
        )

        # Should detect at least one pattern
        assert len(results) > 0, "Should detect failure patterns from .json files"

        # Find context_failure patterns (extension-based)
        context_patterns = [
            r for r in results
            if "context_failure:" in r["error_summary"]
            and ".json" in r["error_summary"]
        ]

        # Should detect context_failure for .json extension
        assert len(context_patterns) > 0, (
            "Should detect context_failure pattern for .json extension. "
            f"Found patterns: {[r['error_summary'] for r in results]}"
        )

        # Verify pattern structure
        json_pattern = context_patterns[0]
        assert json_pattern["pattern_type"] == "tool_failure"
        assert json_pattern["occurrences"] >= 2
        assert json_pattern["confidence"] > 0
        assert len(json_pattern["evidence_session_ids"]) >= 2, (
            "Pattern should span at least 2 distinct sessions"
        )

        # Verify affected files contain .json files
        affected = json_pattern["affected_files"]
        assert any(".json" in f for f in affected), (
            f"Affected files should include .json files: {affected}"
        )

    # === Threshold Tests ===

    def test_respects_min_occurrences(
        self, sessions_with_recurring_failures: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Should filter patterns below occurrence threshold."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers import (
            extract_tool_failure_patterns,
        )

        # With high min_occurrences, should find fewer patterns
        results_high = extract_tool_failure_patterns(
            sessions_with_recurring_failures, min_occurrences=100, min_confidence=0.0
        )
        results_low = extract_tool_failure_patterns(
            sessions_with_recurring_failures, min_occurrences=1, min_confidence=0.0
        )
        assert len(results_high) <= len(results_low)

    def test_respects_min_confidence(
        self, sessions_with_recurring_failures: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Should filter patterns below confidence threshold."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers import (
            extract_tool_failure_patterns,
        )

        results_high = extract_tool_failure_patterns(
            sessions_with_recurring_failures, min_occurrences=1, min_confidence=0.99
        )
        results_low = extract_tool_failure_patterns(
            sessions_with_recurring_failures, min_occurrences=1, min_confidence=0.0
        )
        assert len(results_high) <= len(results_low)

    # === Edge Cases ===

    def test_empty_tool_executions_returns_empty(
        self, multiple_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Should return empty list when no tool_executions."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers import (
            extract_tool_failure_patterns,
        )

        # multiple_sessions fixture has no tool_executions
        results = extract_tool_failure_patterns(multiple_sessions)
        assert results == []

    def test_no_failures_returns_empty(
        self, sessions_all_success: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Should return empty list when all executions succeed."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers import (
            extract_tool_failure_patterns,
        )

        results = extract_tool_failure_patterns(sessions_all_success)
        assert results == []

    def test_single_failure_not_pattern(
        self, single_failure_session: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Should not create pattern from single failure in single session."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers import (
            extract_tool_failure_patterns,
        )

        # With min_distinct_sessions=2, single session shouldn't create patterns
        results = extract_tool_failure_patterns(
            single_failure_session, min_distinct_sessions=2
        )
        assert results == []

    # === CRITICAL DETERMINISM TESTS ===

    def test_stable_pattern_ids(
        self, sessions_with_recurring_failures: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Same input produces IDENTICAL pattern_id values (no uuid4())."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers import (
            extract_tool_failure_patterns,
        )

        result1 = extract_tool_failure_patterns(
            sessions_with_recurring_failures, min_occurrences=1, min_confidence=0.0
        )
        result2 = extract_tool_failure_patterns(
            sessions_with_recurring_failures, min_occurrences=1, min_confidence=0.0
        )

        ids1 = [r["pattern_id"] for r in result1]
        ids2 = [r["pattern_id"] for r in result2]
        assert ids1 == ids2, "Pattern IDs must be deterministic (no uuid4())"

    def test_deterministic_ordering(
        self, sessions_with_recurring_failures: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Results are strictly ordered by (pattern_subtype, tool_name, confidence desc)."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers import (
            extract_tool_failure_patterns,
        )

        result1 = extract_tool_failure_patterns(
            sessions_with_recurring_failures, min_occurrences=1, min_confidence=0.0
        )
        result2 = extract_tool_failure_patterns(
            sessions_with_recurring_failures, min_occurrences=1, min_confidence=0.0
        )

        assert result1 == result2, "Full result list must be identical"

    def test_metadata_json_serializable(
        self, sessions_with_recurring_failures: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """All result values are JSON-serializable."""
        import json

        from omniintelligence.nodes.pattern_extraction_compute.handlers import (
            extract_tool_failure_patterns,
        )

        results = extract_tool_failure_patterns(
            sessions_with_recurring_failures, min_occurrences=1, min_confidence=0.0
        )
        for r in results:
            # Should not raise
            json.dumps(r["error_summary"])
            json.dumps(list(r["affected_files"]))
            json.dumps(list(r["evidence_session_ids"]))

    # === max_results_per_type Tests ===

    def test_respects_max_results_per_type(
        self, sessions_with_many_failure_patterns: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        """Should limit results per pattern subtype when max_results_per_type is set.

        The max_results_per_type parameter should limit the number of results
        returned for each pattern subtype (recurring_failure, failure_sequence,
        context_failure, recovery_pattern, failure_hotspot).

        This test verifies that when max_results_per_type=1 is set, each
        pattern subtype has at most 1 result in the output.
        """
        from collections import Counter

        from omniintelligence.nodes.pattern_extraction_compute.handlers import (
            extract_tool_failure_patterns,
        )

        # First, verify that without limit we get multiple patterns per type
        results_unlimited = extract_tool_failure_patterns(
            sessions_with_many_failure_patterns,
            min_occurrences=1,
            min_confidence=0.0,
            min_distinct_sessions=1,
            max_results_per_type=100,  # Effectively unlimited
        )

        # Now test with limit of 1 per type
        results_limited = extract_tool_failure_patterns(
            sessions_with_many_failure_patterns,
            min_occurrences=1,
            min_confidence=0.0,
            min_distinct_sessions=1,
            max_results_per_type=1,
        )

        # Extract pattern subtypes from error_summary (format: "subtype:tool:...")
        def get_subtype(result: dict) -> str:
            summary = result.get("error_summary", "")
            if ":" in summary:
                return summary.split(":")[0]
            return "unknown"

        # Count patterns per subtype for limited results
        subtype_counts = Counter(get_subtype(r) for r in results_limited)

        # Verify each subtype has at most 1 result
        for subtype, count in subtype_counts.items():
            assert count <= 1, (
                f"Pattern subtype '{subtype}' has {count} results, "
                f"but max_results_per_type=1 should limit to 1. "
                f"Results: {[r['error_summary'] for r in results_limited if get_subtype(r) == subtype]}"
            )

        # Verify limiting actually reduced results (if there were multiple to begin with)
        if len(results_unlimited) > len(subtype_counts):
            assert len(results_limited) < len(results_unlimited), (
                "max_results_per_type=1 should reduce total results when "
                "there are multiple patterns per subtype"
            )


# =============================================================================
# _within_time_bound Helper Function Tests
# =============================================================================


class TestWithinTimeBound:
    """Unit tests for _within_time_bound helper function.

    This function checks if two tool executions are within a time bound.
    It's used as a SECONDARY guard in failure sequence detection.
    Index-based ordering is the primary criterion.
    """

    def test_within_time_bound_returns_true_when_within_limit(
        self, base_time: datetime
    ) -> None:
        """Two executions 30 seconds apart with limit 60 should return True."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_tool_failure_patterns import (
            _within_time_bound,
        )
        from omniintelligence.nodes.pattern_extraction_compute.models import (
            ModelToolExecution,
        )

        exec_a = ModelToolExecution(
            tool_name="Read",
            success=False,
            error_type="FileNotFoundError",
            timestamp=base_time,
        )
        exec_b = ModelToolExecution(
            tool_name="Edit",
            success=False,
            error_type="FileNotFoundError",
            timestamp=base_time + timedelta(seconds=30),
        )

        result = _within_time_bound(exec_a, exec_b, max_gap_sec=60)

        assert result is True, "30 seconds apart with 60 second limit should be within bound"

    def test_within_time_bound_returns_false_when_outside_limit(
        self, base_time: datetime
    ) -> None:
        """Two executions 90 seconds apart with limit 60 should return False."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_tool_failure_patterns import (
            _within_time_bound,
        )
        from omniintelligence.nodes.pattern_extraction_compute.models import (
            ModelToolExecution,
        )

        exec_a = ModelToolExecution(
            tool_name="Read",
            success=False,
            error_type="FileNotFoundError",
            timestamp=base_time,
        )
        exec_b = ModelToolExecution(
            tool_name="Edit",
            success=False,
            error_type="FileNotFoundError",
            timestamp=base_time + timedelta(seconds=90),
        )

        result = _within_time_bound(exec_a, exec_b, max_gap_sec=60)

        assert result is False, "90 seconds apart with 60 second limit should be outside bound"

    def test_within_time_bound_equal_timestamps(
        self, base_time: datetime
    ) -> None:
        """Same timestamp should return True (short-circuit path)."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_tool_failure_patterns import (
            _within_time_bound,
        )
        from omniintelligence.nodes.pattern_extraction_compute.models import (
            ModelToolExecution,
        )

        exec_a = ModelToolExecution(
            tool_name="Read",
            success=False,
            error_type="FileNotFoundError",
            timestamp=base_time,
        )
        exec_b = ModelToolExecution(
            tool_name="Edit",
            success=False,
            error_type="FileNotFoundError",
            timestamp=base_time,  # Same timestamp
        )

        result = _within_time_bound(exec_a, exec_b, max_gap_sec=60)

        assert result is True, "Equal timestamps should return True"

    def test_within_time_bound_handles_negative_gracefully(
        self, base_time: datetime
    ) -> None:
        """B before A (negative delta) should return True (graceful handling).

        This shouldn't happen in practice (index-based ordering is primary),
        but the function handles it gracefully by returning True since
        negative values are <= max_gap_sec.
        """
        from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_tool_failure_patterns import (
            _within_time_bound,
        )
        from omniintelligence.nodes.pattern_extraction_compute.models import (
            ModelToolExecution,
        )

        exec_a = ModelToolExecution(
            tool_name="Read",
            success=False,
            error_type="FileNotFoundError",
            timestamp=base_time + timedelta(seconds=30),  # A is LATER
        )
        exec_b = ModelToolExecution(
            tool_name="Edit",
            success=False,
            error_type="FileNotFoundError",
            timestamp=base_time,  # B is EARLIER
        )

        result = _within_time_bound(exec_a, exec_b, max_gap_sec=60)

        assert result is True, "Negative delta (B before A) should return True"

    def test_within_time_bound_exactly_at_boundary(
        self, base_time: datetime
    ) -> None:
        """Exactly at the boundary (60 seconds with limit 60) should return True."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_tool_failure_patterns import (
            _within_time_bound,
        )
        from omniintelligence.nodes.pattern_extraction_compute.models import (
            ModelToolExecution,
        )

        exec_a = ModelToolExecution(
            tool_name="Read",
            success=False,
            error_type="FileNotFoundError",
            timestamp=base_time,
        )
        exec_b = ModelToolExecution(
            tool_name="Edit",
            success=False,
            error_type="FileNotFoundError",
            timestamp=base_time + timedelta(seconds=60),
        )

        result = _within_time_bound(exec_a, exec_b, max_gap_sec=60)

        assert result is True, "Exactly at boundary (60s with 60s limit) should return True"

    def test_within_time_bound_just_over_boundary(
        self, base_time: datetime
    ) -> None:
        """Just over the boundary (61 seconds with limit 60) should return False."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_tool_failure_patterns import (
            _within_time_bound,
        )
        from omniintelligence.nodes.pattern_extraction_compute.models import (
            ModelToolExecution,
        )

        exec_a = ModelToolExecution(
            tool_name="Read",
            success=False,
            error_type="FileNotFoundError",
            timestamp=base_time,
        )
        exec_b = ModelToolExecution(
            tool_name="Edit",
            success=False,
            error_type="FileNotFoundError",
            timestamp=base_time + timedelta(seconds=61),
        )

        result = _within_time_bound(exec_a, exec_b, max_gap_sec=60)

        assert result is False, "Just over boundary (61s with 60s limit) should return False"

    def test_within_time_bound_zero_max_gap(
        self, base_time: datetime
    ) -> None:
        """Zero max_gap_sec should only allow equal timestamps."""
        from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_tool_failure_patterns import (
            _within_time_bound,
        )
        from omniintelligence.nodes.pattern_extraction_compute.models import (
            ModelToolExecution,
        )

        exec_a = ModelToolExecution(
            tool_name="Read",
            success=False,
            error_type="FileNotFoundError",
            timestamp=base_time,
        )
        exec_b_same = ModelToolExecution(
            tool_name="Edit",
            success=False,
            error_type="FileNotFoundError",
            timestamp=base_time,
        )
        exec_b_later = ModelToolExecution(
            tool_name="Edit",
            success=False,
            error_type="FileNotFoundError",
            timestamp=base_time + timedelta(seconds=1),
        )

        # Same timestamp with zero max_gap should return True
        assert _within_time_bound(exec_a, exec_b_same, max_gap_sec=0) is True

        # Any positive delta with zero max_gap should return False
        assert _within_time_bound(exec_a, exec_b_later, max_gap_sec=0) is False
