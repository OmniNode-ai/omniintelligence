"""
Task Characteristics Similarity Matcher

Implements similarity matching algorithms for Track 3 pattern matching.

This module provides:
1. Multi-dimensional similarity scoring
2. Weighted characteristic matching
3. Structured filtering before semantic search
4. Hybrid similarity (structured + semantic)
5. Similarity explanation and scoring breakdown

The matcher combines structured filtering with semantic similarity
to find the most relevant historical tasks for pattern matching.
"""

from typing import Any, Optional

from server.models.task_characteristics_models import (
    ChangeScope,
    ComplexityLevel,
    Component,
    SimilarityMatch,
    TaskCharacteristics,
    TaskCharacteristicsQuery,
    TaskType,
)


class TaskCharacteristicsMatcher:
    """
    Advanced similarity matcher for task characteristics.

    Supports multiple similarity algorithms:
    - Structured matching: Exact and fuzzy categorical matching
    - Semantic matching: Embedding-based similarity
    - Hybrid matching: Weighted combination

    Usage:
        matcher = TaskCharacteristicsMatcher()
        matches = matcher.find_similar(target_chars, candidate_chars_list)
    """

    # Default weights for similarity components
    DEFAULT_WEIGHTS = {
        "task_type": 0.25,  # Task type similarity
        "complexity": 0.15,  # Complexity similarity
        "scope": 0.15,  # Change scope similarity
        "components": 0.20,  # Component overlap
        "context": 0.15,  # Context similarity
        "semantic": 0.10,  # Semantic text similarity (when available)
    }

    def __init__(self, weights: Optional[dict[str, float]] = None):
        """
        Initialize matcher with optional custom weights.

        Args:
            weights: Optional custom weight dictionary
        """
        self.weights = weights or self.DEFAULT_WEIGHTS
        self._validate_weights()

    def find_similar(
        self,
        target: TaskCharacteristics,
        candidates: list[TaskCharacteristics],
        query: Optional[TaskCharacteristicsQuery] = None,
    ) -> list[SimilarityMatch]:
        """
        Find similar tasks from candidates.

        Args:
            target: Target task characteristics to match
            candidates: List of candidate task characteristics
            query: Optional query specification with filters

        Returns:
            List of SimilarityMatch objects, sorted by similarity score
        """
        # Apply pre-filters if query provided
        if query:
            candidates = self._apply_filters(candidates, query)

        # Calculate similarities
        matches = []
        for candidate in candidates:
            score, matching_chars = self.calculate_similarity(target, candidate)

            # Apply threshold if specified
            if query and score < query.min_similarity_threshold:
                continue

            match = SimilarityMatch(
                task_id=candidate.metadata.task_id,
                similarity_score=score,
                matching_characteristics=matching_chars,
                task_characteristics=candidate,
            )
            matches.append(match)

        # Sort by score descending
        matches.sort(key=lambda x: x.similarity_score, reverse=True)

        # Limit results if specified
        if query and query.max_results:
            matches = matches[: query.max_results]

        return matches

    def calculate_similarity(
        self,
        task1: TaskCharacteristics,
        task2: TaskCharacteristics,
    ) -> tuple[float, list[str]]:
        """
        Calculate multi-dimensional similarity between two tasks.

        Args:
            task1: First task characteristics
            task2: Second task characteristics

        Returns:
            Tuple of (similarity_score, list_of_matching_characteristics)
        """
        scores = {}
        matching_chars = []

        # 1. Task Type Similarity
        type_score = self._task_type_similarity(task1.task_type, task2.task_type)
        scores["task_type"] = type_score
        if type_score > 0.8:
            matching_chars.append(f"task_type ({task1.task_type.value})")

        # 2. Complexity Similarity
        complexity_score = self._complexity_similarity(
            task1.complexity, task2.complexity
        )
        scores["complexity"] = complexity_score
        if complexity_score > 0.8:
            matching_chars.append(
                f"complexity ({task1.complexity.complexity_level.value})"
            )

        # 3. Scope Similarity
        scope_score = self._scope_similarity(task1.change_scope, task2.change_scope)
        scores["scope"] = scope_score
        if scope_score > 0.8:
            matching_chars.append(f"scope ({task1.change_scope.value})")

        # 4. Component Similarity
        component_score, shared_components = self._component_similarity(
            task1.affected_components, task2.affected_components
        )
        scores["components"] = component_score
        if component_score > 0.5:
            matching_chars.append(
                f"components ({', '.join([c.value for c in shared_components[:3]])})"
            )

        # 5. Context Similarity
        context_score = self._context_similarity(task1.context, task2.context)
        scores["context"] = context_score
        if context_score > 0.7:
            matching_chars.append("context_availability")

        # 6. Semantic Similarity (placeholder for embedding-based)
        # This would use actual embeddings in production
        semantic_score = self._semantic_similarity(
            task1.description_text, task2.description_text
        )
        scores["semantic"] = semantic_score

        # Calculate weighted total
        total_score = sum(
            scores[key] * self.weights[key] for key in scores if key in self.weights
        )

        return total_score, matching_chars

    def _task_type_similarity(self, type1: TaskType, type2: TaskType) -> float:
        """
        Calculate task type similarity.

        Exact match = 1.0
        Related types = 0.5-0.8
        Unrelated types = 0.0
        """
        if type1 == type2:
            return 1.0

        # Define related task type groups
        related_groups = [
            {TaskType.BUG_FIX, TaskType.DEBUG_INVESTIGATION},
            {
                TaskType.TEST_WRITING,
                TaskType.TEST_DEBUGGING,
                TaskType.TEST_COVERAGE_IMPROVEMENT,
            },
            {
                TaskType.DOCUMENTATION_CREATION,
                TaskType.DOCUMENTATION_UPDATE,
                TaskType.API_DOCUMENTATION,
            },
            {
                TaskType.FEATURE_IMPLEMENTATION,
                TaskType.API_DESIGN,
                TaskType.ARCHITECTURE_DESIGN,
            },
            {
                TaskType.REFACTORING,
                TaskType.PERFORMANCE_OPTIMIZATION,
                TaskType.TECHNICAL_DEBT,
            },
            {
                TaskType.INFRASTRUCTURE_SETUP,
                TaskType.DEPLOYMENT,
                TaskType.DEVOPS_AUTOMATION,
            },
        ]

        # Check if types are in the same group
        for group in related_groups:
            if type1 in group and type2 in group:
                return 0.6

        return 0.0

    def _complexity_similarity(self, comp1, comp2) -> float:
        """
        Calculate complexity similarity.

        Uses both discrete level and continuous score.
        """
        # Exact level match
        if comp1.complexity_level == comp2.complexity_level:
            level_score = 1.0
        # Adjacent levels
        elif (
            abs(
                self._complexity_level_to_int(comp1.complexity_level)
                - self._complexity_level_to_int(comp2.complexity_level)
            )
            == 1
        ):
            level_score = 0.7
        # Two levels apart
        elif (
            abs(
                self._complexity_level_to_int(comp1.complexity_level)
                - self._complexity_level_to_int(comp2.complexity_level)
            )
            == 2
        ):
            level_score = 0.4
        else:
            level_score = 0.0

        # Continuous score similarity
        score_diff = abs(comp1.complexity_score - comp2.complexity_score)
        score_similarity = max(0.0, 1.0 - score_diff)

        # Weighted average (60% level, 40% score)
        return level_score * 0.6 + score_similarity * 0.4

    def _scope_similarity(self, scope1: ChangeScope, scope2: ChangeScope) -> float:
        """
        Calculate change scope similarity.

        Exact match = 1.0
        Adjacent scopes = 0.6
        """
        if scope1 == scope2:
            return 1.0

        scope_order = [
            ChangeScope.SINGLE_FILE,
            ChangeScope.MULTIPLE_FILES,
            ChangeScope.MODULE,
            ChangeScope.CROSS_MODULE,
            ChangeScope.CROSS_SERVICE,
            ChangeScope.REPOSITORY_WIDE,
            ChangeScope.CROSS_REPOSITORY,
        ]

        try:
            idx1 = scope_order.index(scope1)
            idx2 = scope_order.index(scope2)
            diff = abs(idx1 - idx2)

            if diff == 1:
                return 0.6
            elif diff == 2:
                return 0.3
            else:
                return 0.0
        except ValueError:
            return 0.0

    def _component_similarity(
        self, components1: list[Component], components2: list[Component]
    ) -> tuple[float, list[Component]]:
        """
        Calculate component overlap similarity.

        Returns similarity score and list of shared components.
        """
        set1 = set(components1)
        set2 = set(components2)

        if not set1 or not set2:
            return 0.0, []

        intersection = set1 & set2
        union = set1 | set2

        # Jaccard similarity
        similarity = len(intersection) / len(union) if union else 0.0

        return similarity, list(intersection)

    def _context_similarity(self, context1, context2) -> float:
        """
        Calculate context availability similarity.

        Compares context completeness and available context types.
        """
        # Completeness similarity
        completeness_diff = abs(
            context1.context_completeness_score - context2.context_completeness_score
        )
        completeness_sim = max(0.0, 1.0 - completeness_diff)

        # Available context types overlap
        set1 = set(context1.available_context_types)
        set2 = set(context2.available_context_types)

        overlap = len(set1 & set2) / max(len(set1), len(set2)) if set1 or set2 else 0.0

        # Weighted average
        return completeness_sim * 0.6 + overlap * 0.4

    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic text similarity.

        PLACEHOLDER: Would use actual embeddings in production.
        For now, uses simple word overlap as approximation.
        """
        if not text1 or not text2:
            return 0.0

        # Simple word overlap (placeholder)
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0

    def _apply_filters(
        self,
        candidates: list[TaskCharacteristics],
        query: TaskCharacteristicsQuery,
    ) -> list[TaskCharacteristics]:
        """Apply structured filters before similarity matching."""
        filtered = candidates

        # Filter by task type
        if query.filter_by_task_type:
            filtered = [c for c in filtered if c.task_type in query.filter_by_task_type]

        # Filter by component
        if query.filter_by_component:
            filtered = [
                c
                for c in filtered
                if any(
                    comp in c.affected_components for comp in query.filter_by_component
                )
            ]

        # Filter by code examples requirement
        if query.require_code_examples:
            filtered = [c for c in filtered if c.context.has_code_examples]

        return filtered

    @staticmethod
    def _complexity_level_to_int(level: ComplexityLevel) -> int:
        """Convert complexity level to integer for distance calculation."""
        mapping = {
            ComplexityLevel.TRIVIAL: 0,
            ComplexityLevel.SIMPLE: 1,
            ComplexityLevel.MODERATE: 2,
            ComplexityLevel.COMPLEX: 3,
            ComplexityLevel.VERY_COMPLEX: 4,
        }
        return mapping.get(level, 2)

    def _validate_weights(self):
        """Validate that weights sum to approximately 1.0."""
        total = sum(self.weights.values())
        if not (0.95 <= total <= 1.05):
            raise ValueError(f"Similarity weights must sum to ~1.0, got {total:.2f}")


class TaskCharacteristicsValidator:
    """
    Validator for task characteristics extraction quality.

    Validates:
    - Completeness of extracted characteristics
    - Consistency of derived values
    - Quality of context assessment
    - Feasibility of autonomous execution scores
    """

    def validate(self, characteristics: TaskCharacteristics) -> dict[str, Any]:
        """
        Comprehensive validation of task characteristics.

        Args:
            characteristics: TaskCharacteristics to validate

        Returns:
            Validation result dictionary with errors, warnings, and scores
        """
        errors = []
        warnings = []

        # 1. Validate task type classification
        if characteristics.task_type == TaskType.UNKNOWN:
            warnings.append("Task type could not be determined - manual review needed")

        # 2. Validate complexity assessment
        if characteristics.complexity.complexity_score == 0.0:
            errors.append("Complexity score is 0.0 - assessment failed")

        if characteristics.complexity.estimated_files_affected == 0:
            warnings.append("No estimated files - scope may be unclear")

        # 3. Validate context assessment
        if characteristics.context.context_completeness_score < 0.3:
            warnings.append(
                "Low context completeness (<30%) - task may lack necessary information"
            )

        if (
            characteristics.context.required_context_types
            and not characteristics.context.available_context_types
        ):
            warnings.append(
                "Required context identified but none available - execution may be difficult"
            )

        # 4. Validate components
        if not characteristics.affected_components:
            errors.append("No affected components identified")

        if (
            Component.UNKNOWN_COMPONENT in characteristics.affected_components
            and len(characteristics.affected_components) == 1
        ):
            warnings.append(
                "Only unknown components identified - categorization needed"
            )

        # 5. Validate autonomous execution feasibility
        if characteristics.autonomous_execution_feasibility > 0.8:
            if characteristics.complexity.complexity_score > 0.8:
                warnings.append(
                    "High feasibility with high complexity - may be overly optimistic"
                )

        # 6. Validate consistency
        if characteristics.change_scope == ChangeScope.SINGLE_FILE:
            if characteristics.complexity.estimated_files_affected > 1:
                errors.append(
                    "Inconsistent: Single file scope but multiple files estimated"
                )

        # Calculate completeness score
        completeness_factors = [
            characteristics.task_type != TaskType.UNKNOWN,
            characteristics.complexity.complexity_score > 0.0,
            len(characteristics.affected_components) > 0,
            characteristics.context.context_completeness_score > 0.0,
            characteristics.metadata.feature_label is not None,
        ]

        completeness_score = sum(completeness_factors) / len(completeness_factors)

        # Determine extraction quality
        if completeness_score >= 0.9 and not errors:
            quality = "excellent"
        elif completeness_score >= 0.7 and not errors:
            quality = "good"
        elif completeness_score >= 0.5:
            quality = "fair"
        else:
            quality = "poor"

        return {
            "is_valid": len(errors) == 0,
            "validation_errors": errors,
            "validation_warnings": warnings,
            "completeness_score": completeness_score,
            "extraction_quality": quality,
        }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def create_similarity_query(
    target: TaskCharacteristics,
    min_threshold: float = 0.7,
    max_results: int = 10,
    **filters,
) -> TaskCharacteristicsQuery:
    """
    Create a similarity query with common defaults.

    Args:
        target: Target task characteristics
        min_threshold: Minimum similarity threshold
        max_results: Maximum results to return
        **filters: Additional filter parameters

    Returns:
        TaskCharacteristicsQuery object
    """
    return TaskCharacteristicsQuery(
        target_characteristics=target,
        min_similarity_threshold=min_threshold,
        max_results=max_results,
        filter_by_task_type=filters.get("task_types"),
        filter_by_component=filters.get("components"),
        require_code_examples=filters.get("require_examples", False),
    )


def explain_similarity(match: SimilarityMatch) -> str:
    """
    Generate human-readable explanation of similarity match.

    Args:
        match: SimilarityMatch object

    Returns:
        Formatted explanation string
    """
    lines = [
        f"Similarity Score: {match.similarity_score:.2%}",
        f"Task: {match.task_characteristics.metadata.title}",
        "Matching Characteristics:",
    ]

    for char in match.matching_characteristics:
        lines.append(f"  - {char}")

    return "\n".join(lines)
