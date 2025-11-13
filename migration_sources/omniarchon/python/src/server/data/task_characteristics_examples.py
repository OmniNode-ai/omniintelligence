"""
Task Characteristics Example Instances

Comprehensive examples covering diverse task scenarios for Track 3 and Track 4.

These examples demonstrate:
1. Different task types (bug fix, feature, test, docs, etc.)
2. Various complexity levels (trivial to very complex)
3. Different change scopes (single file to cross-repository)
4. Context availability scenarios (rich context vs minimal context)
5. Component coverage (API, database, UI, infrastructure)
6. Execution patterns (TDD, debug-first, prototype, etc.)

Usage:
    from src.server.data.task_characteristics_examples import EXAMPLE_TASKS

    # Get specific example
    bug_fix_example = EXAMPLE_TASKS["simple_bug_fix"]

    # Test extraction logic
    extractor = TaskCharacteristicsExtractor()
    characteristics = extractor.extract(bug_fix_example["archon_task"])
"""

# ============================================================================
# EXAMPLE 1: Simple Bug Fix - High Context
# ============================================================================

SIMPLE_BUG_FIX = {
    "name": "simple_bug_fix",
    "description": "Single file bug fix with good context and code examples",
    "archon_task": {
        "id": "task-001-bug-fix",
        "project_id": "proj-001",
        "title": "Fix null pointer exception in user authentication",
        "description": """Bug: Users experiencing null pointer exception when logging in with OAuth.

Error trace shows issue in src/auth/oauth_provider.py at line 145.
Need to add null check before accessing user.email attribute.

Acceptance Criteria:
- No null pointer exceptions in auth flow
- All existing tests pass
- Add test case for null email scenario""",
        "status": "todo",
        "assignee": "AI IDE Agent",
        "task_order": 10,
        "feature": "authentication",
        "parent_task_id": None,
        "sources": [
            {
                "url": "https://docs.python.org/3/library/exceptions.html",
                "type": "documentation",
                "relevance": "Understanding AttributeError handling",
            }
        ],
        "code_examples": [
            {
                "file": "src/auth/oauth_provider.py",
                "function": "OAuthProvider.authenticate",
                "purpose": "Location of bug",
            },
            {
                "file": "tests/auth/test_oauth.py",
                "function": "test_oauth_authentication",
                "purpose": "Existing test pattern to follow",
            },
        ],
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
    },
    "expected_characteristics": {
        "task_type": "bug_fix",
        "complexity_level": "simple",
        "complexity_score_range": (0.2, 0.4),
        "change_scope": "single_file",
        "affected_components": ["authentication", "business_logic"],
        "context_completeness_min": 0.8,
        "autonomous_feasibility_min": 0.7,
        "suggested_execution_pattern": "reproduce_then_fix",
    },
}

# ============================================================================
# EXAMPLE 2: Feature Implementation - Moderate Complexity
# ============================================================================

FEATURE_IMPLEMENTATION = {
    "name": "feature_implementation",
    "description": "Multi-file feature with API and database changes",
    "archon_task": {
        "id": "task-002-feature",
        "project_id": "proj-001",
        "title": "Implement task filtering by assignee and status",
        "description": """Add filtering capabilities to task list API endpoint.

Requirements:
- Add query parameters: assignee, status, include_closed
- Update database query logic to support filters
- Add validation for filter parameters
- Update API documentation
- Maintain backwards compatibility

Files to modify:
- src/api/routes/tasks.py - Add query parameters
- src/services/task_service.py - Update list_tasks method
- src/models/task_models.py - Add filter validation
- docs/api/tasks.md - Update API documentation

Acceptance Criteria:
- Filter by single assignee works correctly
- Filter by status (todo/doing/review/done) works
- Combine multiple filters correctly
- Returns 400 for invalid filter values
- API documentation is updated and accurate""",
        "status": "todo",
        "assignee": "AI IDE Agent",
        "task_order": 5,
        "feature": "task_management",
        "parent_task_id": None,
        "sources": [
            {
                "url": "docs/architecture/api-design.md",
                "type": "design_document",
                "relevance": "API design patterns and conventions",
            },
            {
                "url": "https://flask.palletsprojects.com/en/2.3.x/quickstart/#accessing-request-data",
                "type": "documentation",
                "relevance": "Flask query parameter handling",
            },
        ],
        "code_examples": [
            {
                "file": "src/api/routes/projects.py",
                "function": "list_projects",
                "purpose": "Similar filtering pattern",
            },
            {
                "file": "src/services/project_service.py",
                "function": "list_projects",
                "purpose": "Service layer filtering example",
            },
        ],
        "created_at": "2025-01-14T14:00:00Z",
        "updated_at": "2025-01-14T14:00:00Z",
    },
    "expected_characteristics": {
        "task_type": "feature_implementation",
        "complexity_level": "moderate",
        "complexity_score_range": (0.4, 0.6),
        "change_scope": "multiple_files",
        "affected_components": ["api_layer", "business_logic", "api_docs"],
        "context_completeness_min": 0.7,
        "autonomous_feasibility_min": 0.6,
    },
}

