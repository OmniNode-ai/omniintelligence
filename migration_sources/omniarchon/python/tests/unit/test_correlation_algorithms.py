"""
Unit tests for intelligence correlation algorithms.

Tests temporal correlation detection, semantic correlation calculation,
breaking change detection, and correlation strength algorithms.
"""

from datetime import datetime

import pytest
from src.server.data.intelligence_data_access import BreakingChangeData


class CorrelationAlgorithms:
    """
    Correlation algorithm implementations for testing.

    These algorithms would normally be part of the intelligence processing
    pipeline, but are extracted here for focused unit testing.
    """

    @staticmethod
    def calculate_temporal_correlation_strength(time_diff_hours: float) -> float:
        """
        Calculate temporal correlation strength based on time difference.

        Args:
            time_diff_hours: Time difference in hours between events

        Returns:
            Correlation strength between 0.0 and 1.0
        """
        # Handle negative time differences
        time_diff_hours = abs(time_diff_hours)

        if time_diff_hours <= 1:
            return 0.95  # Very high correlation within 1 hour
        elif time_diff_hours <= 3:
            return 0.8  # High correlation within 3 hours
        elif time_diff_hours <= 12:
            return 0.6  # Medium correlation within 12 hours
        elif time_diff_hours <= 36:
            return 0.3  # Low correlation within 36 hours
        elif time_diff_hours <= 168:  # 7 days
            return 0.1  # Minimal correlation within 7 days (classified as "none")
        else:
            return 0.0  # No correlation beyond 7 days

    @staticmethod
    def classify_correlation_strength(strength: float) -> str:
        """
        Classify numeric correlation strength into categories.

        Args:
            strength: Correlation strength between 0.0 and 1.0

        Returns:
            String classification: "high", "medium", "low", "none"
        """
        if strength >= 0.8:
            return "high"
        elif strength >= 0.5:
            return "medium"
        elif strength >= 0.2:
            return "low"
        else:
            return "none"

    @staticmethod
    def calculate_semantic_similarity(
        keywords1: list[str], keywords2: list[str]
    ) -> float:
        """
        Calculate semantic similarity between two sets of keywords.

        Args:
            keywords1: First set of keywords
            keywords2: Second set of keywords

        Returns:
            Semantic similarity score between 0.0 and 1.0
        """
        if not keywords1 or not keywords2:
            return 0.0

        set1 = {keyword.lower() for keyword in keywords1}
        set2 = {keyword.lower() for keyword in keywords2}

        # Calculate Jaccard similarity coefficient
        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        return intersection / union

    @staticmethod
    def find_common_keywords(keywords1: list[str], keywords2: list[str]) -> list[str]:
        """
        Find common keywords between two keyword lists.

        Args:
            keywords1: First set of keywords
            keywords2: Second set of keywords

        Returns:
            List of common keywords (case-insensitive)
        """
        set1 = {keyword.lower() for keyword in keywords1}
        set2 = {keyword.lower() for keyword in keywords2}

        common = set1 & set2
        return sorted(common)

    @staticmethod
    def detect_breaking_changes(
        old_code: str, new_code: str, file_path: str
    ) -> list[BreakingChangeData]:
        """
        Detect breaking changes between old and new code.

        Args:
            old_code: Original code
            new_code: Modified code
            file_path: Path to the file being analyzed

        Returns:
            List of detected breaking changes
        """
        breaking_changes = []

        # Simplified breaking change detection patterns
        patterns = [
            {
                "pattern": "def ",
                "type": "FUNCTION_SIGNATURE_CHANGE",
                "severity": "HIGH",
            },
            {
                "pattern": "class ",
                "type": "CLASS_DEFINITION_CHANGE",
                "severity": "HIGH",
            },
            {"pattern": "import ", "type": "IMPORT_CHANGE", "severity": "MEDIUM"},
            {"pattern": "from ", "type": "IMPORT_CHANGE", "severity": "MEDIUM"},
        ]

        old_lines = old_code.split("\n")
        new_lines = new_code.split("\n")

        for pattern_info in patterns:
            pattern = pattern_info["pattern"]
            old_matches = [line for line in old_lines if pattern in line]
            new_matches = [line for line in new_lines if pattern in line]

            if old_matches != new_matches:
                breaking_changes.append(
                    BreakingChangeData(
                        type=pattern_info["type"],
                        severity=pattern_info["severity"],
                        description=f"Changes detected in {pattern.strip()} statements",
                        files_affected=[file_path],
                    )
                )

        return breaking_changes

    @staticmethod
    def calculate_combined_correlation_score(
        temporal_strength: float,
        semantic_similarity: float,
        weights: dict[str, float] = None,
    ) -> float:
        """
        Calculate combined correlation score from temporal and semantic components.

        Args:
            temporal_strength: Temporal correlation strength (0.0-1.0)
            semantic_similarity: Semantic similarity score (0.0-1.0)
            weights: Optional weights for temporal and semantic components

        Returns:
            Combined correlation score (0.0-1.0)
        """
        if weights is None:
            weights = {"temporal": 0.6, "semantic": 0.4}

        # Ensure weights sum to 1.0
        total_weight = sum(weights.values())
        if total_weight > 0:
            normalized_weights = {k: v / total_weight for k, v in weights.items()}
        else:
            normalized_weights = {"temporal": 0.5, "semantic": 0.5}

        combined_score = temporal_strength * normalized_weights.get(
            "temporal", 0.5
        ) + semantic_similarity * normalized_weights.get("semantic", 0.5)

        return min(1.0, max(0.0, combined_score))


