# Track 3 Autonomous Execution API - OpenAPI Specification

**Version**: 1.0.0
**Base URL**: `http://localhost:8053/api/autonomous`
**Performance Target**: <100ms response time for all endpoints

## Overview

This specification defines the Track 3 APIs consumed by the Track 4 Autonomous Execution System. These APIs provide intelligent predictions for agent selection, time estimation, safety assessment, and pattern learning.

## Authentication

**Current**: No authentication (internal service)
**Future**: Service-to-service JWT authentication

## API Endpoints

### 1. Agent Selection API

**Endpoint**: `POST /api/autonomous/predict/agent`
**Purpose**: Predict optimal agent for task execution
**Performance Target**: <100ms

#### Request Body

```json
{
  "task_description": "Implement OAuth2 authentication with Google provider",
  "task_type": "code_generation",
  "complexity": "complex",
  "change_scope": "module",
  "estimated_files_affected": 5,
  "requires_testing": true,
  "requires_validation": true,
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "context": {
    "framework": "FastAPI",
    "language": "python",
    "dependencies": ["authlib", "pydantic"]
  },
  "historical_similar_tasks": []
}
```

#### Response (200 OK)

```json
{
  "recommended_agent": "agent-api-architect",
  "confidence_score": 0.87,
  "confidence_level": "high",
  "reasoning": "Agent has 92% success rate on OAuth2 implementations with FastAPI",
  "alternative_agents": [
    {
      "agent_name": "agent-code-quality-analyzer",
      "confidence": 0.73,
      "reasoning": "Can assist with OAuth2 code quality verification",
      "estimated_success_rate": 0.85
    }
  ],
  "expected_success_rate": 0.92,
  "capability_match_score": 0.94,
  "historical_data_points": 47,
  "prediction_metadata": {
    "similar_tasks_found": 12,
    "average_duration_ms": 285000,
    "common_patterns_used": ["oauth2_pkce", "token_refresh"],
    "execution_time_ms": 45.2
  }
}
```

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `confidence_threshold` | float | 0.7 | Minimum confidence for recommendation (0.0-1.0) |

#### Error Responses

- **500 Internal Server Error**: Agent prediction failed
  ```json
  {
    "detail": "Agent prediction failed: <error message>"
  }
  ```

---

### 2. Time Estimation API

**Endpoint**: `POST /api/autonomous/predict/time`
**Purpose**: Estimate execution time with percentile predictions
**Performance Target**: <100ms

#### Request Body

```json
{
  "task_description": "Implement OAuth2 authentication with Google provider",
  "task_type": "code_generation",
  "complexity": "complex",
  "change_scope": "module",
  "estimated_files_affected": 5,
  "requires_testing": true,
  "requires_validation": true,
  "project_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent` | string | **Yes** | Agent that will execute the task |

#### Response (200 OK)

```json
{
  "estimated_duration_ms": 285000,
  "p25_duration_ms": 180000,
  "p75_duration_ms": 420000,
  "p95_duration_ms": 650000,
  "confidence_score": 0.82,
  "time_breakdown": {
    "planning_ms": 45000,
    "implementation_ms": 180000,
    "testing_ms": 40000,
    "review_ms": 15000,
    "overhead_ms": 5000
  },
  "historical_variance": 95000,
  "factors_affecting_time": [
    "complexity_of_oauth2_provider_integration",
    "test_coverage_requirements",
    "documentation_completeness"
  ],
  "similar_tasks_analyzed": 12,
  "estimation_metadata": {
    "execution_time_ms": 38.5,
    "agent_used": "agent-api-architect",
    "complexity": "complex",
    "baseline_duration_ms": 180000
  }
}
```

#### Error Responses

- **404 Not Found**: Agent not found in capabilities database
  ```json
  {
    "detail": "Agent 'agent-unknown' not found in capabilities database"
  }
  ```

- **500 Internal Server Error**: Time estimation failed
  ```json
  {
    "detail": "Time estimation failed: <error message>"
  }
  ```

---

### 3. Safety Score API

