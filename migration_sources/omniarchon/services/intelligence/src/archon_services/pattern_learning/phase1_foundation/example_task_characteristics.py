#!/usr/bin/env python3
"""
Example Task Characteristics for Common Task Types

This module provides example task characteristics for training and testing
the autonomous agent selection system. These examples represent typical
task patterns observed in the Archon system.

Part of Track 4 Autonomous System (Pattern Learning Engine).

Author: Archon Intelligence Team
Date: 2025-10-02
"""

from uuid import UUID, uuid4

from src.archon_services.pattern_learning.phase1_foundation.models.model_task_characteristics import (
    EnumChangeScope,
    EnumComplexity,
    EnumTaskType,
    ModelTaskCharacteristics,
)

# ============================================================================
# Code Generation Task Examples
# ============================================================================

EXAMPLE_CODE_GENERATION_SIMPLE = ModelTaskCharacteristics(
    task_id=uuid4(),
    task_type=EnumTaskType.CODE_GENERATION,
    complexity=EnumComplexity.SIMPLE,
    change_scope=EnumChangeScope.SINGLE_FILE,
    has_sources=True,
    has_code_examples=True,
    has_acceptance_criteria=True,
    estimated_files_affected=1,
    affected_components=["api"],
    feature_label="api_endpoints",
    estimated_tokens=2000,
    title_normalized="add new api endpoint for user profile",
    description_normalized="create get endpoint users profile with authentication",
    keywords=["api", "endpoint", "user", "profile", "get"],
)

EXAMPLE_CODE_GENERATION_COMPLEX = ModelTaskCharacteristics(
    task_id=uuid4(),
    task_type=EnumTaskType.CODE_GENERATION,
    complexity=EnumComplexity.COMPLEX,
    change_scope=EnumChangeScope.MULTIPLE_MODULES,
    has_sources=True,
    has_code_examples=True,
    has_acceptance_criteria=True,
    estimated_files_affected=15,
    affected_components=["auth", "api", "database", "cache"],
    feature_label="authentication",
    estimated_tokens=12000,
    title_normalized="implement oauth2 authentication system",
    description_normalized="build comprehensive oauth2 authentication multiple providers jwt tokens session management",
    keywords=[
        "oauth2",
        "authentication",
        "jwt",
        "session",
        "providers",
        "tokens",
    ],
)

# ============================================================================
# Debugging Task Examples
# ============================================================================

EXAMPLE_DEBUGGING_SIMPLE = ModelTaskCharacteristics(
    task_id=uuid4(),
    task_type=EnumTaskType.DEBUGGING,
    complexity=EnumComplexity.SIMPLE,
    change_scope=EnumChangeScope.SINGLE_FILE,
    has_sources=False,
    has_code_examples=False,
    has_acceptance_criteria=False,
    estimated_files_affected=1,
    affected_components=["api"],
    feature_label="bug_fix",
    estimated_tokens=1500,
    title_normalized="fix null pointer error in user service",
    description_normalized="debug null pointer exception users service endpoint",
    keywords=["fix", "null", "pointer", "error", "users", "service"],
)

EXAMPLE_DEBUGGING_COMPLEX = ModelTaskCharacteristics(
    task_id=uuid4(),
    task_type=EnumTaskType.DEBUGGING,
    complexity=EnumComplexity.COMPLEX,
    change_scope=EnumChangeScope.MULTIPLE_FILES,
    has_sources=True,
    has_code_examples=False,
    has_acceptance_criteria=True,
    estimated_files_affected=5,
    affected_components=["database", "cache", "queue"],
    feature_label="performance_issue",
    estimated_tokens=8000,
    title_normalized="investigate race condition in event processing",
    description_normalized="debug race condition event processing system multiple subscribers concurrent updates",
    keywords=[
        "race",
        "condition",
        "event",
        "processing",
        "concurrent",
        "debug",
    ],
)

# ============================================================================
# Refactoring Task Examples
# ============================================================================

EXAMPLE_REFACTORING_MODERATE = ModelTaskCharacteristics(
    task_id=uuid4(),
    task_type=EnumTaskType.REFACTORING,
    complexity=EnumComplexity.MODERATE,
    change_scope=EnumChangeScope.SINGLE_MODULE,
    has_sources=False,
    has_code_examples=True,
    has_acceptance_criteria=True,
    estimated_files_affected=8,
    affected_components=["pattern", "intelligence"],
    feature_label="code_quality",
    estimated_tokens=6000,
    title_normalized="refactor pattern learning engine structure",
    description_normalized="reorganize pattern learning engine better modularity clean imports onex patterns",
    keywords=[
        "refactor",
        "pattern",
        "learning",
        "modularity",
        "structure",
    ],
)

# ============================================================================
# Testing Task Examples
# ============================================================================

