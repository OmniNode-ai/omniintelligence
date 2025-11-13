"""
Task Characteristics Extractor

Extracts TaskCharacteristics from Archon task objects for Track 3 and Track 4.

This module provides intelligent extraction logic that:
1. Analyzes task content to infer task type, complexity, and scope
2. Assesses available context and execution readiness
3. Identifies file patterns and affected components
4. Links historical patterns when available
5. Suggests execution patterns based on characteristics

The extractor uses NLP, heuristics, and pattern matching to derive
comprehensive characteristics from minimal task information.
"""

import re
from datetime import datetime
from typing import Any, Optional

from server.models.task_characteristics_models import (
    ChangeScope,
    ComplexityLevel,
    Component,
    ContextType,
    ExecutionPattern,
    TaskCharacteristics,
    TaskComplexityMetrics,
    TaskContext,
    TaskDependencies,
    TaskFilePatterns,
    TaskHistoricalContext,
    TaskMetadata,
    TaskType,
)


class TaskCharacteristicsExtractor:
    """
    Intelligent extractor for deriving task characteristics from Archon tasks.

    Usage:
        extractor = TaskCharacteristicsExtractor()
        characteristics = extractor.extract(archon_task)
        embedding_text = characteristics.to_embedding_text()
    """

    # Keyword patterns for task type classification
    TASK_TYPE_KEYWORDS = {
        TaskType.BUG_FIX: [
            "bug",
            "fix",
            "error",
            "issue",
            "broken",
            "crash",
            "failing",
            "incorrect",
            "wrong",
        ],
        TaskType.FEATURE_IMPLEMENTATION: [
            "implement",
            "add feature",
            "new feature",
            "create",
            "build",
            "develop",
        ],
        TaskType.TEST_WRITING: [
            "test",
            "unit test",
            "integration test",
            "e2e test",
            "coverage",
            "spec",
        ],
        TaskType.TEST_DEBUGGING: [
            "test fail",
            "test error",
            "failing test",
            "debug test",
            "fix test",
        ],
        TaskType.DOCUMENTATION_CREATION: [
            "document",
            "docs",
            "readme",
            "guide",
            "tutorial",
            "write docs",
        ],
        TaskType.DOCUMENTATION_UPDATE: [
            "update docs",
            "fix documentation",
            "improve docs",
            "revise docs",
        ],
        TaskType.API_DOCUMENTATION: [
            "api docs",
            "api documentation",
            "swagger",
            "openapi",
            "endpoint docs",
        ],
        TaskType.REFACTORING: [
            "refactor",
            "restructure",
            "reorganize",
            "cleanup",
            "simplify",
        ],
        TaskType.PERFORMANCE_OPTIMIZATION: [
            "optimize",
            "performance",
            "speed up",
            "improve speed",
            "faster",
            "slow",
        ],
        TaskType.TECHNICAL_DEBT: [
            "technical debt",
            "tech debt",
            "debt",
            "legacy",
            "outdated",
        ],
        TaskType.INFRASTRUCTURE_SETUP: [
            "infrastructure",
            "setup",
            "configure",
            "provision",
            "deploy",
        ],
        TaskType.DEPLOYMENT: [
            "deploy",
            "deployment",
            "release",
            "production",
            "rollout",
        ],
        TaskType.DEVOPS_AUTOMATION: [
            "ci/cd",
            "pipeline",
            "automation",
            "jenkins",
            "github actions",
        ],
        TaskType.ARCHITECTURE_DESIGN: [
            "architecture",
            "design",
            "system design",
            "architecture",
        ],
        TaskType.API_DESIGN: [
            "api design",
            "api spec",
            "rest api",
            "graphql",
            "endpoint",
        ],
        TaskType.DATABASE_DESIGN: [
            "database",
            "schema",
            "migration",
            "model",
            "table",
        ],
        TaskType.DEBUG_INVESTIGATION: [
            "debug",
            "investigate",
            "root cause",
            "analyze",
            "troubleshoot",
        ],
        TaskType.RESEARCH: [
            "research",
            "investigate",
            "explore",
            "spike",
            "evaluate",
        ],
        TaskType.PROOF_OF_CONCEPT: [
            "poc",
            "proof of concept",
            "prototype",
            "experiment",
        ],
        TaskType.CODE_REVIEW: [
            "review",
            "code review",
            "pr review",
            "pull request",
        ],
        TaskType.SECURITY_AUDIT: [
            "security",
            "audit",
            "vulnerability",
            "penetration",
            "secure",
        ],
    }

    # Component patterns based on keywords
    COMPONENT_KEYWORDS = {
        Component.API_LAYER: ["api", "endpoint", "route", "handler"],
        Component.BUSINESS_LOGIC: ["service", "business", "logic", "domain"],
        Component.DATA_ACCESS: ["repository", "dao", "data access"],
        Component.AUTHENTICATION: ["auth", "authentication", "login", "jwt"],
        Component.AUTHORIZATION: ["authorization", "permission", "rbac", "acl"],
        Component.DATABASE_SCHEMA: ["schema", "migration", "table", "column"],
        Component.UI_COMPONENTS: ["component", "ui", "frontend", "react", "vue"],
        Component.STATE_MANAGEMENT: ["state", "redux", "vuex", "store"],
        Component.TESTING_COMPONENTS: ["test", "spec", "unit", "integration"],
        Component.CONFIGURATION: ["config", "settings", "environment"],
        Component.MONITORING: ["monitor", "metric", "observability", "alert"],
        Component.LOGGING: ["log", "logging", "logger"],
        Component.CACHING: ["cache", "redis", "memcache"],
        Component.CI_CD: ["ci", "cd", "pipeline", "github actions"],
    }

    # File extension to component mapping
    FILE_EXTENSION_COMPONENTS = {
        ".py": [Component.BUSINESS_LOGIC],
        ".ts": [Component.UI_COMPONENTS],
        ".tsx": [Component.UI_COMPONENTS],
        ".js": [Component.UI_COMPONENTS],
        ".jsx": [Component.UI_COMPONENTS],
        ".sql": [Component.DATABASE_SCHEMA],
        ".yml": [Component.CONFIGURATION],
        ".yaml": [Component.CONFIGURATION],
        ".json": [Component.CONFIGURATION],
        ".md": [Component.README],
    }

    def __init__(self):
        """Initialize the extractor."""
        self.extraction_version = "1.0.0"

    def extract(
        self,
        archon_task: dict[str, Any],
        historical_data: Optional[dict[str, Any]] = None,
    ) -> TaskCharacteristics:
        """
        Extract complete task characteristics from an Archon task.

        Args:
            archon_task: Archon task dictionary
            historical_data: Optional historical pattern data

        Returns:
            Complete TaskCharacteristics object
        """
        # Extract metadata
        metadata = self._extract_metadata(archon_task)

        # Classify task type
        task_type = self._classify_task_type(archon_task)

        # Assess complexity
        complexity = self._assess_complexity(archon_task)

        # Determine change scope
        change_scope = self._determine_change_scope(archon_task, complexity)

        # Extract context information
        context = self._extract_context(archon_task)

        # Extract dependencies
        dependencies = self._extract_dependencies(archon_task)

        # Extract file patterns
        file_patterns = self._extract_file_patterns(archon_task)

        # Identify affected components
        affected_components = self._identify_components(archon_task, file_patterns)

        # Extract historical context
        historical = self._extract_historical_context(
            archon_task, task_type, historical_data
        )

        # Suggest execution pattern
        execution_pattern = self._suggest_execution_pattern(
            task_type, complexity, context
        )

        # Extract assignee information
        assignee = archon_task.get("assignee", "User")

        # Get full description
        description_text = archon_task.get("description", "")

        return TaskCharacteristics(
            metadata=metadata,
            task_type=task_type,
            change_scope=change_scope,
            complexity=complexity,
            context=context,
            dependencies=dependencies,
            file_patterns=file_patterns,
            affected_components=affected_components,
            historical=historical,
            suggested_execution_pattern=execution_pattern,
            assignee=assignee,
            assignee_type="auto",  # Will be auto-determined by validator
            description_text=description_text,
            extracted_at=datetime.now(),
            extraction_version=self.extraction_version,
        )

    def _extract_metadata(self, task: dict[str, Any]) -> TaskMetadata:
        """Extract basic task metadata."""
        return TaskMetadata(
            task_id=task["id"],
            project_id=task["project_id"],
            title=task["title"],
            created_at=self._parse_datetime(task["created_at"]),
            updated_at=self._parse_datetime(task["updated_at"]),
            feature_label=task.get("feature"),
        )

    def _classify_task_type(self, task: dict[str, Any]) -> TaskType:
        """
        Classify task type using keyword matching and heuristics.

        Uses title and description to identify the most likely task type.
        """
        text = f"{task.get('title', '')} {task.get('description', '')}".lower()

        # Score each task type
        scores = {}
        for task_type, keywords in self.TASK_TYPE_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                scores[task_type] = score

        # Return highest scoring type, or UNKNOWN
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]

        return TaskType.UNKNOWN

    def _assess_complexity(self, task: dict[str, Any]) -> TaskComplexityMetrics:
        """
        Assess task complexity using multiple factors.

        Complexity factors:
        - Description length (longer = more complex)
        - Number of sources (more research = more complex)
        - Number of code examples (more examples = more guidance but also more complex)
        - Presence of acceptance criteria (detailed = more complex)
        - Parent task presence (subtask = potentially less complex)
        """
        description = task.get("description", "")
        sources = task.get("sources", [])
        code_examples = task.get("code_examples", [])
        parent_task_id = task.get("parent_task_id")

        # Base complexity from description length
        desc_words = len(description.split())
        desc_score = min(1.0, desc_words / 500)  # 500 words = max complexity

        # Adjust for sources and examples
        source_score = min(0.3, len(sources) * 0.05)  # Up to 0.3
        example_score = min(0.2, len(code_examples) * 0.05)  # Up to 0.2

        # Reduce complexity if it's a subtask
        subtask_penalty = -0.2 if parent_task_id else 0.0

        # Calculate total complexity
        complexity_score = max(
            0.0, min(1.0, desc_score + source_score + example_score + subtask_penalty)
        )

        # Determine complexity level
        if complexity_score < 0.2:
            level = ComplexityLevel.TRIVIAL
        elif complexity_score < 0.4:
            level = ComplexityLevel.SIMPLE
        elif complexity_score < 0.6:
            level = ComplexityLevel.MODERATE
        elif complexity_score < 0.8:
            level = ComplexityLevel.COMPLEX
        else:
            level = ComplexityLevel.VERY_COMPLEX

        # Estimate tokens (rough approximation)
        estimated_tokens = int(desc_words * 1.3)  # ~1.3 tokens per word

        # Estimate files affected based on description keywords
        file_keywords = ["file", "module", "component", "service"]
        estimated_files = sum(
            1 for keyword in file_keywords if keyword in description.lower()
        )
        estimated_files = max(1, estimated_files)  # At least 1 file

        return TaskComplexityMetrics(
            complexity_score=complexity_score,
            complexity_level=level,
            estimated_tokens=estimated_tokens,
            estimated_files_affected=estimated_files,
        )

    def _determine_change_scope(
        self, task: dict[str, Any], complexity: TaskComplexityMetrics
    ) -> ChangeScope:
        """
        Determine the scope of changes required.

        Uses description keywords and complexity to infer scope.
        """
        description = task.get("description", "").lower()

        # Check for explicit scope indicators
        if any(
            word in description
            for word in ["cross-repository", "multiple repositories", "multi-repo"]
        ):
            return ChangeScope.CROSS_REPOSITORY
        if any(
            word in description
            for word in ["repository-wide", "entire codebase", "全codebase"]
        ):
            return ChangeScope.REPOSITORY_WIDE
        if any(
            word in description
            for word in ["cross-service", "multiple services", "microservices"]
        ):
            return ChangeScope.CROSS_SERVICE
        if any(
            word in description
            for word in ["cross-module", "multiple modules", "several packages"]
        ):
            return ChangeScope.CROSS_MODULE
        if any(word in description for word in ["module", "package", "directory"]):
            return ChangeScope.MODULE
        if any(
            word in description for word in ["multiple files", "several files", "files"]
        ):
            return ChangeScope.MULTIPLE_FILES

        # Fall back to complexity-based inference
        estimated_files = complexity.estimated_files_affected
        if estimated_files == 1:
            return ChangeScope.SINGLE_FILE
        elif estimated_files <= 5:
            return ChangeScope.MULTIPLE_FILES
        elif estimated_files <= 10:
            return ChangeScope.MODULE
        else:
            return ChangeScope.CROSS_MODULE

    def _extract_context(self, task: dict[str, Any]) -> TaskContext:
        """Extract and assess available context information."""
        sources = task.get("sources", [])
        code_examples = task.get("code_examples", [])
        description = task.get("description", "")
        parent_task_id = task.get("parent_task_id")

        # Check for acceptance criteria
        has_acceptance_criteria = any(
            keyword in description.lower()
            for keyword in [
                "acceptance criteria",
                "must",
                "should",
                "requirements",
                "success criteria",
            ]
        )

        # Identify available context types
        available_context = []
        if sources:
            for source in sources:
                source_type = source.get("type", "").lower()
                if "documentation" in source_type:
                    available_context.append(ContextType.DOCUMENTATION_REFERENCE)
                elif "api" in source_type:
                    available_context.append(ContextType.API_SPECIFICATION)
                elif "design" in source_type:
                    available_context.append(ContextType.DESIGN_DOCUMENT)

        if code_examples:
            available_context.append(ContextType.CODE_EXAMPLE)

        if has_acceptance_criteria:
            available_context.append(ContextType.ACCEPTANCE_CRITERIA)

        if parent_task_id:
            available_context.append(ContextType.PARENT_TASK)

        # Determine required context (based on task characteristics)
        required_context = []
        if "api" in description.lower():
            required_context.append(ContextType.API_SPECIFICATION)
        if "design" in description.lower() or "architecture" in description.lower():
            required_context.append(ContextType.DESIGN_DOCUMENT)
        if "implement" in description.lower() or "feature" in description.lower():
            required_context.append(ContextType.ACCEPTANCE_CRITERIA)
            required_context.append(ContextType.CODE_EXAMPLE)

        # Calculate context completeness
        if required_context:
            completeness = len(set(available_context) & set(required_context)) / len(
                required_context
            )
        else:
            completeness = 1.0 if available_context else 0.5

        return TaskContext(
            has_sources=len(sources) > 0,
            has_code_examples=len(code_examples) > 0,
            has_acceptance_criteria=has_acceptance_criteria,
            has_parent_task=parent_task_id is not None,
            has_related_tasks=False,  # Would need to query related tasks
            required_context_types=required_context,
            available_context_types=available_context,
            context_completeness_score=completeness,
        )

    def _extract_dependencies(self, task: dict[str, Any]) -> TaskDependencies:
        """Extract dependency information."""
        parent_task_id = task.get("parent_task_id")

        # Calculate dependency chain length (would need recursive query)
        # For now, use simple heuristic
        chain_length = 1 if parent_task_id else 0

        return TaskDependencies(
            dependency_chain_length=chain_length,
            parent_task_id=parent_task_id,
            parent_task_type=None,  # Would need to fetch parent task
            blocking_task_count=0,  # Would need to query blocking tasks
            dependent_task_count=0,  # Would need to query dependent tasks
        )

    def _extract_file_patterns(self, task: dict[str, Any]) -> TaskFilePatterns:
        """
        Extract file patterns from description and code examples.

        Looks for file paths, extensions, and directory references.
        """
        description = task.get("description", "")
        code_examples = task.get("code_examples", [])

        # Extract patterns from code examples
        file_patterns = []
        directories = set()
        file_types = set()

        for example in code_examples:
            file_path = example.get("file", "")
            if file_path:
                # Extract directory
                parts = file_path.split("/")
                if len(parts) > 1:
                    directories.add("/".join(parts[:-1]))

                # Extract file extension
                if "." in file_path:
                    ext = "." + file_path.split(".")[-1]
                    file_types.add(ext)

                # Create pattern
                file_patterns.append(file_path)

        # Look for file paths in description using regex
        path_pattern = r"(?:src/|lib/|tests?/|components?/)[\w/]+\.[\w]+"
        matches = re.findall(path_pattern, description)
        for match in matches:
            file_patterns.append(match)
            if "." in match:
                ext = "." + match.split(".")[-1]
                file_types.add(ext)

        return TaskFilePatterns(
            affected_file_patterns=file_patterns,
            affected_directories=list(directories),
            primary_file_types=list(file_types),
        )

    def _identify_components(
        self, task: dict[str, Any], file_patterns: TaskFilePatterns
    ) -> list[Component]:
        """
        Identify affected system components.

        Uses keywords and file patterns to infer components.
        """
        text = f"{task.get('title', '')} {task.get('description', '')}".lower()
        components = set()

        # Keyword-based component identification
        for component, keywords in self.COMPONENT_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                components.add(component)

        # File extension-based component identification
        for file_type in file_patterns.primary_file_types:
            if file_type in self.FILE_EXTENSION_COMPONENTS:
                components.update(self.FILE_EXTENSION_COMPONENTS[file_type])

        # If no components identified, use UNKNOWN
        if not components:
            components.add(Component.UNKNOWN_COMPONENT)

        return list(components)

    def _extract_historical_context(
        self,
        task: dict[str, Any],
        task_type: TaskType,
        historical_data: Optional[dict[str, Any]],
    ) -> TaskHistoricalContext:
        """
        Extract historical pattern information.

        If historical_data is provided, uses actual historical metrics.
        Otherwise, provides default/empty values.
        """
        if historical_data:
            return TaskHistoricalContext(
                similar_task_count=historical_data.get("similar_count", 0),
                average_completion_time_hours=historical_data.get(
                    "avg_completion_hours"
                ),
                success_rate=historical_data.get("success_rate"),
                common_execution_pattern=historical_data.get("common_pattern"),
            )

        return TaskHistoricalContext(
            similar_task_count=0,
            average_completion_time_hours=None,
            success_rate=None,
            common_execution_pattern=None,
        )

    def _suggest_execution_pattern(
        self,
        task_type: TaskType,
        complexity: TaskComplexityMetrics,
        context: TaskContext,
    ) -> Optional[ExecutionPattern]:
        """
        Suggest execution pattern based on task characteristics.

        Uses heuristics to recommend appropriate execution approach.
        """
        # Bug fixes typically need reproduction first
        if task_type == TaskType.BUG_FIX:
            return ExecutionPattern.REPRODUCE_THEN_FIX

        # Debug investigations need root cause analysis
        if task_type == TaskType.DEBUG_INVESTIGATION:
            return ExecutionPattern.DEBUG_ROOT_CAUSE

        # Performance tasks need analysis first
        if task_type == TaskType.PERFORMANCE_OPTIMIZATION:
            return ExecutionPattern.ANALYZE_THEN_OPTIMIZE

        # Research tasks need spike then implement
        if task_type in [TaskType.RESEARCH, TaskType.PROOF_OF_CONCEPT]:
            return ExecutionPattern.SPIKE_THEN_IMPLEMENT

        # Test writing benefits from TDD if context is good
        if (
            task_type == TaskType.TEST_WRITING
            and context.context_completeness_score > 0.7
        ):
            return ExecutionPattern.TEST_DRIVEN_DEVELOPMENT

        # Refactoring should happen before extension
        if task_type == TaskType.REFACTORING:
            return ExecutionPattern.REFACTOR_THEN_EXTEND

        # Complex tasks with good context can be sequential
        if (
            complexity.complexity_score > 0.6
            and context.context_completeness_score > 0.7
        ):
            return ExecutionPattern.SEQUENTIAL_IMPLEMENTATION

        # Simple prototyping pattern for simple tasks
        if complexity.complexity_score < 0.4:
            return ExecutionPattern.PROTOTYPE_THEN_REFINE

        return ExecutionPattern.UNKNOWN_PATTERN

    @staticmethod
    def _parse_datetime(dt_str: str) -> datetime:
        """Parse datetime string from Archon task."""
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except Exception:
            return datetime.now()