# ============================================================================
# EXAMPLE 3: Test Writing - TDD Pattern
# ============================================================================

TEST_WRITING = {
    "name": "test_writing",
    "description": "Comprehensive test suite creation",
    "archon_task": {
        "id": "task-003-tests",
        "project_id": "proj-001",
        "title": "Write unit tests for task characteristics extractor",
        "description": """Create comprehensive unit test suite for TaskCharacteristicsExtractor.

Test Coverage Required:
- Task type classification (all task types)
- Complexity assessment edge cases
- Context extraction accuracy
- Component identification
- File pattern extraction
- Validation logic

Target coverage: >90%

Use pytest fixtures for common test data.
Follow existing test patterns in tests/services/""",
        "status": "todo",
        "assignee": "AI IDE Agent",
        "task_order": 15,
        "feature": "testing",
        "parent_task_id": None,
        "sources": [],
        "code_examples": [
            {
                "file": "tests/services/test_task_service.py",
                "function": "test_create_task",
                "purpose": "Test structure pattern",
            },
            {
                "file": "tests/conftest.py",
                "function": "sample_task_fixture",
                "purpose": "Fixture pattern",
            },
        ],
        "created_at": "2025-01-16T09:00:00Z",
        "updated_at": "2025-01-16T09:00:00Z",
    },
    "expected_characteristics": {
        "task_type": "test_writing",
        "complexity_level": "moderate",
        "change_scope": "single_file",
        "affected_components": ["unit_tests"],
        "suggested_execution_pattern": "test_driven_development",
    },
}

# ============================================================================
# EXAMPLE 4: Performance Optimization - Complex
# ============================================================================

PERFORMANCE_OPTIMIZATION = {
    "name": "performance_optimization",
    "description": "Database query optimization for slow endpoints",
    "archon_task": {
        "id": "task-004-perf",
        "project_id": "proj-001",
        "title": "Optimize slow task list query performance",
        "description": """Current task list API is taking 2-3 seconds for projects with 1000+ tasks.
Need to optimize database queries and add caching.

Performance Issues:
- N+1 query problem loading task sources and code examples
- Missing database indexes on project_id and status
- No query result caching

Optimization Plan:
1. Add database indexes
2. Implement eager loading for JSONB fields
3. Add Redis caching for common queries
4. Add query result pagination

Target: <200ms response time for 1000 task projects

Files affected:
- src/services/task_service.py - Query optimization
- migrations/ - New index migration
- src/cache/task_cache.py - Cache implementation
- src/api/routes/tasks.py - Pagination logic""",
        "status": "todo",
        "assignee": "Archon",
        "task_order": 20,
        "feature": "performance",
        "parent_task_id": None,
        "sources": [
            {
                "url": "https://www.postgresql.org/docs/current/indexes.html",
                "type": "documentation",
                "relevance": "PostgreSQL indexing strategies",
            },
            {
                "url": "docs/architecture/caching-strategy.md",
                "type": "design_document",
                "relevance": "Caching implementation guide",
            },
        ],
        "code_examples": [
            {
                "file": "src/services/project_service.py",
                "function": "list_projects",
                "purpose": "Pagination example",
            },
        ],
        "created_at": "2025-01-13T11:00:00Z",
        "updated_at": "2025-01-13T15:00:00Z",
    },
    "expected_characteristics": {
        "task_type": "performance_optimization",
        "complexity_level": "complex",
        "complexity_score_range": (0.6, 0.8),
        "change_scope": "cross_module",
        "affected_components": ["data_access", "caching", "migrations"],
        "suggested_execution_pattern": "analyze_then_optimize",
    },
}