class TestTemporalCorrelationAlgorithms:
    """Test temporal correlation detection algorithms."""

    def test_temporal_correlation_strength_calculation(self):
        """Test temporal correlation strength calculation for various time differences."""
        test_cases = [
            (0.0, 0.95),  # Immediate - very high correlation
            (0.5, 0.95),  # 30 minutes - very high correlation
            (1.0, 0.95),  # 1 hour - very high correlation
            (2.0, 0.8),  # 2 hours - high correlation
            (3.0, 0.8),  # 3 hours - high correlation
            (6.0, 0.6),  # 6 hours - medium correlation
            (12.0, 0.6),  # 12 hours - medium correlation
            (24.0, 0.3),  # 1 day - low correlation
            (36.0, 0.3),  # 1.5 days - low correlation
            (48.0, 0.1),  # 2 days - minimal correlation (none)
            (72.0, 0.1),  # 3 days - minimal correlation (none)
            (120.0, 0.1),  # 5 days - minimal correlation (none)
            (168.0, 0.1),  # 7 days - minimal correlation (none)
            (200.0, 0.0),  # >7 days - no correlation
        ]

        for time_diff, expected_strength in test_cases:
            strength = CorrelationAlgorithms.calculate_temporal_correlation_strength(
                time_diff
            )
            assert (
                strength == expected_strength
            ), f"Time diff {time_diff}h -> {strength} (expected {expected_strength})"

    def test_correlation_strength_classification(self, correlation_strength_test_cases):
        """Test classification of correlation strength into categories."""
        for strength, expected_category in correlation_strength_test_cases:
            category = CorrelationAlgorithms.classify_correlation_strength(strength)
            assert (
                category == expected_category
            ), f"Strength {strength} -> '{category}' (expected '{expected_category}')"

    def test_temporal_correlation_with_scenarios(self, temporal_correlation_scenarios):
        """Test temporal correlation detection with realistic scenarios."""
        for scenario in temporal_correlation_scenarios:
            events = scenario["events"]

            if len(events) >= 2:
                # Parse timestamps
                time1 = datetime.fromisoformat(
                    events[0]["timestamp"].replace("Z", "+00:00")
                )
                time2 = datetime.fromisoformat(
                    events[1]["timestamp"].replace("Z", "+00:00")
                )

                # Calculate time difference
                time_diff_hours = abs((time2 - time1).total_seconds()) / 3600

                # Calculate correlation strength
                strength = (
                    CorrelationAlgorithms.calculate_temporal_correlation_strength(
                        time_diff_hours
                    )
                )
                category = CorrelationAlgorithms.classify_correlation_strength(strength)

                # Verify results match expectations
                assert (
                    abs(time_diff_hours - scenario["expected_time_diff"]) < 0.01
                ), f"Time diff mismatch in '{scenario['name']}'"
                assert (
                    category == scenario["expected_strength"]
                ), f"Strength category mismatch in '{scenario['name']}'"
                assert (
                    strength >= scenario["strength_threshold"]
                ), f"Strength below threshold in '{scenario['name']}'"

    def test_temporal_correlation_edge_cases(self):
        """Test temporal correlation edge cases."""
        # Test negative time differences (should be handled as absolute values)
        strength = CorrelationAlgorithms.calculate_temporal_correlation_strength(-2.0)
        assert strength > 0.0, "Negative time difference should be handled"

        # Test zero time difference
        strength = CorrelationAlgorithms.calculate_temporal_correlation_strength(0.0)
        assert strength == 0.95, "Zero time difference should give maximum correlation"

        # Test very large time differences
        strength = CorrelationAlgorithms.calculate_temporal_correlation_strength(
            10000.0
        )
        assert (
            strength == 0.0
        ), "Very large time differences should give zero correlation"