**Endpoint**: `POST /api/autonomous/calculate/safety`
**Purpose**: Calculate safety score for autonomous execution
**Performance Target**: <100ms

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_type` | string | **Yes** | Type of task (code_generation, bug_fix, etc.) |
| `complexity` | float | **Yes** | Task complexity score (0.0-1.0) |
| `change_scope` | string | **Yes** | Scope of changes (single_file, module, service, etc.) |
| `agent` | string | No | Specific agent for assessment |

#### Response (200 OK)

```json
{
  "safety_score": 0.78,
  "safety_rating": "caution",
  "can_execute_autonomously": true,
  "requires_human_review": true,
  "historical_success_rate": 0.88,
  "historical_failure_rate": 0.12,
  "risk_factors": [
    {
      "factor": "oauth2_security_complexity",
      "severity": "medium",
      "likelihood": 0.3,
      "mitigation": "Automated security scanning before deployment"
    },
    {
      "factor": "external_dependency_integration",
      "severity": "low",
      "likelihood": 0.15,
      "mitigation": "Mock testing with provider sandbox"
    }
  ],
  "safety_checks_required": [
    "security_audit",
    "test_coverage_threshold",
    "integration_test_pass"
  ],
  "rollback_capability": true,
  "impact_radius": "module",
  "confidence_in_assessment": 0.85,
  "safety_metadata": {
    "execution_time_ms": 42.1,
    "task_type": "code_generation",
    "complexity_score": 0.7,
    "agent_assessed": "agent-api-architect",
    "risk_factors_count": 2
  }
}
```

#### Error Responses

- **500 Internal Server Error**: Safety calculation failed
  ```json
  {
    "detail": "Safety score calculation failed: <error message>"
  }
  ```

---

### 4. Pattern Query API

**Endpoint**: `GET /api/autonomous/patterns/success`
**Purpose**: Retrieve successful execution patterns
**Performance Target**: <100ms

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_success_rate` | float | 0.8 | Minimum success rate filter (0.0-1.0) |
| `task_type` | string | None | Filter by task type |
| `limit` | integer | 20 | Maximum patterns to return (1-100) |

#### Response (200 OK)

```json
[
  {
    "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
    "pattern_name": "oauth2_fastapi_implementation",
    "pattern_hash": "a8f7e3d2c1b0",
    "task_type": "code_generation",
    "agent_sequence": [
      "agent-api-architect",
      "agent-testing",
      "agent-security-audit"
    ],
    "success_count": 24,
    "failure_count": 2,
    "success_rate": 0.923,
    "average_duration_ms": 285000,
    "confidence_score": 0.91,
    "prerequisites": [
      "FastAPI framework installed",
      "OAuth2 provider credentials configured"
    ],
    "constraints": [
      "Requires external OAuth2 provider access",
      "Needs environment variables for secrets"
    ],
    "best_practices": [
      "Use PKCE for enhanced security",
      "Implement token refresh mechanism",
      "Add comprehensive error handling"
    ],
    "example_tasks": [
      "Implement Google OAuth2 login",
      "Add GitHub OAuth2 authentication"
    ],
    "last_used_at": "2025-10-01T14:30:00Z",
    "created_at": "2025-09-01T10:00:00Z",
    "pattern_metadata": {
      "total_executions": 26,
      "avg_duration_minutes": 4
    }
  }
]
```

#### Error Responses

- **500 Internal Server Error**: Pattern retrieval failed
  ```json
  {
    "detail": "Pattern retrieval failed: <error message>"
  }
  ```

---

### 5. Pattern Ingestion API

**Endpoint**: `POST /api/autonomous/patterns/ingest`
**Purpose**: Ingest execution pattern for learning
**Performance Target**: <100ms

#### Request Body

```json
{
  "execution_id": "660f9500-f3ac-42e5-b827-557766550111",
  "task_characteristics": {
    "task_description": "Implement OAuth2 authentication with Google",
    "task_type": "code_generation",
    "complexity": "complex",
    "change_scope": "module",
    "estimated_files_affected": 5,
    "requires_testing": true,
    "requires_validation": true
  },
  "execution_details": {
    "agent_used": "agent-api-architect",
    "start_time": "2025-10-01T10:00:00Z",
    "end_time": "2025-10-01T10:15:30Z",
    "steps_executed": [
      "analyze_requirements",
      "design_architecture",
      "implement_oauth2_flow",
      "write_tests",
      "validate_security"
    ],
    "files_modified": [
      "src/auth/oauth2.py",
      "src/auth/providers/google.py",
      "tests/test_oauth2.py"
    ],
    "commands_executed": [
      "poetry add authlib",
      "pytest tests/test_oauth2.py"
    ],
    "tools_used": [
      "code_generator",
      "test_runner",
      "security_scanner"
    ]
  },
  "outcome": {
    "success": true,
    "duration_ms": 930000,
    "error_type": null,
    "error_message": null,
    "quality_score": 0.89,
    "test_coverage": 0.92
  },
  "learned_insights": [
    "OAuth2 PKCE flow requires additional state management",
    "Token refresh mechanism critical for user experience"
  ],
  "pattern_contribution": "Reinforces oauth2_fastapi_implementation pattern"
}
```