# ============================================================================
# EXAMPLE 5: Documentation - Simple
# ============================================================================

DOCUMENTATION_TASK = {
    "name": "documentation_task",
    "description": "API documentation update",
    "archon_task": {
        "id": "task-005-docs",
        "project_id": "proj-001",
        "title": "Update API documentation for new task filtering parameters",
        "description": """Update task API documentation to reflect new filtering parameters.

Changes needed:
- Add query parameter descriptions (assignee, status, include_closed)
- Add example requests with filters
- Update response schema examples
- Add error response examples for invalid filters

File: docs/api/tasks.md

Follow existing documentation format and include curl examples.""",
        "status": "todo",
        "assignee": "User",
        "task_order": 25,
        "feature": "documentation",
        "parent_task_id": "task-002-feature",  # Child of feature implementation
        "sources": [
            {
                "url": "docs/style-guide.md",
                "type": "documentation",
                "relevance": "Documentation style guide",
            }
        ],
        "code_examples": [
            {
                "file": "docs/api/projects.md",
                "function": None,
                "purpose": "API docs format example",
            }
        ],
        "created_at": "2025-01-14T16:00:00Z",
        "updated_at": "2025-01-14T16:00:00Z",
    },
    "expected_characteristics": {
        "task_type": "documentation_update",
        "complexity_level": "simple",
        "change_scope": "single_file",
        "affected_components": ["api_docs"],
        "context_completeness_min": 0.6,
        "has_parent_task": True,
    },
}

# ============================================================================
# EXAMPLE 6: Architecture Design - High Complexity
# ============================================================================

ARCHITECTURE_DESIGN = {
    "name": "architecture_design",
    "description": "System architecture design task",
    "archon_task": {
        "id": "task-006-arch",
        "project_id": "proj-002",
        "title": "Design event-driven architecture for cross-service coordination",
        "description": """Design event-driven architecture to enable autonomous agent coordination.

Requirements:
- Event bus for agent communication
- Event schema standardization
- Event persistence and replay
- Dead letter queue handling
- Event correlation and causality tracking

Deliverables:
- Architecture design document
- Event schema specifications
- Sequence diagrams for key workflows
- Technology stack recommendations
- Migration strategy from current RPC model

This is a planning task - no code implementation required yet.""",
        "status": "todo",
        "assignee": "Archon",
        "task_order": 1,
        "feature": "agent_coordination",
        "parent_task_id": None,
        "sources": [
            {
                "url": "https://microservices.io/patterns/data/event-driven-architecture.html",
                "type": "documentation",
                "relevance": "Event-driven architecture patterns",
            },
            {
                "url": "docs/current-architecture.md",
                "type": "design_document",
                "relevance": "Current system architecture",
            },
        ],
        "code_examples": [],
        "created_at": "2025-01-10T08:00:00Z",
        "updated_at": "2025-01-12T14:00:00Z",
    },
    "expected_characteristics": {
        "task_type": "architecture_design",
        "complexity_level": "very_complex",
        "change_scope": "cross_service",
        "affected_components": ["event_system", "architecture_docs"],
    },
}

# ============================================================================
# EXAMPLE 7: Debug Investigation - Minimal Context
# ============================================================================