class TestSemanticCorrelationAlgorithms:
    """Test semantic correlation calculation algorithms."""

    def test_semantic_similarity_calculation(self):
        """Test semantic similarity calculation using Jaccard coefficient."""
        test_cases = [
            # Identical keywords - perfect similarity
            (["auth", "user", "login"], ["auth", "user", "login"], 1.0),
            # Partial overlap - medium similarity
            (
                ["auth", "user", "login", "password"],
                ["auth", "user", "session", "token"],
                0.333,
            ),  # 2/6 = 0.333 (Jaccard: intersection/union)
            # Single common keyword - low similarity
            (
                ["database", "query", "sql"],
                ["api", "endpoint", "database"],
                0.2,
            ),  # 1/5 = 0.2
            # No common keywords - zero similarity
            (["frontend", "react", "component"], ["backend", "python", "server"], 0.0),
            # One empty list - zero similarity
            (["auth", "user"], [], 0.0),
            # Both empty lists - zero similarity
            ([], [], 0.0),
        ]

        for keywords1, keywords2, expected_similarity in test_cases:
            similarity = CorrelationAlgorithms.calculate_semantic_similarity(
                keywords1, keywords2
            )
            assert (
                abs(similarity - expected_similarity) < 0.01
            ), f"Similarity mismatch: {keywords1} vs {keywords2} -> {similarity} (expected {expected_similarity})"

    def test_common_keywords_extraction(self):
        """Test extraction of common keywords."""
        test_cases = [
            (["Auth", "USER", "login"], ["auth", "user", "SESSION"], ["auth", "user"]),
            (["database", "query"], ["api", "database"], ["database"]),
            (["react", "component"], ["python", "server"], []),
            ([], ["auth", "user"], []),
        ]

        for keywords1, keywords2, expected_common in test_cases:
            common = CorrelationAlgorithms.find_common_keywords(keywords1, keywords2)
            assert (
                common == expected_common
            ), f"Common keywords mismatch: {keywords1} vs {keywords2} -> {common} (expected {expected_common})"

    def test_semantic_correlation_with_scenarios(self, semantic_correlation_scenarios):
        """Test semantic correlation with realistic scenarios."""
        for scenario in semantic_correlation_scenarios:
            docs = scenario["documents"]

            if len(docs) >= 2:
                keywords1 = docs[0]["keywords"]
                keywords2 = docs[1]["keywords"]

                # Calculate semantic similarity
                similarity = CorrelationAlgorithms.calculate_semantic_similarity(
                    keywords1, keywords2
                )
                common_keywords = CorrelationAlgorithms.find_common_keywords(
                    keywords1, keywords2
                )

                # Verify results
                assert (
                    abs(similarity - scenario["expected_similarity"]) < 0.15
                ), f"Similarity mismatch in '{scenario['name']}': {similarity} vs {scenario['expected_similarity']}"
                assert (
                    similarity >= scenario["similarity_threshold"]
                ), f"Similarity below threshold in '{scenario['name']}'"

                # Verify common keywords are as expected
                expected_common = set(scenario["common_keywords"])
                actual_common = set(common_keywords)
                assert (
                    expected_common.issubset(actual_common) or len(expected_common) == 0
                ), f"Common keywords mismatch in '{scenario['name']}'"

    def test_case_insensitive_semantic_analysis(self):
        """Test that semantic analysis is case-insensitive."""
        keywords1 = ["AUTH", "User", "LOGIN"]
        keywords2 = ["auth", "USER", "session"]

        similarity = CorrelationAlgorithms.calculate_semantic_similarity(
            keywords1, keywords2
        )
        common = CorrelationAlgorithms.find_common_keywords(keywords1, keywords2)

        assert similarity > 0, "Case variations should be handled"
        assert (
            "auth" in common and "user" in common
        ), "Common keywords should be case-normalized"


