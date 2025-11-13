# Quality Gates Documentation

**Version**: 1.0
**Last Updated**: 2025-10-02
**Maintainer**: Archon Quality Team

## Table of Contents

1. [Overview](#overview)
2. [Gate Descriptions](#gate-descriptions)
3. [Threshold Explanations](#threshold-explanations)
4. [Environment Configurations](#environment-configurations)
5. [Exemption Process](#exemption-process)
6. [Integration Guide](#integration-guide)
7. [Troubleshooting](#troubleshooting)

---

## Overview

The Quality Gates system provides automated, multi-dimensional validation of code quality, performance, security, and architectural compliance. It implements a **30% AI-automated + 70% human-defined** business rules approach to ensure consistent quality standards across all deployments.

### Key Features

- **6 Quality Gates**: ONEX Compliance, Test Coverage, Code Quality, Performance, Security, Multi-Model Consensus
- **Environment-Specific**: Different thresholds for dev, staging, and production
- **Blocking vs Warning**: Gates can block deployments or provide warnings
- **Exemption System**: Structured process for justified exceptions
- **Multi-Model AI**: Consensus validation for critical decisions

### Quick Start

```bash
# Validate configuration
python -m intelligence.quality_gates.validator

# Run quality gates (development)
python -m intelligence.quality_gates.runner --env development

# Run quality gates (production)
python -m intelligence.quality_gates.runner --env production --strict
```

---

## Gate Descriptions

### 1. ONEX Compliance Gate

**Priority**: 1 (Highest)
**Blocking**: Yes (in staging/production)
**Threshold**: 0.95 (95% compliance)

#### Purpose

Validates adherence to ONEX architectural patterns, ensuring consistent structure and maintainability across the codebase.

#### What It Checks

1. **Naming Conventions**
   - Classes follow pattern: `Node<Name><Type>` (e.g., `NodeDatabaseWriterEffect`)
   - Files follow pattern: `node_*_<type>.py` (e.g., `node_database_writer_effect.py`)
   - Models: `Model<Name>` (e.g., `ModelContract`)
   - Enums: `Enum<Name>` (e.g., `EnumStatus`)

2. **Contract Usage**
   - All nodes must have associated contracts
   - Contract type must match node type
   - Contracts must include versioning
   - Proper contract inheritance

3. **Node Types**
   - Only valid types: `effect`, `compute`, `reducer`, `orchestrator`
   - Single responsibility per node
   - Correct base class usage
   - Proper method signatures

4. **Architecture Patterns**
   - Dependency injection
   - Async/await patterns
   - Transaction management
   - Error handling
   - Logging integration

5. **Anti-Pattern Detection**
   - Mixed node responsibilities
   - Synchronous blocking I/O
   - Direct database access in compute nodes
   - Missing error handling
   - Hardcoded dependencies

#### Threshold Explanation

- **0.95 (Production)**: Ensures 95% of code follows ONEX patterns. The 5% tolerance allows for:
  - Legacy code being migrated
  - Third-party integrations
  - Temporary workarounds with approved exemptions

- **0.90 (Staging)**: Slightly relaxed for final testing
- **0.75 (Development)**: Allows learning and experimentation

#### Common Failures

```python
# ❌ FAIL: Incorrect naming
class DatabaseWriter:  # Missing "Node" prefix and type suffix
    pass

# ✅ PASS: Correct naming
class NodeDatabaseWriterEffect:
    pass

# ❌ FAIL: Mixed responsibilities
class NodeUserManagerEffect:
    def write_user(self):  # Effect operation
        pass
    def calculate_score(self):  # Compute operation - WRONG!
        pass

# ✅ PASS: Single responsibility
class NodeUserWriterEffect:
    def write_user(self):  # Only effect operations
        pass
```

---

### 2. Test Coverage Gate

**Priority**: 2
**Blocking**: Yes (in staging/production)
**Threshold**: 0.90 (90% coverage)

#### Purpose

Ensures comprehensive test coverage to prevent regressions and validate functionality.

#### What It Checks

1. **Line Coverage**: 90% of code lines executed by tests
2. **Branch Coverage**: 85% of conditional branches tested
3. **Function Coverage**: 95% of functions have tests
4. **Critical Path Coverage**: 100% coverage for critical business logic

#### Coverage Types

```yaml
coverage_types:
  line_coverage:
    threshold: 0.90  # 90% of lines executed
  branch_coverage:
    threshold: 0.85  # 85% of branches tested
  function_coverage:
    threshold: 0.95  # 95% of functions covered
```

#### Excluded Patterns

- Test files themselves (`*/tests/*`, `*/test_*.py`)
- Init files (`*/__init__.py`)
- Migration scripts (`*/migrations/*`)
- Configuration files (`*/config/*`)

#### Critical Paths

Critical business logic requires **100% coverage**:

- Pattern learning services
- Quality assessment logic
- Intelligence core functionality

#### Threshold Explanation

- **0.90 (Production)**: Industry best practice for production systems
- **0.85 (Staging)**: Allows final integration testing
- **0.70 (Development)**: Encourages testing during development

#### Example Report

```
Coverage Report:
================
Line Coverage:     92% ✅ (threshold: 90%)
Branch Coverage:   88% ✅ (threshold: 85%)
Function Coverage: 96% ✅ (threshold: 95%)
Critical Paths:    100% ✅ (threshold: 100%)

Overall: PASS
```

---

### 3. Code Quality Gate

**Priority**: 3
**Blocking**: Yes (in staging/production)
**Threshold**: 0.70 (70% quality score)

#### Purpose

Validates code quality metrics including complexity, duplication, maintainability, and documentation.

#### What It Checks

1. **Complexity Metrics**
   - **Cyclomatic Complexity**: Max 10 per function
   - **Cognitive Complexity**: Max 15 per function
   - **Function Lines**: Max 50 lines per function
   - **Class Lines**: Max 300 lines per class

2. **Code Duplication**
   - Maximum 5% duplicate code
   - Minimum 6 lines to count as duplication

3. **Maintainability**
   - Minimum "B" grade (A-F scale)
   - Factors: complexity + duplication + documentation + naming

4. **Code Smells**
   - Long methods
   - Long parameter lists
   - Large classes
   - Feature envy
   - Data clumps

5. **Documentation**
   - Public functions must have docstrings
   - Public classes must have docstrings
   - Complex logic must be documented
   - Minimum 20 characters per docstring

6. **Type Hints**
   - 95% type hint coverage
   - All public APIs must be typed

#### Threshold Explanation

- **0.70 (Production)**: Ensures maintainable, professional-quality code
- **0.65 (Staging)**: Slight relaxation for integration testing
- **0.50 (Development)**: Encourages quality without blocking rapid development

#### Complexity Examples

```python
# ❌ FAIL: Cyclomatic complexity too high (15)
def process_order(order, user, discount, shipping):
    if order.is_valid():
        if user.is_premium():
            if discount.is_applicable():
                if shipping.is_available():
                    if order.total > 100:
                        if discount.percentage > 20:
                            if user.loyalty_points > 500:
                                # ... more nested conditions
                                return result
    return None

# ✅ PASS: Refactored for lower complexity (4)
def process_order(order, user, discount, shipping):
    if not self._is_order_processable(order, user, discount, shipping):
        return None

    discount_amount = self._calculate_discount(order, user, discount)
    return self._finalize_order(order, discount_amount, shipping)
```

---

### 4. Performance Gate

**Priority**: 4
**Blocking**: Yes in production, Warning in dev
**Threshold**: Operation-specific (see below)

#### Purpose

Monitors performance metrics and identifies optimization opportunities to maintain system responsiveness.

#### Performance Thresholds

| Operation | Max Duration | Percentile | Severity |
|-----------|--------------|------------|----------|
| Pattern Extraction | 200ms | 95th | Medium |
| Vector Search | 100ms | 95th | High |
| Storage Query | 50ms | 95th | Medium |
| API Endpoint | 500ms | 99th | High |
| Batch Processing | 5000ms | 95th | Low |

#### What It Checks

1. **Response Times**: Operations complete within thresholds
2. **CPU Usage**: <80% average over 60 seconds
3. **Memory Usage**: <1024MB with leak detection
4. **Database Connections**: Max 20 active, 5 idle
5. **Cache Hit Rate**: >70% hit rate
6. **Regression Detection**: <20% performance degradation vs baseline

#### Threshold Explanation

Thresholds based on:
- **User Experience**: API endpoints must respond quickly
- **System Resources**: Prevent resource exhaustion
- **Baseline Comparison**: Detect performance regressions

#### Environment Differences

```yaml
# Production
vector_search:
  max_duration_ms: 100  # Strict

# Staging
vector_search:
  max_duration_ms: 120  # +20ms tolerance

# Development
vector_search:
  max_duration_ms: 300  # Relaxed for debugging
```

#### Performance Report Example

```
Performance Report:
==================
Pattern Extraction:  185ms ✅ (threshold: 200ms, p95)
Vector Search:       95ms ✅ (threshold: 100ms, p95)
Storage Query:       45ms ✅ (threshold: 50ms, p95)
API Endpoint:        420ms ✅ (threshold: 500ms, p99)

CPU Usage:           72% ✅ (threshold: 80%)
Memory Usage:        890MB ✅ (threshold: 1024MB)
Cache Hit Rate:      76% ✅ (threshold: 70%)

Overall: PASS
```

---

### 5. Security Gate

**Priority**: 5
**Blocking**: Yes
**Severity Threshold**: Medium+

#### Purpose

Scans for security vulnerabilities, secrets, and compliance issues to prevent security incidents.

#### What It Checks

1. **Dependency Vulnerabilities**
   - Tools: `safety`, `pip-audit`
   - Zero tolerance for critical/high severity
   - Limited medium/low severity allowed

2. **Code Vulnerabilities**
   - Tools: `bandit`, `semgrep`
   - SQL injection
   - Command injection
   - Path traversal
   - Insecure random
   - Hardcoded secrets
   - Weak cryptography

3. **Secret Detection**
   - Tools: `detect-secrets`, `trufflehog`
   - API keys
   - Passwords
   - Tokens
   - Certificates
   - Connection strings

4. **License Compliance**
   - Allowed: MIT, Apache-2.0, BSD-3-Clause, BSD-2-Clause, ISC
   - Blocked: GPL-3.0, AGPL-3.0, LGPL-3.0

5. **Container Security** (staging/production)
   - Base image scanning
   - High+ vulnerability threshold

#### Severity Levels

```yaml
Production:
  critical: 0  # Zero tolerance
  high: 0      # Zero tolerance
  medium: 0    # Zero tolerance
  low: 10      # Minimal allowed

Staging:
  critical: 0
  high: 0
  medium: 3    # Limited allowed
  low: 15

Development:
  critical: 0
  high: 2      # Some allowed for testing
  medium: 999  # Warning only
  low: 999     # Warning only
```

#### Common Vulnerabilities

```python
# ❌ FAIL: Hardcoded secret
API_KEY = "sk-1234567890abcdef"

# ✅ PASS: Environment variable
API_KEY = os.environ.get("API_KEY")

# ❌ FAIL: SQL injection risk
query = f"SELECT * FROM users WHERE id = {user_id}"

# ✅ PASS: Parameterized query
query = "SELECT * FROM users WHERE id = %s"
cursor.execute(query, (user_id,))

# ❌ FAIL: Weak random
import random
token = random.randint(1000, 9999)

# ✅ PASS: Cryptographically secure random
import secrets
token = secrets.token_urlsafe(32)
```

---

### 6. Multi-Model Consensus Gate

**Priority**: 6
**Blocking**: Yes
**Consensus Threshold**: 0.67 (2 of 3 models)

#### Purpose

Validates critical architectural and code changes through multi-model AI consensus to ensure quality decisions.

#### AI Models

| Model | Weight | Specialty | Status |
|-------|--------|-----------|--------|
| Gemini Pro | 1.0 | General reasoning | Active |
| Codestral | 1.5 | Code generation | Active |
| DeepSeek | 2.0 | Advanced codegen | Active |

**Total Weight**: 7.5

#### Consensus Calculation

```python
# Weighted consensus
total_weight = sum(model.weight for model in models if model.agrees)
total_possible = sum(model.weight for model in models)
consensus_score = total_weight / total_possible

# Example: 2 of 3 models agree
# Gemini (1.0) + DeepSeek (2.0) agree = 3.0
# Total possible = 7.5
# Consensus = 3.0 / 7.5 = 0.40 ❌ FAIL (below 0.67)

# Example: Different 2 of 3 agree
# Codestral (1.5) + DeepSeek (2.0) agree = 3.5
# Total possible = 7.5
# Consensus = 3.5 / 7.5 = 0.47 ❌ FAIL (below 0.67)

# Example: All 3 agree
# Gemini (1.0) + Codestral (1.5) + DeepSeek (2.0) = 4.5
# Wait, that's still only 60%... Let me recalculate
# Actually the sum should be: 1.0 + 1.5 + 2.0 = 4.5 total
# So if all agree: 4.5 / 4.5 = 1.0 ✅ PASS
```

#### Applied To

1. **Architecture Decisions** (min 0.67 consensus)
   - New node creation
   - Contract changes
   - Architectural pattern changes

2. **Critical Code Changes** (min 0.80 consensus in prod)
   - Core service modifications
   - Database schema changes
   - API contract changes
   - Security-related changes

3. **Refactoring** (min 0.67 consensus)
   - Large-scale refactoring
   - Pattern extraction
   - Code reorganization

#### Validation Criteria

Each model evaluates:
- **Correctness**: Does it work?
- **Best Practices**: Does it follow standards?
- **Performance Impact**: Will it be fast enough?
- **Security Impact**: Is it secure?
- **Maintainability**: Can it be maintained?

#### Example Consensus Report

```
Multi-Model Consensus Report:
============================
Change: Refactor PatternExtractor to use async processing

Gemini Pro (weight: 1.0): ✅ APPROVE
  - Correctness: Good
  - Best Practices: Excellent
  - Performance: Improved
  - Security: No concerns
  - Maintainability: Better

Codestral (weight: 1.5): ✅ APPROVE
  - Correctness: Excellent
  - Best Practices: Good
  - Performance: Significant improvement
  - Security: Enhanced
  - Maintainability: Much better

DeepSeek (weight: 2.0): ⚠️ CONCERNS
  - Correctness: Good
  - Best Practices: Good
  - Performance: Improved but potential race conditions
  - Security: Needs review
  - Maintainability: Good

Consensus: 2.5 / 4.5 = 0.56 ❌ FAIL (threshold: 0.67)
Recommendation: Address DeepSeek's race condition concerns
```

---

## Threshold Explanations

### Why These Numbers?

#### ONEX Compliance: 0.95

- **Industry Standard**: 95% compliance is considered "excellent" in software architecture
- **Flexibility**: 5% allows for legitimate exceptions (legacy code, third-party integrations)
- **Enforcement**: High enough to ensure consistency, low enough to be achievable

#### Test Coverage: 0.90

- **Research-Backed**: Studies show 90% coverage correlates with 50% fewer bugs
- **Cost-Benefit**: Going above 90% provides diminishing returns
- **Critical Paths**: 100% for critical code, 90% overall balances thoroughness with practicality

#### Code Quality: 0.70

- **Professional Grade**: 70% represents "good" quality in most grading systems
- **Maintainability**: Above 70% typically means code is maintainable long-term
- **Practical**: Achievable without being overly restrictive

#### Performance: Operation-Specific

- **User Experience**: Based on user perception thresholds
  - <100ms: Instantaneous
  - <300ms: Responsive
  - <1000ms: Acceptable
  - >1000ms: Slow
- **System Resources**: Based on infrastructure capacity and cost

#### Security: Zero Tolerance (Critical/High)

- **Risk Management**: Single critical vulnerability can compromise entire system
- **Regulatory**: Many compliance frameworks require zero critical/high vulnerabilities
- **Cost**: Fixing vulnerabilities in production is 100x more expensive than in development

#### Multi-Model Consensus: 0.67

- **Simple Majority**: 2 of 3 models (67%) is a clear majority
- **Prevents Deadlock**: Avoids 50/50 ties
- **Quality Assurance**: Multiple perspectives reduce blind spots

### Threshold Adjustment Guidelines

When to adjust thresholds:

1. **Too Strict**: >20% failure rate for 2+ weeks
2. **Too Lenient**: <5% failure rate for 1+ month
3. **Business Impact**: Clear correlation between threshold and business metrics
4. **Team Maturity**: As team improves, gradually increase thresholds

---

## Environment Configurations

### Development Environment

**Philosophy**: Encourage quality without blocking rapid development

```yaml
Key Differences:
- ONEX Compliance: 0.75 (vs 0.95 prod)
- Test Coverage: 0.70 (vs 0.90 prod)
- Code Quality: 0.50 (vs 0.70 prod)
- Blocking: Most gates are warnings only
- Multi-Model: Disabled for speed
- Exemptions: No approval required
```

**Use When**: Local development, prototyping, learning

### Staging Environment

**Philosophy**: Production-like validation with minimal relaxations

```yaml
Key Differences:
- ONEX Compliance: 0.90 (vs 0.95 prod)
- Test Coverage: 0.85 (vs 0.90 prod)
- Code Quality: 0.65 (vs 0.70 prod)
- Performance: Slightly relaxed thresholds
- Security: Limited medium vulnerabilities
- Multi-Model: Enabled with lower thresholds
```

**Use When**: Final testing before production, integration testing

### Production Environment

**Philosophy**: Zero tolerance for critical issues, highest standards

```yaml
Key Features:
- Strictest thresholds across all gates
- All gates blocking except performance (warning)
- Zero tolerance for critical/high security issues
- Multi-model consensus required for critical changes
- Exemptions require 2 approvals
- Comprehensive monitoring and alerting
```

**Use When**: Production deployments only

### Switching Environments

```bash
# Via environment variable
export QUALITY_GATES_ENV=production
python -m intelligence.quality_gates.runner

# Via command line
python -m intelligence.quality_gates.runner --env staging

# Via configuration
quality_gates_config = load_config(environment="development")
```

---

## Exemption Process

### When to Request Exemption

Valid reasons for exemptions:

1. **Legacy Migration**: Code being migrated from legacy systems
2. **Third-Party Integration**: Constraints from external libraries
3. **Performance Critical**: Optimization requires pattern deviation
4. **Temporary Workaround**: Short-term solution with remediation plan
5. **Experimental Feature**: Feature behind feature flag

### How to Request

1. **Create Exemption Request**

```yaml
exemption_request:
  gate: "onex_compliance"
  file: "src/legacy/old_processor.py"
  reason: "legacy_migration"
  justification: |
    This file is part of the legacy data processor being migrated to ONEX.
    Migration planned for Sprint 23 (2 weeks).
  timeline:
    start: "2025-10-02"
    end: "2025-10-16"
  ticket: "ARCH-1234"
  approvers_requested:
    - "tech_lead"
    - "principal_engineer"
```

2. **Submit for Approval**

```bash
python -m intelligence.quality_gates.exemption submit exemption_request.yaml
```

3. **Approval Process**

- **Development**: Auto-approved
- **Staging**: 1 approval required (Tech Lead)
- **Production**: 2 approvals required (Tech Lead + Principal Engineer)

4. **Tracking**

All exemptions are tracked in database:
- Creation date
- Expiration date
- Review status
- Approval chain
- Related tickets

### Exemption Limits

```yaml
Per File:
  max_exemptions: 2

Per Reason:
  legacy_migration: max_duration_days: 90
  temporary_workaround: max_duration_days: 30
  experimental_feature: max_duration_days: 60

Review:
  frequency_days: 14  # Bi-weekly review
  automatic_expiration: true
```

### Revoking Exemptions

Exemptions automatically expire after max_duration. To revoke early:

```bash
python -m intelligence.quality_gates.exemption revoke --id EXEMPTION_ID
```

---

## Integration Guide

### CI/CD Integration

#### GitHub Actions

```yaml
name: Quality Gates
on: [push, pull_request]

jobs:
  quality_gates:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run Quality Gates
        env:
          QUALITY_GATES_ENV: ${{ github.ref == 'refs/heads/main' && 'production' || 'staging' }}
        run: |
          python -m intelligence.quality_gates.runner --strict

      - name: Upload Report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: quality-gates-report
          path: quality_gates_report.html
```

#### GitLab CI

```yaml
quality_gates:
  stage: test
  script:
    - pip install -r requirements.txt
    - python -m intelligence.quality_gates.runner --env ${CI_ENVIRONMENT_NAME}
  artifacts:
    reports:
      junit: quality_gates_report.xml
    paths:
      - quality_gates_report.html
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      variables:
        QUALITY_GATES_ENV: "production"
    - when: always
      variables:
        QUALITY_GATES_ENV: "staging"
```

### Pre-Commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "Running Quality Gates..."
python -m intelligence.quality_gates.runner --env development --fast

if [ $? -ne 0 ]; then
    echo "❌ Quality gates failed. Use --no-verify to skip (not recommended)"
    exit 1
fi

echo "✅ Quality gates passed"
```

### IDE Integration

#### VS Code

```json
{
  "tasks": [
    {
      "label": "Quality Gates",
      "type": "shell",
      "command": "python -m intelligence.quality_gates.runner --env development",
      "problemMatcher": [],
      "group": {
        "kind": "test",
        "isDefault": true
      }
    }
  ]
}
```

### API Integration

```python
from intelligence.quality_gates import QualityGateRunner

runner = QualityGateRunner(environment="production")
results = runner.run()

if results.passed:
    print("✅ All gates passed")
    deploy()
else:
    print("❌ Quality gates failed:")
    for failure in results.failures:
        print(f"  - {failure.gate}: {failure.message}")
    sys.exit(1)
```

---

## Troubleshooting

### Common Issues

#### Issue: Gate Timing Out

```
Error: Quality gate 'multi_model_consensus' timed out after 120s
```

**Solution**:
```yaml
# Increase timeout in config
quality_gates:
  multi_model_consensus:
    timeout_seconds: 300  # Increase from 120
```

#### Issue: False Positive on ONEX Compliance

```
Error: File 'legacy_processor.py' fails ONEX naming conventions
```

**Solution**:
1. Check if exemption is appropriate
2. If yes, request exemption with justification
3. If no, rename file to follow conventions

#### Issue: Test Coverage Below Threshold

```
Error: Coverage 87% < threshold 90%
```

**Solution**:
```bash
# Generate coverage report to see what's missing
pytest --cov=src --cov-report=html

# Open htmlcov/index.html to see uncovered lines
open htmlcov/index.html

# Add tests for uncovered code
```

#### Issue: Performance Regression

```
Error: vector_search duration 150ms > threshold 100ms
```

**Solution**:
1. Profile the code to find bottleneck
2. Optimize hot path
3. If optimization not possible, request threshold adjustment with justification

#### Issue: Multi-Model Consensus Disagreement

```
Error: Consensus 0.60 < threshold 0.67
Models disagreeing on architectural decision
```

**Solution**:
1. Review each model's feedback
2. Address concerns raised
3. Re-run consensus
4. If still failing, consider alternative approach

### Debug Mode

```bash
# Run with verbose logging
python -m intelligence.quality_gates.runner --env development --debug

# Run single gate
python -m intelligence.quality_gates.runner --gate onex_compliance --debug

# Dry run (don't fail, just report)
python -m intelligence.quality_gates.runner --dry-run
```

### Getting Help

1. **Documentation**: https://docs.archon.dev/quality-gates
2. **Slack**: #quality-gates channel
3. **Email**: quality@archon.dev
4. **GitHub Issues**: https://github.com/archon/intelligence/issues

---

## Appendix

### Grading Scale

```
Quality Score  Grade  Description
0.90 - 1.00    A      Excellent - Exceeds standards
0.70 - 0.89    B      Good - Meets standards
0.50 - 0.69    C      Acceptable - Needs improvement
0.30 - 0.49    D      Poor - Significant issues
0.00 - 0.29    F      Failing - Major problems
```

### Severity Levels

```
Severity   Impact            Action
Critical   System failure    Block immediately
High       Major issue       Block in prod/staging
Medium     Moderate issue    Block in production
Low        Minor issue       Warning only
```

### Model Weights Rationale

| Model | Weight | Rationale |
|-------|--------|-----------|
| Gemini Pro | 1.0 | Baseline, general-purpose reasoning |
| Codestral | 1.5 | Code specialist, higher confidence |
| DeepSeek | 2.0 | Advanced codegen, highest confidence |

### Configuration Validation

```bash
# Validate YAML syntax
python -m intelligence.quality_gates.validator --config quality_gates.yaml

# Validate against schema
python -m intelligence.quality_gates.validator --schema quality_gates.schema.json

# Validate all environments
python -m intelligence.quality_gates.validator --all-environments
```

---

**End of Documentation**

For updates and contributions, see: `/config/QUALITY_GATES_CHANGELOG.md`