DEBUG_INVESTIGATION = {
    "name": "debug_investigation",
    "description": "Root cause analysis with minimal initial context",
    "archon_task": {
        "id": "task-007-debug",
        "project_id": "proj-001",
        "title": "Investigate intermittent WebSocket disconnections",
        "description": """Users reporting random WebSocket disconnections every 30-60 minutes.

Symptoms:
- Connection drops without error message
- Reconnection works immediately
- Happens across different browsers
- No obvious pattern in logs

Need to:
- Analyze server logs for patterns
- Check WebSocket timeout configurations
- Monitor connection lifecycle
- Identify root cause""",
        "status": "todo",
        "assignee": "agent-debug-intelligence",
        "task_order": 30,
        "feature": "websockets",
        "parent_task_id": None,
        "sources": [],
        "code_examples": [],
        "created_at": "2025-01-17T13:00:00Z",
        "updated_at": "2025-01-17T13:00:00Z",
    },
    "expected_characteristics": {
        "task_type": "debug_investigation",
        "complexity_level": "complex",
        "change_scope": "module",
        "context_completeness_score_max": 0.4,  # Low context
        "autonomous_feasibility_max": 0.5,  # Low feasibility due to investigation nature
        "suggested_execution_pattern": "debug_root_cause",
    },
}

# ============================================================================
# EXAMPLE 8: Infrastructure Setup - DevOps
# ============================================================================

INFRASTRUCTURE_SETUP = {
    "name": "infrastructure_setup",
    "description": "Kubernetes deployment configuration",
    "archon_task": {
        "id": "task-008-infra",
        "project_id": "proj-003",
        "title": "Setup Kubernetes deployment for production environment",
        "description": """Create Kubernetes manifests for production deployment.

Requirements:
- Deployment manifests for all services
- Service definitions with load balancing
- ConfigMaps for environment variables
- Secrets management for sensitive data
- Horizontal Pod Autoscaling configuration
- Ingress configuration with TLS
- Health check and readiness probes

Files to create:
- k8s/deployments/*.yaml
- k8s/services/*.yaml
- k8s/configmaps/*.yaml
- k8s/ingress.yaml
- k8s/hpa.yaml

Follow Kubernetes best practices for resource limits and security.""",
        "status": "todo",
        "assignee": "agent-devops-infrastructure",
        "task_order": 5,
        "feature": "infrastructure",
        "parent_task_id": None,
        "sources": [
            {
                "url": "https://kubernetes.io/docs/concepts/workloads/",
                "type": "documentation",
                "relevance": "Kubernetes workload management",
            },
            {
                "url": "docs/deployment/staging-k8s.yaml",
                "type": "code_example",
                "relevance": "Existing staging configuration",
            },
        ],
        "code_examples": [],
        "created_at": "2025-01-11T10:00:00Z",
        "updated_at": "2025-01-11T10:00:00Z",
    },
    "expected_characteristics": {
        "task_type": "infrastructure_setup",
        "complexity_level": "complex",
        "change_scope": "repository_wide",
        "affected_components": ["containerization", "orchestration"],
    },
}

# ============================================================================
# EXAMPLE 9: Refactoring - Technical Debt
# ============================================================================

REFACTORING_TASK = {
    "name": "refactoring_task",
    "description": "Code refactoring to reduce technical debt",
    "archon_task": {
        "id": "task-009-refactor",
        "project_id": "proj-001",
        "title": "Refactor task service to use dependency injection",
        "description": """Current TaskService directly instantiates Supabase client, making testing difficult.

Refactoring needed:
- Convert to dependency injection pattern
- Add interface/protocol for database client
- Update all service methods to use injected client
- Create mock client for testing
- Update all tests to use mock client
- Maintain backwards compatibility

Benefits:
- Easier unit testing
- Better separation of concerns
- More flexible for future database changes

Files affected:
- src/services/task_service.py - Main refactoring
- src/interfaces/database_client.py - New interface
- tests/services/test_task_service.py - Update tests
- tests/mocks/mock_database.py - New mock""",
        "status": "todo",
        "assignee": "AI IDE Agent",
        "task_order": 12,
        "feature": "code_quality",
        "parent_task_id": None,
        "sources": [
            {
                "url": "https://en.wikipedia.org/wiki/Dependency_injection",
                "type": "documentation",
                "relevance": "Dependency injection pattern",
            }
        ],
        "code_examples": [
            {
                "file": "src/services/intelligence_service.py",
                "function": "__init__",
                "purpose": "Existing DI pattern example",
            }
        ],
        "created_at": "2025-01-15T14:00:00Z",
        "updated_at": "2025-01-15T14:00:00Z",
    },
    "expected_characteristics": {
        "task_type": "refactoring",
        "complexity_level": "moderate",
        "change_scope": "module",
        "affected_components": ["business_logic", "unit_tests"],
        "suggested_execution_pattern": "refactor_then_extend",
    },
}