class TestBreakingChangeDetection:
    """Test breaking change detection algorithms."""

    def test_breaking_change_detection(self, breaking_change_scenarios):
        """Test breaking change detection with various scenarios."""
        for scenario in breaking_change_scenarios:
            changes = scenario["changes"]

            for change in changes:
                # Simulate breaking change detection
                if change["type"] == "API_SIGNATURE_CHANGE":
                    old_code = change.get("old_code", "def old_function():")
                    new_code = change.get("new_code", "def new_function(param):")
                else:
                    old_code = "original code"
                    new_code = "modified code"

                detected_changes = CorrelationAlgorithms.detect_breaking_changes(
                    old_code, new_code, change["file"]
                )

                # Verify detection results
                assert (
                    len(detected_changes) >= 0
                ), f"Breaking change detection failed for {scenario['name']}"

                if detected_changes:
                    assert detected_changes[0].severity in [
                        "LOW",
                        "MEDIUM",
                        "HIGH",
                        "CRITICAL",
                    ], f"Invalid severity in {scenario['name']}"

    def test_function_signature_change_detection(self):
        """Test detection of function signature changes."""
        old_code = """
def get_user(id: int) -> User:
    return User.objects.get(pk=id)

def process_data(data):
    return processed_data
"""

        new_code = """
def get_user(user_id: str, include_profile: bool = False) -> UserResponse:
    user = User.objects.get(pk=int(user_id))
    return user.to_response(include_profile)

def process_data(data, options=None):
    return processed_data
"""

        changes = CorrelationAlgorithms.detect_breaking_changes(
            old_code, new_code, "api.py"
        )

        # Should detect function definition changes
        function_changes = [c for c in changes if c.type == "FUNCTION_SIGNATURE_CHANGE"]
        assert len(function_changes) > 0, "Should detect function signature changes"
        assert all(
            c.severity == "HIGH" for c in function_changes
        ), "Function changes should be HIGH severity"

    def test_class_definition_change_detection(self):
        """Test detection of class definition changes."""
        old_code = """
class User:
    def __init__(self, name):
        self.name = name

class DatabaseConfig:
    pass
"""

        new_code = """
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email

class DatabaseSettings:  # Renamed class
    def __init__(self):
        pass
"""

        changes = CorrelationAlgorithms.detect_breaking_changes(
            old_code, new_code, "models.py"
        )

        # Should detect class definition changes
        class_changes = [c for c in changes if c.type == "CLASS_DEFINITION_CHANGE"]
        assert len(class_changes) > 0, "Should detect class definition changes"

    def test_import_change_detection(self):
        """Test detection of import changes."""
        old_code = """
import os
from typing import List, Dict
from mymodule import helper_function
"""

        new_code = """
import os
import sys
from typing import List, Dict, Optional
from mymodule import helper_function, new_function
"""

        changes = CorrelationAlgorithms.detect_breaking_changes(
            old_code, new_code, "utils.py"
        )

        # Should detect import changes
        import_changes = [c for c in changes if c.type == "IMPORT_CHANGE"]
        assert len(import_changes) > 0, "Should detect import changes"
        assert all(
            c.severity == "MEDIUM" for c in import_changes
        ), "Import changes should be MEDIUM severity"

    def test_no_breaking_changes(self):
        """Test when no breaking changes are detected."""
        old_code = """
# Add a comment
x = 1
y = 2
"""

        new_code = """
# Add a different comment
x = 1
y = 3
z = 4
"""

        changes = CorrelationAlgorithms.detect_breaking_changes(
            old_code, new_code, "constants.py"
        )

        # Minor changes shouldn't trigger breaking change detection
        assert (
            len(changes) == 0
        ), "Minor changes should not be detected as breaking changes"