#### Response (200 OK)

```json
{
  "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
  "pattern_name": "code_generation_agent-api-architect",
  "is_new_pattern": false,
  "success_rate": 0.923,
  "total_executions": 25,
  "confidence_score": 0.91,
  "message": "Pattern updated successfully with execution data"
}
```

#### Error Responses

- **500 Internal Server Error**: Pattern ingestion failed
  ```json
  {
    "detail": "Pattern ingestion failed: <error message>"
  }
  ```

---

## Common Data Models

### TaskCharacteristics

```typescript
{
  task_description: string;        // Min length: 10
  task_type: TaskType;            // Enum
  complexity: TaskComplexity;     // Enum
  change_scope: ChangeScope;      // Enum
  estimated_files_affected?: number; // >= 0
  requires_testing: boolean;      // Default: true
  requires_validation: boolean;   // Default: true
  project_id?: string;           // UUID
  context?: Record<string, any>;
  historical_similar_tasks?: string[]; // UUIDs
}
```

### Enums

#### TaskType
- `code_generation`
- `code_modification`
- `bug_fix`
- `refactoring`
- `testing`
- `documentation`
- `debugging`
- `architecture`
- `performance`
- `security`

#### TaskComplexity
- `trivial`
- `simple`
- `moderate`
- `complex`
- `critical`

#### ChangeScope
- `single_file`
- `multiple_files`
- `module`
- `service`
- `system_wide`

#### ConfidenceLevel
- `very_low` (<0.3)
- `low` (0.3-0.5)
- `medium` (0.5-0.7)
- `high` (0.7-0.9)
- `very_high` (>0.9)

#### SafetyRating
- `safe` (>0.8) - Can execute autonomously
- `caution` (0.6-0.8) - Requires review
- `unsafe` (<0.6) - Human intervention required

---

## Performance Specifications

### Response Time Targets

| Endpoint | Target | P95 Acceptable |
|----------|--------|----------------|
| `/predict/agent` | <100ms | <150ms |
| `/predict/time` | <100ms | <150ms |
| `/calculate/safety` | <100ms | <150ms |
| `/patterns/success` | <100ms | <150ms |
| `/patterns/ingest` | <100ms | <150ms |

### Throughput Requirements

- **Minimum**: 100 requests/second per endpoint
- **Target**: 500 requests/second per endpoint
- **Peak**: 1000 requests/second burst capacity

### Availability

- **Target**: 99.9% uptime
- **Max Downtime**: 8.76 hours/year
- **Recovery Time**: <5 minutes

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| 200 | OK | Successful request |
| 400 | Bad Request | Invalid parameters or request body |
| 404 | Not Found | Agent or pattern not found |
| 422 | Validation Error | Pydantic validation failed |
| 500 | Internal Server Error | Unexpected server error |
| 503 | Service Unavailable | Service temporarily unavailable |

### Error Response Format

```json
{
  "detail": "Descriptive error message"
}
```

For validation errors (422):
```json
{
  "detail": [
    {
      "loc": ["body", "task_description"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Rate Limiting

**Current**: No rate limiting
**Future**: 1000 requests/minute per service

---

## Versioning

**Current Version**: v1.0.0
**API Versioning**: URL path-based (`/api/autonomous/v1/...`)
**Deprecation Policy**: 6 months notice before breaking changes

---

## Health & Monitoring

### Health Check Endpoint

**Endpoint**: `GET /api/autonomous/health`

#### Response (200 OK)

```json
{
  "status": "healthy",
  "service": "autonomous-execution-api",
  "version": "1.0.0",
  "mode": "mock_data",
  "endpoints": [
    "/predict/agent",
    "/predict/time",
    "/calculate/safety",
    "/patterns/success",
    "/patterns/ingest"
  ],
  "performance_target_ms": 100,
  "timestamp": "2025-10-02T10:00:00Z"
}
```

### Statistics Endpoint

**Endpoint**: `GET /api/autonomous/stats`

#### Response (200 OK)

```json
{
  "total_patterns": 3,
  "total_agents": 6,
  "average_pattern_success_rate": 0.901,
  "most_successful_pattern": "bug_fix_authentication",
  "most_used_agent": "agent-api-architect",
  "total_executions_tracked": 59,
  "timestamp": "2025-10-02T10:00:00Z"
}
```

---

## Change Log

### Version 1.0.0 (2025-10-02)
- Initial release with 5 core endpoints
- Mock data implementation for Track 4 preparation
- Performance targets established (<100ms)
- Complete Pydantic models and OpenAPI documentation