EXAMPLE_TESTING_MODERATE = ModelTaskCharacteristics(
    task_id=uuid4(),
    task_type=EnumTaskType.TESTING,
    complexity=EnumComplexity.MODERATE,
    change_scope=EnumChangeScope.MULTIPLE_FILES,
    has_sources=True,
    has_code_examples=True,
    has_acceptance_criteria=True,
    estimated_files_affected=5,
    affected_file_patterns=["test_*.py", "*.test.ts"],
    affected_components=["api", "testing"],
    feature_label="test_coverage",
    estimated_tokens=5000,
    title_normalized="add integration tests for rag query flow",
    description_normalized="create comprehensive integration tests rag query orchestration vector search knowledge graph",
    keywords=[
        "test",
        "integration",
        "rag",
        "query",
        "orchestration",
    ],
)

# ============================================================================
# Documentation Task Examples
# ============================================================================

EXAMPLE_DOCUMENTATION_SIMPLE = ModelTaskCharacteristics(
    task_id=uuid4(),
    task_type=EnumTaskType.DOCUMENTATION,
    complexity=EnumComplexity.SIMPLE,
    change_scope=EnumChangeScope.SINGLE_FILE,
    has_sources=False,
    has_code_examples=False,
    has_acceptance_criteria=True,
    estimated_files_affected=1,
    affected_file_patterns=["*.md"],
    affected_components=["documentation"],
    feature_label="docs",
    estimated_tokens=2000,
    title_normalized="update readme with installation instructions",
    description_normalized="add comprehensive installation instructions readme docker setup environment variables",
    keywords=["readme", "installation", "instructions", "setup", "docker"],
)

# ============================================================================
# Architecture Task Examples
# ============================================================================

EXAMPLE_ARCHITECTURE_COMPLEX = ModelTaskCharacteristics(
    task_id=uuid4(),
    task_type=EnumTaskType.ARCHITECTURE,
    complexity=EnumComplexity.VERY_COMPLEX,
    change_scope=EnumChangeScope.SYSTEM_WIDE,
    has_sources=True,
    has_code_examples=True,
    has_acceptance_criteria=True,
    estimated_files_affected=50,
    affected_components=[
        "api",
        "database",
        "cache",
        "queue",
        "service",
        "intelligence",
    ],
    feature_label="autonomous_system",
    estimated_tokens=25000,
    title_normalized="design autonomous agent orchestration system",
    description_normalized="design comprehensive autonomous agent orchestration pattern matching task routing multi agent coordination",
    keywords=[
        "architecture",
        "autonomous",
        "agent",
        "orchestration",
        "pattern",
        "matching",
    ],
)

# ============================================================================
# Performance Optimization Task Examples
# ============================================================================

EXAMPLE_PERFORMANCE_MODERATE = ModelTaskCharacteristics(
    task_id=uuid4(),
    task_type=EnumTaskType.PERFORMANCE,
    complexity=EnumComplexity.MODERATE,
    change_scope=EnumChangeScope.MULTIPLE_FILES,
    has_sources=True,
    has_code_examples=True,
    has_acceptance_criteria=True,
    estimated_files_affected=8,
    affected_components=["database", "cache", "api"],
    feature_label="optimization",
    estimated_tokens=7000,
    title_normalized="optimize database query performance",
    description_normalized="improve database query performance add indexes caching reduce n+1 queries",
    keywords=[
        "optimize",
        "performance",
        "database",
        "query",
        "indexes",
        "cache",
    ],
)

# ============================================================================
# Security Task Examples
# ============================================================================

EXAMPLE_SECURITY_COMPLEX = ModelTaskCharacteristics(
    task_id=uuid4(),
    task_type=EnumTaskType.SECURITY,
    complexity=EnumComplexity.COMPLEX,
    change_scope=EnumChangeScope.MULTIPLE_MODULES,
    has_sources=True,
    has_code_examples=True,
    has_acceptance_criteria=True,
    estimated_files_affected=12,
    affected_components=["auth", "api", "security"],
    feature_label="security_hardening",
    estimated_tokens=10000,
    title_normalized="implement rate limiting and ddos protection",
    description_normalized="add rate limiting ddos protection api endpoints security headers authentication",
    keywords=[
        "security",
        "rate",
        "limiting",
        "ddos",
        "protection",
        "authentication",
    ],
)

# ============================================================================
# Integration Task Examples
# ============================================================================