# ============================================================================
# BATCH EXTRACTION UTILITIES
# ============================================================================


class BatchTaskCharacteristicsExtractor:
    """
    Batch extractor for processing multiple tasks efficiently.

    Supports:
    - Parallel extraction
    - Historical data integration
    - Progress tracking
    - Error handling
    """

    def __init__(self):
        """Initialize batch extractor."""
        self.extractor = TaskCharacteristicsExtractor()

    def extract_batch(
        self,
        tasks: list[dict[str, Any]],
        historical_data_map: Optional[dict[str, dict[str, Any]]] = None,
    ) -> list[TaskCharacteristics]:
        """
        Extract characteristics for a batch of tasks.

        Args:
            tasks: List of Archon task dictionaries
            historical_data_map: Optional map of task_id -> historical_data

        Returns:
            List of TaskCharacteristics objects
        """
        results = []
        historical_map = historical_data_map or {}

        for task in tasks:
            try:
                task_id = task.get("id")
                historical = historical_map.get(task_id)
                characteristics = self.extractor.extract(task, historical)
                results.append(characteristics)
            except Exception as e:
                # Log error but continue processing
                print(
                    f"Error extracting characteristics for task {task.get('id')}: {e}"
                )
                continue

        return results

    def extract_and_validate(
        self, task: dict[str, Any]
    ) -> tuple[Optional[TaskCharacteristics], list[str]]:
        """
        Extract and validate characteristics in one step.

        Args:
            task: Archon task dictionary

        Returns:
            Tuple of (characteristics, validation_errors)
        """
        try:
            characteristics = self.extractor.extract(task)
            errors = self._validate_extraction(characteristics)
            return characteristics, errors
        except Exception as e:
            return None, [f"Extraction failed: {e!s}"]

    @staticmethod
    def _validate_extraction(characteristics: TaskCharacteristics) -> list[str]:
        """Validate extracted characteristics."""
        errors = []

        # Check for UNKNOWN task type
        if characteristics.task_type == TaskType.UNKNOWN:
            errors.append("Could not determine task type")

        # Check for minimal context
        if characteristics.context.context_completeness_score < 0.3:
            errors.append("Insufficient context available")

        # Check for complexity assessment
        if characteristics.complexity.complexity_score == 0.0:
            errors.append("Could not assess task complexity")

        # Check for component identification
        if (
            Component.UNKNOWN_COMPONENT in characteristics.affected_components
            and len(characteristics.affected_components) == 1
        ):
            errors.append("Could not identify affected components")

        return errors
