#!/usr/bin/env python3
"""
Task Characteristics Extractor - ONEX Compute Node

Extracts comprehensive task characteristics from Archon tasks for
autonomous agent selection and pattern matching.

Part of Track 4 Autonomous System (Pattern Learning Engine).

Author: Archon Intelligence Team
Date: 2025-10-02
"""

import re
import time
from collections import Counter
from typing import Dict, List, Optional

from src.archon_services.pattern_learning.phase1_foundation.models.model_task_characteristics import (
    EnumChangeScope,
    EnumComplexity,
    EnumTaskType,
    ModelTaskCharacteristics,
    ModelTaskCharacteristicsInput,
    ModelTaskCharacteristicsOutput,
)

# ============================================================================
# ONEX Compute Node Implementation
# ============================================================================


class NodeTaskCharacteristicsExtractorCompute:
    """
    ONEX-Compliant Compute Node for Task Characteristics Extraction.

    Analyzes Archon tasks to extract comprehensive characteristics including:
    - Task type classification
    - Complexity estimation
    - Change scope prediction
    - Context availability detection
    - Impact estimation
    - Resource estimation

    ONEX Patterns:
    - Pure functional computation (no side effects)
    - Deterministic results for same inputs
    - Correlation ID propagation
    - Performance optimized (<100ms target)
    """

    # Task type keywords for classification
    TASK_TYPE_KEYWORDS: Dict[EnumTaskType, List[str]] = {
        EnumTaskType.CODE_GENERATION: [
            "create",
            "implement",
            "generate",
            "build",
            "develop",
            "add",
            "write",
            "setup",
        ],
        EnumTaskType.DEBUGGING: [
            "debug",
            "fix",
            "error",
            "bug",
            "issue",
            "problem",
            "crash",
            "fail",
        ],
        EnumTaskType.REFACTORING: [
            "refactor",
            "improve",
            "optimize",
            "restructure",
            "clean",
            "reorganize",
            "migrate",
        ],
        EnumTaskType.TESTING: [
            "test",
            "validate",
            "verify",
            "check",
            "assert",
            "spec",
            "unittest",
            "coverage",
        ],
        EnumTaskType.DOCUMENTATION: [
            "document",
            "explain",
            "describe",
            "comment",
            "annotate",
            "doc",
            "readme",
            "guide",
        ],
        EnumTaskType.ANALYSIS: [
            "analyze",
            "review",
            "inspect",
            "examine",
            "evaluate",
            "assess",
            "audit",
        ],
        EnumTaskType.ARCHITECTURE: [
            "architect",
            "design",
            "structure",
            "pattern",
            "framework",
            "system",
            "schema",
        ],
        EnumTaskType.PERFORMANCE: [
            "performance",
            "optimize",
            "speed",
            "benchmark",
            "profile",
            "latency",
            "throughput",
        ],
        EnumTaskType.SECURITY: [
            "security",
            "authentication",
            "authorization",
            "encrypt",
            "vulnerability",
            "audit",
        ],
        EnumTaskType.INTEGRATION: [
            "integrate",
            "connect",
            "api",
            "endpoint",
            "service",
            "interface",
        ],
        EnumTaskType.DEPLOYMENT: [
            "deploy",
            "release",
            "production",
            "container",
            "docker",
            "kubernetes",
        ],
        EnumTaskType.RESEARCH: [
            "research",
            "investigate",
            "explore",
            "evaluate",
            "compare",
            "study",
        ],
    }

    # Complexity indicators
    COMPLEXITY_INDICATORS = {
        "trivial": ["simple", "quick", "small", "minor", "trivial"],
        "simple": ["basic", "straightforward", "simple"],
        "moderate": ["moderate", "standard", "typical"],
        "complex": ["complex", "advanced", "comprehensive", "multiple"],
        "very_complex": [
            "very complex",
            "extensive",
            "large-scale",
            "system-wide",
        ],
    }

    # File pattern indicators
    FILE_PATTERNS = {
        "python": r"\.py$",
        "typescript": r"\.tsx?$",
        "test": r"test_.*\.py$|.*_test\.py$|.*\.test\.tsx?$",
        "config": r"\.(yaml|yml|json|toml|ini)$",
        "docker": r"Dockerfile|docker-compose",
        "docs": r"\.(md|rst|txt)$",
    }

    # Component keywords
    COMPONENT_KEYWORDS = [
        "api",
        "auth",
        "authentication",
        "database",
        "cache",
        "queue",
        "event",
        "service",
        "agent",
        "intelligence",
        "pattern",
        "search",
        "mcp",
        "frontend",
        "backend",
    ]

    def __init__(self) -> None:
        """Initialize task characteristics extractor."""
        # Pre-compile regex patterns for performance
        self._file_patterns_compiled = {
            name: re.compile(pattern) for name, pattern in self.FILE_PATTERNS.items()
        }

        # Statistics tracking
        self._extraction_count = 0
        self._total_processing_time = 0.0

    # ========================================================================
    # ONEX Execute Compute Method (Primary Interface)
    # ========================================================================

    async def execute_compute(
        self, input_state: ModelTaskCharacteristicsInput
    ) -> ModelTaskCharacteristicsOutput:
        """
        Execute task characteristics extraction (ONEX NodeCompute interface).

        Pure functional method with no side effects, deterministic results.

        Args:
            input_state: Input state with task information

        Returns:
            ModelTaskCharacteristicsOutput: Extracted characteristics with metadata
        """
        start_time = time.time()

        try:
            # Extract task type
            task_type = self._classify_task_type(
                input_state.title, input_state.description
            )

            # Estimate complexity
            complexity = self._estimate_complexity(
                input_state.title, input_state.description, input_state.sources
            )

            # Estimate change scope
            change_scope = self._estimate_change_scope(
                input_state.description, complexity
            )

            # Detect context availability
            has_sources = bool(input_state.sources)
            has_code_examples = bool(input_state.code_examples)
            has_acceptance_criteria = self._detect_acceptance_criteria(
                input_state.description
            )

            # Analyze dependencies
            is_subtask = input_state.parent_task_id is not None
            dependency_chain_length = 1 if is_subtask else 0

            # Estimate impact
            affected_file_patterns = self._extract_file_patterns(
                input_state.description
            )
            estimated_files_affected = self._estimate_file_count(
                complexity, change_scope, affected_file_patterns
            )
            affected_components = self._extract_components(
                input_state.title, input_state.description
            )

            # Extract keywords
            keywords = self._extract_keywords(
                input_state.title, input_state.description
            )

            # Estimate tokens
            estimated_tokens = self._estimate_tokens(
                input_state.description,
                has_sources,
                has_code_examples,
                complexity,
            )

            # Normalize text for embedding
            title_normalized = self._normalize_text(input_state.title)
            description_normalized = self._normalize_text(input_state.description)

            # Build characteristics
            characteristics = ModelTaskCharacteristics(
                task_id=input_state.task_id,
                correlation_id=input_state.correlation_id,
                task_type=task_type,
                complexity=complexity,
                change_scope=change_scope,
                has_sources=has_sources,
                has_code_examples=has_code_examples,
                has_acceptance_criteria=has_acceptance_criteria,
                dependency_chain_length=dependency_chain_length,
                is_subtask=is_subtask,
                affected_file_patterns=affected_file_patterns,
                estimated_files_affected=estimated_files_affected,
                affected_components=affected_components,
                feature_label=input_state.feature,
                estimated_tokens=estimated_tokens,
                title_normalized=title_normalized,
                description_normalized=description_normalized,
                keywords=keywords,
                metadata={
                    "assignee": input_state.assignee,
                    "source_count": len(input_state.sources or []),
                    "code_example_count": len(input_state.code_examples or []),
                },
            )

            # Calculate confidence
            confidence = self._calculate_confidence(characteristics)

            # Calculate processing time
            processing_time_ms = (time.time() - start_time) * 1000

            # Track statistics
            self._extraction_count += 1
            self._total_processing_time += processing_time_ms

            return ModelTaskCharacteristicsOutput(
                characteristics=characteristics,
                confidence=confidence,
                processing_time_ms=processing_time_ms,
                correlation_id=input_state.correlation_id,
                metadata={
                    "extraction_count": self._extraction_count,
                    "avg_processing_time_ms": self._total_processing_time
                    / self._extraction_count,
                },
            )

        except Exception as e:
            # Graceful error handling with fallback characteristics
            processing_time_ms = (time.time() - start_time) * 1000

            fallback_characteristics = ModelTaskCharacteristics(
                task_id=input_state.task_id,
                correlation_id=input_state.correlation_id,
                task_type=EnumTaskType.UNKNOWN,
                complexity=EnumComplexity.MODERATE,
                change_scope=EnumChangeScope.MULTIPLE_FILES,
                metadata={"error": str(e), "fallback": True},
            )

            return ModelTaskCharacteristicsOutput(
                characteristics=fallback_characteristics,
                confidence=0.0,
                processing_time_ms=processing_time_ms,
                correlation_id=input_state.correlation_id,
                metadata={"error": str(e)},
            )

    # ========================================================================
    # Pure Functional Classification Methods
    # ========================================================================

    def _classify_task_type(self, title: str, description: str) -> EnumTaskType:
        """
        Classify task type using keyword matching.

        Args:
            title: Task title
            description: Task description

        Returns:
            Classified task type
        """
        combined_text = f"{title} {description}".lower()
        tokens = self._tokenize(combined_text)

        # Score each task type
        scores: Dict[EnumTaskType, float] = {}
        for task_type, keywords in self.TASK_TYPE_KEYWORDS.items():
            score = sum(1.0 for keyword in keywords if keyword in tokens)
            scores[task_type] = score

        # Return type with highest score
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                return max(scores.items(), key=lambda x: x[1])[0]

        return EnumTaskType.UNKNOWN

    def _estimate_complexity(
        self,
        title: str,
        description: str,
        sources: Optional[List[Dict[str, str]]] = None,
    ) -> EnumComplexity:
        """
        Estimate task complexity using multiple indicators.

        Args:
            title: Task title
            description: Task description
            sources: Source references

        Returns:
            Estimated complexity level
        """
        combined_text = f"{title} {description}".lower()

        # Check complexity indicators
        complexity_scores = {
            EnumComplexity.TRIVIAL: 0.0,
            EnumComplexity.SIMPLE: 0.0,
            EnumComplexity.MODERATE: 1.0,  # Default baseline
            EnumComplexity.COMPLEX: 0.0,
            EnumComplexity.VERY_COMPLEX: 0.0,
        }

        # Keyword-based scoring
        for complexity_name, keywords in self.COMPLEXITY_INDICATORS.items():
            for keyword in keywords:
                if keyword in combined_text:
                    complexity_scores[EnumComplexity(complexity_name)] += 1.0

        # Length-based adjustment
        desc_length = len(description)
        if desc_length < 100:
            complexity_scores[EnumComplexity.TRIVIAL] += 0.5
        elif desc_length < 300:
            complexity_scores[EnumComplexity.SIMPLE] += 0.5
        elif desc_length < 800:
            complexity_scores[EnumComplexity.MODERATE] += 0.5
        elif desc_length < 1500:
            complexity_scores[EnumComplexity.COMPLEX] += 0.5
        else:
            complexity_scores[EnumComplexity.VERY_COMPLEX] += 0.5

        # Source count adjustment
        source_count = len(sources or [])
        if source_count == 0:
            complexity_scores[EnumComplexity.SIMPLE] += 0.3
        elif source_count > 5:
            complexity_scores[EnumComplexity.COMPLEX] += 0.3

        # Return highest scoring complexity
        return max(complexity_scores.items(), key=lambda x: x[1])[0]

    def _estimate_change_scope(
        self, description: str, complexity: EnumComplexity
    ) -> EnumChangeScope:
        """
        Estimate the scope of changes based on description and complexity.

        Args:
            description: Task description
            complexity: Task complexity

        Returns:
            Estimated change scope
        """
        desc_lower = description.lower()

        # Scope indicators
        scope_indicators = {
            EnumChangeScope.SINGLE_FUNCTION: ["function", "method", "single function"],
            EnumChangeScope.SINGLE_FILE: ["file", "single file", "one file"],
            EnumChangeScope.MULTIPLE_FILES: [
                "files",
                "multiple files",
                "several files",
            ],
            EnumChangeScope.SINGLE_MODULE: [
                "module",
                "package",
                "single module",
            ],
            EnumChangeScope.MULTIPLE_MODULES: [
                "modules",
                "multiple modules",
                "packages",
            ],
            EnumChangeScope.CROSS_SERVICE: [
                "service",
                "services",
                "cross-service",
                "microservice",
            ],
            EnumChangeScope.SYSTEM_WIDE: [
                "system",
                "system-wide",
                "entire system",
                "all services",
            ],
        }

        # Check for explicit scope mentions
        for scope, keywords in scope_indicators.items():
            if any(keyword in desc_lower for keyword in keywords):
                return scope

        # Fallback based on complexity
        complexity_to_scope = {
            EnumComplexity.TRIVIAL: EnumChangeScope.SINGLE_FUNCTION,
            EnumComplexity.SIMPLE: EnumChangeScope.SINGLE_FILE,
            EnumComplexity.MODERATE: EnumChangeScope.MULTIPLE_FILES,
            EnumComplexity.COMPLEX: EnumChangeScope.MULTIPLE_MODULES,
            EnumComplexity.VERY_COMPLEX: EnumChangeScope.SYSTEM_WIDE,
        }

        return complexity_to_scope.get(complexity, EnumChangeScope.MULTIPLE_FILES)

    def _detect_acceptance_criteria(self, description: str) -> bool:
        """
        Detect if task has explicit acceptance criteria.

        Args:
            description: Task description

        Returns:
            True if acceptance criteria detected
        """
        criteria_indicators = [
            "acceptance criteria",
            "success criteria",
            "requirements:",
            "must:",
            "should:",
            "- [ ]",  # Checklist
            "1.",  # Numbered list
            "deliverables:",
        ]

        desc_lower = description.lower()
        return any(indicator in desc_lower for indicator in criteria_indicators)

    def _extract_file_patterns(self, description: str) -> List[str]:
        """
        Extract file patterns mentioned in description.

        Args:
            description: Task description

        Returns:
            List of file patterns
        """
        patterns = []

        # Check for explicit file extensions
        for pattern_name, pattern_regex in self._file_patterns_compiled.items():
            if pattern_name in description.lower():
                patterns.append(f"*.{pattern_name}")

        # Check for common patterns
        if "test" in description.lower():
            patterns.append("test_*.py")
        if "model" in description.lower():
            patterns.append("model_*.py")
        if "node" in description.lower():
            patterns.append("node_*.py")

        return list(set(patterns))  # Remove duplicates

    def _estimate_file_count(
        self,
        complexity: EnumComplexity,
        change_scope: EnumChangeScope,
        file_patterns: List[str],
    ) -> int:
        """
        Estimate number of files affected.

        Args:
            complexity: Task complexity
            change_scope: Change scope
            file_patterns: Detected file patterns

        Returns:
            Estimated file count
        """
        # Base estimation from scope
        scope_to_count = {
            EnumChangeScope.SINGLE_FUNCTION: 1,
            EnumChangeScope.SINGLE_FILE: 1,
            EnumChangeScope.MULTIPLE_FILES: 5,
            EnumChangeScope.SINGLE_MODULE: 8,
            EnumChangeScope.MULTIPLE_MODULES: 15,
            EnumChangeScope.CROSS_SERVICE: 25,
            EnumChangeScope.SYSTEM_WIDE: 50,
        }

        base_count = scope_to_count.get(change_scope, 5)

        # Adjust for complexity
        complexity_multiplier = {
            EnumComplexity.TRIVIAL: 0.5,
            EnumComplexity.SIMPLE: 0.8,
            EnumComplexity.MODERATE: 1.0,
            EnumComplexity.COMPLEX: 1.5,
            EnumComplexity.VERY_COMPLEX: 2.0,
        }

        multiplier = complexity_multiplier.get(complexity, 1.0)

        return max(1, int(base_count * multiplier))

    def _extract_components(self, title: str, description: str) -> List[str]:
        """
        Extract affected components from title and description.

        Args:
            title: Task title
            description: Task description

        Returns:
            List of component names
        """
        combined_text = f"{title} {description}".lower()
        components = []

        for component in self.COMPONENT_KEYWORDS:
            if component in combined_text:
                components.append(component)

        return components

    def _extract_keywords(self, title: str, description: str) -> List[str]:
        """
        Extract important keywords for semantic matching.

        Args:
            title: Task title
            description: Task description

        Returns:
            List of keywords
        """
        combined_text = f"{title} {description}"
        tokens = self._tokenize(combined_text.lower())

        # Filter stop words and get most common
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
        }

        filtered_tokens = [t for t in tokens if t not in stop_words and len(t) > 2]

        # Get top keywords by frequency
        counter = Counter(filtered_tokens)
        top_keywords = [word for word, _ in counter.most_common(10)]

        return top_keywords

    def _estimate_tokens(
        self,
        description: str,
        has_sources: bool,
        has_code_examples: bool,
        complexity: EnumComplexity,
    ) -> int:
        """
        Estimate token count for task completion.

        Args:
            description: Task description
            has_sources: Whether sources are provided
            has_code_examples: Whether code examples are provided
            complexity: Task complexity

        Returns:
            Estimated token count
        """
        # Base tokens from description
        base_tokens = len(description) // 4  # Rough estimate: 4 chars per token

        # Complexity multiplier for context and generation
        complexity_tokens = {
            EnumComplexity.TRIVIAL: 1000,
            EnumComplexity.SIMPLE: 2000,
            EnumComplexity.MODERATE: 5000,
            EnumComplexity.COMPLEX: 10000,
            EnumComplexity.VERY_COMPLEX: 20000,
        }

        total_tokens = base_tokens + complexity_tokens.get(complexity, 5000)

        # Add tokens for sources and examples
        if has_sources:
            total_tokens += 1000  # Additional context from sources
        if has_code_examples:
            total_tokens += 2000  # Additional context from examples

        return total_tokens

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for embedding generation.

        Args:
            text: Input text

        Returns:
            Normalized text
        """
        # Remove extra whitespace
        normalized = " ".join(text.split())

        # Remove special characters but keep semantic meaning
        normalized = re.sub(r"[^\w\s\-_]", " ", normalized)

        # Lowercase
        normalized = normalized.lower()

        return normalized.strip()

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words.

        Args:
            text: Input text

        Returns:
            List of tokens
        """
        return re.findall(r"\w+", text.lower())

    def _calculate_confidence(self, characteristics: ModelTaskCharacteristics) -> float:
        """
        Calculate extraction confidence based on completeness.

        Args:
            characteristics: Extracted characteristics

        Returns:
            Confidence score (0.0-1.0)
        """
        confidence_factors = []

        # Task type classification confidence
        if characteristics.task_type != EnumTaskType.UNKNOWN:
            confidence_factors.append(1.0)
        else:
            confidence_factors.append(0.3)

        # Keyword extraction completeness
        if len(characteristics.keywords) >= 3:
            confidence_factors.append(1.0)
        elif len(characteristics.keywords) > 0:
            confidence_factors.append(0.7)
        else:
            confidence_factors.append(0.4)

        # Component detection
        if len(characteristics.affected_components) > 0:
            confidence_factors.append(1.0)
        else:
            confidence_factors.append(0.6)

        # Context availability
        context_score = (
            sum(
                [
                    characteristics.has_sources,
                    characteristics.has_code_examples,
                    characteristics.has_acceptance_criteria,
                ]
            )
            / 3.0
        )
        confidence_factors.append(context_score)

        # Average all factors
        return sum(confidence_factors) / len(confidence_factors)