# ============================================================================
# EXAMPLE 10: Research Task - Proof of Concept
# ============================================================================

RESEARCH_POC = {
    "name": "research_poc",
    "description": "Technology research and proof of concept",
    "archon_task": {
        "id": "task-010-research",
        "project_id": "proj-002",
        "title": "Research and POC: LangGraph for multi-agent coordination",
        "description": """Evaluate LangGraph as potential framework for agent coordination.

Research Questions:
- Can LangGraph handle our agent communication patterns?
- Performance characteristics for 10+ concurrent agents?
- Integration complexity with existing architecture?
- State management capabilities?

POC Requirements:
- Simple 3-agent coordination example
- State persistence demonstration
- Error handling and recovery
- Performance benchmarks

Deliverable:
- Research findings document
- POC code in experiments/ directory
- Recommendation: adopt, modify, or reject
- Migration effort estimate if recommended""",
        "status": "todo",
        "assignee": "Archon",
        "task_order": 2,
        "feature": "agent_coordination",
        "parent_task_id": "task-006-arch",
        "sources": [
            {
                "url": "https://github.com/langchain-ai/langgraph",
                "type": "documentation",
                "relevance": "LangGraph documentation",
            }
        ],
        "code_examples": [],
        "created_at": "2025-01-12T09:00:00Z",
        "updated_at": "2025-01-12T09:00:00Z",
    },
    "expected_characteristics": {
        "task_type": "proof_of_concept",
        "complexity_level": "moderate",
        "change_scope": "module",
        "suggested_execution_pattern": "spike_then_implement",
    },
}

# ============================================================================
# EXAMPLE 11: Security Audit - Critical
# ============================================================================

SECURITY_AUDIT = {
    "name": "security_audit",
    "description": "Security vulnerability assessment",
    "archon_task": {
        "id": "task-011-security",
        "project_id": "proj-001",
        "title": "Security audit: API authentication and authorization",
        "description": """Comprehensive security review of API authentication and authorization.

Scope:
- JWT token validation
- Permission checking logic
- API key management
- Rate limiting implementation
- CORS configuration
- Input validation and sanitization

Deliverables:
- Security assessment report
- List of vulnerabilities with severity ratings
- Remediation recommendations with priorities
- Updated security documentation

Use OWASP API Security Top 10 as baseline.""",
        "status": "todo",
        "assignee": "agent-security-audit",
        "task_order": 1,
        "feature": "security",
        "parent_task_id": None,
        "sources": [
            {
                "url": "https://owasp.org/www-project-api-security/",
                "type": "documentation",
                "relevance": "OWASP API Security guidelines",
            }
        ],
        "code_examples": [],
        "created_at": "2025-01-16T08:00:00Z",
        "updated_at": "2025-01-16T08:00:00Z",
    },
    "expected_characteristics": {
        "task_type": "security_audit",
        "complexity_level": "complex",
        "change_scope": "cross_module",
        "affected_components": ["authentication", "authorization", "api_layer"],
    },
}

# ============================================================================
# EXAMPLE 12: Database Migration - Moderate
# ============================================================================