EXAMPLE_INTEGRATION_MODERATE = ModelTaskCharacteristics(
    task_id=uuid4(),
    task_type=EnumTaskType.INTEGRATION,
    complexity=EnumComplexity.MODERATE,
    change_scope=EnumChangeScope.CROSS_SERVICE,
    has_sources=True,
    has_code_examples=True,
    has_acceptance_criteria=True,
    estimated_files_affected=10,
    affected_components=["api", "service", "mcp"],
    feature_label="mcp_integration",
    estimated_tokens=8000,
    title_normalized="integrate archon mcp with claude code",
    description_normalized="integrate archon mcp server claude code client setup configuration tools",
    keywords=["integrate", "mcp", "archon", "claude", "code", "client"],
)

# ============================================================================
# Collection of All Examples
# ============================================================================

ALL_EXAMPLES = [
    EXAMPLE_CODE_GENERATION_SIMPLE,
    EXAMPLE_CODE_GENERATION_COMPLEX,
    EXAMPLE_DEBUGGING_SIMPLE,
    EXAMPLE_DEBUGGING_COMPLEX,
    EXAMPLE_REFACTORING_MODERATE,
    EXAMPLE_TESTING_MODERATE,
    EXAMPLE_DOCUMENTATION_SIMPLE,
    EXAMPLE_ARCHITECTURE_COMPLEX,
    EXAMPLE_PERFORMANCE_MODERATE,
    EXAMPLE_SECURITY_COMPLEX,
    EXAMPLE_INTEGRATION_MODERATE,
]

# Group by task type for pattern analysis
EXAMPLES_BY_TYPE = {
    EnumTaskType.CODE_GENERATION: [
        EXAMPLE_CODE_GENERATION_SIMPLE,
        EXAMPLE_CODE_GENERATION_COMPLEX,
    ],
    EnumTaskType.DEBUGGING: [
        EXAMPLE_DEBUGGING_SIMPLE,
        EXAMPLE_DEBUGGING_COMPLEX,
    ],
    EnumTaskType.REFACTORING: [EXAMPLE_REFACTORING_MODERATE],
    EnumTaskType.TESTING: [EXAMPLE_TESTING_MODERATE],
    EnumTaskType.DOCUMENTATION: [EXAMPLE_DOCUMENTATION_SIMPLE],
    EnumTaskType.ARCHITECTURE: [EXAMPLE_ARCHITECTURE_COMPLEX],
    EnumTaskType.PERFORMANCE: [EXAMPLE_PERFORMANCE_MODERATE],
    EnumTaskType.SECURITY: [EXAMPLE_SECURITY_COMPLEX],
    EnumTaskType.INTEGRATION: [EXAMPLE_INTEGRATION_MODERATE],
}

# Group by complexity for analysis
EXAMPLES_BY_COMPLEXITY = {
    EnumComplexity.SIMPLE: [
        EXAMPLE_CODE_GENERATION_SIMPLE,
        EXAMPLE_DEBUGGING_SIMPLE,
        EXAMPLE_DOCUMENTATION_SIMPLE,
    ],
    EnumComplexity.MODERATE: [
        EXAMPLE_REFACTORING_MODERATE,
        EXAMPLE_TESTING_MODERATE,
        EXAMPLE_PERFORMANCE_MODERATE,
        EXAMPLE_INTEGRATION_MODERATE,
    ],
    EnumComplexity.COMPLEX: [
        EXAMPLE_CODE_GENERATION_COMPLEX,
        EXAMPLE_DEBUGGING_COMPLEX,
        EXAMPLE_SECURITY_COMPLEX,
    ],
    EnumComplexity.VERY_COMPLEX: [EXAMPLE_ARCHITECTURE_COMPLEX],
}


# NOTE: correlation_id support enabled for tracing
def get_example_by_type(task_type: EnumTaskType) -> list[ModelTaskCharacteristics]:
    """
    Get example characteristics for a specific task type.

    Args:
        task_type: Task type to get examples for

    Returns:
        List of example characteristics
    """
    return EXAMPLES_BY_TYPE.get(task_type, [])


def get_example_by_complexity(
    complexity: EnumComplexity,
) -> list[ModelTaskCharacteristics]:
    """
    Get example characteristics for a specific complexity level.

    Args:
        complexity: Complexity level to get examples for

    Returns:
        List of example characteristics
    """
    return EXAMPLES_BY_COMPLEXITY.get(complexity, [])


def print_example_summary():
    """Print summary of all example characteristics."""
    print("\n" + "=" * 70)
    print("Example Task Characteristics Summary")
    print("=" * 70)

    for task_type, examples in EXAMPLES_BY_TYPE.items():
        if examples:
            print(f"\n{task_type.value.upper().replace('_', ' ')}:")
            for example in examples:
                print(f"  - {example.title_normalized}")
                print(f"    Complexity: {example.complexity.value}")
                print(f"    Scope: {example.change_scope.value}")
                print(f"    Est. Files: {example.estimated_files_affected}")
                print(f"    Est. Tokens: {example.estimated_tokens}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    print_example_summary()