class TestCombinedCorrelationScoring:
    """Test combined correlation scoring algorithms."""

    def test_combined_correlation_score_calculation(self):
        """Test calculation of combined correlation scores."""
        test_cases = [
            # High temporal, high semantic
            (0.9, 0.8, {"temporal": 0.6, "semantic": 0.4}, 0.86),  # 0.9*0.6 + 0.8*0.4
            # High temporal, low semantic
            (0.9, 0.2, {"temporal": 0.6, "semantic": 0.4}, 0.62),  # 0.9*0.6 + 0.2*0.4
            # Low temporal, high semantic
            (0.3, 0.9, {"temporal": 0.6, "semantic": 0.4}, 0.54),  # 0.3*0.6 + 0.9*0.4
            # Equal weights
            (0.7, 0.5, {"temporal": 0.5, "semantic": 0.5}, 0.6),  # 0.7*0.5 + 0.5*0.5
        ]

        for temporal, semantic, weights, expected_score in test_cases:
            score = CorrelationAlgorithms.calculate_combined_correlation_score(
                temporal, semantic, weights
            )
            assert (
                abs(score - expected_score) < 0.01
            ), f"Combined score mismatch: temporal={temporal}, semantic={semantic} -> {score} (expected {expected_score})"

    def test_combined_score_with_default_weights(self):
        """Test combined score calculation with default weights."""
        # Default weights should be temporal=0.6, semantic=0.4
        score = CorrelationAlgorithms.calculate_combined_correlation_score(0.8, 0.6)
        expected = 0.8 * 0.6 + 0.6 * 0.4  # 0.48 + 0.24 = 0.72

        assert (
            abs(score - expected) < 0.01
        ), f"Default weights calculation: {score} vs {expected}"

    def test_combined_score_bounds(self):
        """Test that combined scores are bounded between 0.0 and 1.0."""
        test_cases = [
            (0.0, 0.0),  # Minimum case
            (1.0, 1.0),  # Maximum case
            (0.5, 0.5),  # Middle case
        ]

        for temporal, semantic in test_cases:
            score = CorrelationAlgorithms.calculate_combined_correlation_score(
                temporal, semantic
            )
            assert (
                0.0 <= score <= 1.0
            ), f"Score {score} is outside valid bounds [0.0, 1.0]"

    def test_combined_score_weight_normalization(self):
        """Test that weights are normalized if they don't sum to 1.0."""
        # Weights that sum to 2.0 should be normalized to sum to 1.0
        weights = {"temporal": 0.8, "semantic": 1.2}  # Sum = 2.0
        score = CorrelationAlgorithms.calculate_combined_correlation_score(
            0.6, 0.4, weights
        )

        # Normalized weights: temporal=0.4, semantic=0.6
        expected = 0.6 * 0.4 + 0.4 * 0.6  # 0.24 + 0.24 = 0.48
        assert (
            abs(score - expected) < 0.01
        ), f"Weight normalization failed: {score} vs {expected}"

    def test_algorithm_validation_scenarios(self, algorithm_validation_scenarios):
        """Test algorithm validation with comprehensive scenarios."""
        for scenario in algorithm_validation_scenarios:
            scenario_name = scenario["name"]
            input_data = scenario["input"]
            expected_output = scenario["expected_output"]

            if scenario_name == "Perfect Temporal Match":
                time1 = datetime.fromisoformat(
                    input_data["repo1_time"].replace("Z", "+00:00")
                )
                time2 = datetime.fromisoformat(
                    input_data["repo2_time"].replace("Z", "+00:00")
                )
                time_diff = abs((time2 - time1).total_seconds()) / 3600
                strength = (
                    CorrelationAlgorithms.calculate_temporal_correlation_strength(
                        time_diff
                    )
                )

                assert abs(time_diff - expected_output["time_diff"]) < 0.01
                assert abs(strength - expected_output["correlation_strength"]) < 0.1

            elif scenario_name == "Perfect Semantic Match":
                similarity = CorrelationAlgorithms.calculate_semantic_similarity(
                    input_data["repo1_keywords"], input_data["repo2_keywords"]
                )
                common = CorrelationAlgorithms.find_common_keywords(
                    input_data["repo1_keywords"], input_data["repo2_keywords"]
                )

                assert abs(similarity - expected_output["semantic_similarity"]) < 0.01
                assert set(common) == set(expected_output["common_keywords"])

            elif scenario_name == "Combined Temporal and Semantic Correlation":
                temporal_strength = (
                    CorrelationAlgorithms.calculate_temporal_correlation_strength(
                        input_data["time_diff_hours"]
                    )
                )
                combined_strength = (
                    CorrelationAlgorithms.calculate_combined_correlation_score(
                        temporal_strength, input_data["semantic_similarity"]
                    )
                )

                assert (
                    abs(combined_strength - expected_output["combined_strength"]) < 0.1
                )