DATABASE_MIGRATION = {
    "name": "database_migration",
    "description": "Database schema change with data migration",
    "archon_task": {
        "id": "task-012-migration",
        "project_id": "proj-001",
        "title": "Add task_characteristics JSONB column to archon_tasks table",
        "description": """Add new column to store extracted task characteristics.

Changes:
- Add task_characteristics JSONB column to archon_tasks
- Create GIN index on task_characteristics for fast queries
- Backfill existing tasks with extracted characteristics
- Add validation trigger for JSONB schema

Migration steps:
1. Add column (nullable initially)
2. Create index
3. Run backfill script for existing tasks
4. Add NOT NULL constraint
5. Add validation trigger

Rollback plan:
- Save column creation as separate migration
- Ensure data backup before backfill

Files:
- migrations/add_task_characteristics_column.sql
- scripts/backfill_task_characteristics.py""",
        "status": "todo",
        "assignee": "AI IDE Agent",
        "task_order": 8,
        "feature": "task_intelligence",
        "parent_task_id": None,
        "sources": [
            {
                "url": "https://www.postgresql.org/docs/current/datatype-json.html",
                "type": "documentation",
                "relevance": "PostgreSQL JSONB documentation",
            }
        ],
        "code_examples": [
            {
                "file": "migrations/add_task_sources_column.sql",
                "function": None,
                "purpose": "Similar JSONB column migration",
            }
        ],
        "created_at": "2025-01-17T10:00:00Z",
        "updated_at": "2025-01-17T10:00:00Z",
    },
    "expected_characteristics": {
        "task_type": "database_design",
        "complexity_level": "moderate",
        "change_scope": "module",
        "affected_components": ["database_schema", "migrations"],
    },
}

# ============================================================================
# CONSOLIDATED EXAMPLES DICTIONARY
# ============================================================================

EXAMPLE_TASKS = {
    "simple_bug_fix": SIMPLE_BUG_FIX,
    "feature_implementation": FEATURE_IMPLEMENTATION,
    "test_writing": TEST_WRITING,
    "performance_optimization": PERFORMANCE_OPTIMIZATION,
    "documentation_task": DOCUMENTATION_TASK,
    "architecture_design": ARCHITECTURE_DESIGN,
    "debug_investigation": DEBUG_INVESTIGATION,
    "infrastructure_setup": INFRASTRUCTURE_SETUP,
    "refactoring_task": REFACTORING_TASK,
    "research_poc": RESEARCH_POC,
    "security_audit": SECURITY_AUDIT,
    "database_migration": DATABASE_MIGRATION,
}


# ============================================================================
# EXAMPLE USAGE
# ============================================================================


def get_example_by_complexity(complexity_level: str) -> list:
    """Get all examples matching a complexity level."""
    return [
        example
        for example in EXAMPLE_TASKS.values()
        if example.get("expected_characteristics", {}).get("complexity_level")
        == complexity_level
    ]


def get_example_by_task_type(task_type: str) -> list:
    """Get all examples matching a task type."""
    return [
        example
        for example in EXAMPLE_TASKS.values()
        if example.get("expected_characteristics", {}).get("task_type") == task_type
    ]


def get_high_context_examples() -> list:
    """Get examples with high context completeness."""
    return [
        example
        for example in EXAMPLE_TASKS.values()
        if example.get("expected_characteristics", {}).get(
            "context_completeness_min", 0
        )
        >= 0.7
    ]


def get_autonomous_ready_examples() -> list:
    """Get examples ready for autonomous execution."""
    return [
        example
        for example in EXAMPLE_TASKS.values()
        if example.get("expected_characteristics", {}).get(
            "autonomous_feasibility_min", 0
        )
        >= 0.6
    ]


if __name__ == "__main__":
    # Example usage
    print(f"Total example tasks: {len(EXAMPLE_TASKS)}")
    print(f"\nSimple tasks: {len(get_example_by_complexity('simple'))}")
    print(f"Moderate tasks: {len(get_example_by_complexity('moderate'))}")
    print(f"Complex tasks: {len(get_example_by_complexity('complex'))}")
    print(f"\nHigh context examples: {len(get_high_context_examples())}")
    print(f"Autonomous-ready examples: {len(get_autonomous_ready_examples())}")
