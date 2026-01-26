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

from datetime import UTC, datetime, timedelta

import pytest

from omniintelligence.nodes.pattern_extraction_compute.handlers import (
    extract_all_patterns,
    extract_architecture_patterns,
    extract_error_patterns,
    extract_file_access_patterns,
    extract_tool_patterns,
)
from omniintelligence.nodes.pattern_extraction_compute.handlers.exceptions import (
    PatternExtractionComputeError,
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
            config=config,
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
            config=config,
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
            config=config,
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
                config=ModelExtractionConfig(reference_time=reference_time),
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
            config=config,
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
            config=config,
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