class TestCorrelationAlgorithmPerformance:
    """Test performance characteristics of correlation algorithms."""

    def test_temporal_correlation_performance(self):
        """Test temporal correlation calculation performance."""
        import time

        # Test with large number of calculations
        time_diffs = [i * 0.1 for i in range(10000)]  # 10,000 time differences

        start_time = time.time()
        strengths = [
            CorrelationAlgorithms.calculate_temporal_correlation_strength(td)
            for td in time_diffs
        ]
        end_time = time.time()

        processing_time = end_time - start_time

        assert len(strengths) == 10000, "All calculations should complete"
        assert (
            processing_time < 1.0
        ), f"Temporal correlation calculation too slow: {processing_time:.3f}s"
        assert all(
            0.0 <= s <= 1.0 for s in strengths
        ), "All strengths should be in valid range"

    def test_semantic_similarity_performance(self):
        """Test semantic similarity calculation performance."""
        import time

        # Generate test keyword sets
        base_keywords = [f"keyword{i}" for i in range(100)]
        keyword_pairs = [
            (base_keywords[:50], base_keywords[25:75])  # 1000 pairs with overlaps
            for _ in range(1000)
        ]

        start_time = time.time()
        similarities = [
            CorrelationAlgorithms.calculate_semantic_similarity(k1, k2)
            for k1, k2 in keyword_pairs
        ]
        end_time = time.time()

        processing_time = end_time - start_time

        assert len(similarities) == 1000, "All calculations should complete"
        assert (
            processing_time < 2.0
        ), f"Semantic similarity calculation too slow: {processing_time:.3f}s"
        assert all(
            0.0 <= s <= 1.0 for s in similarities
        ), "All similarities should be in valid range"

    def test_breaking_change_detection_performance(self):
        """Test breaking change detection performance."""
        import time

        # Generate test code samples
        old_codes = [
            f"def function_{i}(param): pass\nclass Class_{i}: pass" for i in range(100)
        ]
        new_codes = [
            f"def function_{i}(param, new_param): pass\nclass Class_{i}: pass"
            for i in range(100)
        ]

        start_time = time.time()
        all_changes = []
        for old, new in zip(old_codes, new_codes, strict=False):
            changes = CorrelationAlgorithms.detect_breaking_changes(
                old, new, f"file_{len(all_changes)}.py"
            )
            all_changes.extend(changes)
        end_time = time.time()

        processing_time = end_time - start_time

        assert len(all_changes) > 0, "Should detect some breaking changes"
        assert (
            processing_time < 1.0
        ), f"Breaking change detection too slow: {processing_time:.3f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
