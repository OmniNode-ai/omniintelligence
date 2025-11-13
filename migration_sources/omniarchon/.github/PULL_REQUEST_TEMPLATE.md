# Pull Request Template

## 📋 PR Information

**Type of Change** (check all that apply):
- [ ] 🚀 Feature (new functionality)
- [ ] 🐛 Bug fix (non-breaking change that fixes an issue)
- [ ] 🔧 Refactor (code change that neither fixes a bug nor adds a feature)
- [ ] 📚 Documentation (changes to documentation only)
- [ ] 🎨 Style (formatting, missing semi-colons, etc; no code change)
- [ ] ⚡ Performance (improves performance)
- [ ] 🧪 Test (adds missing tests or corrects existing tests)
- [ ] 🔒 Security (addresses security vulnerabilities)
- [ ] ⬆️ Dependencies (updates dependencies)
- [ ] 🏗️ Build/CI (changes to build process or CI/CD)

**Change Scope**:
- [ ] Small (< 5 files, minimal impact)
- [ ] Medium (5-20 files, moderate impact)  
- [ ] Large (20+ files, significant impact)
- [ ] Critical (affects core services or architecture)

## 🎯 Description

### Problem/Motivation
<!-- Describe the problem this PR solves or the motivation for the changes -->

### Solution Approach
<!-- Describe your solution and why you chose this approach -->

### Key Changes
<!-- List the main changes in this PR -->
-
-
-

## 🏗️ ONEX Compliance Checklist

### ✅ **Mandatory Requirements** (All must be checked)

#### Type Safety & Standards
- [ ] **Zero `Any` types used** - All types are strongly typed (zero tolerance policy)
- [ ] **Pydantic models properly implemented** - All data models use Pydantic BaseModel
- [ ] **Contract-driven architecture followed** - Interfaces and contracts are defined
- [ ] **Registry pattern implemented correctly** - Service registration follows ONEX patterns
- [ ] **Error handling with OnexError** - Custom errors use proper error classes

#### Code Quality
- [ ] **mypy type checking passes** - No type checking errors
- [ ] **ruff linting passes** - Code follows style guidelines
- [ ] **black formatting applied** - Consistent code formatting
- [ ] **No TODO/FIXME comments** - All temporary comments addressed
- [ ] **Docstrings added for public APIs** - Public functions/classes documented

#### Architecture & Design
- [ ] **Single Responsibility Principle** - Each class/function has one clear purpose
- [ ] **Dependency Injection used** - Dependencies are injected, not hardcoded
- [ ] **No circular dependencies** - Import cycles avoided
- [ ] **Proper abstraction layers** - Business logic separated from infrastructure
- [ ] **Configuration externalized** - No hardcoded configuration values

## 🧪 Testing Requirements

### Test Coverage
- [ ] **Unit tests added/updated** - New code has corresponding unit tests
- [ ] **Integration tests considered** - Cross-service interactions tested
- [ ] **Edge cases tested** - Error conditions and boundary cases covered
- [ ] **Test coverage ≥ 80%** - Code coverage meets minimum requirements
- [ ] **Tests pass locally** - All tests run successfully in development environment

### Test Quality
- [ ] **Tests are deterministic** - Tests produce consistent results
- [ ] **No flaky tests** - Tests don't randomly fail
- [ ] **Test data is isolated** - Tests don't depend on external state
- [ ] **Mocks used appropriately** - External dependencies properly mocked

## 🔒 Security Checklist

- [ ] **No sensitive data in code** - API keys, passwords, etc. externalized
- [ ] **Input validation implemented** - User inputs are validated and sanitized
- [ ] **SQL injection prevention** - Parameterized queries or ORM used
- [ ] **HTTPS/secure connections** - All external calls use secure protocols
- [ ] **Authentication/authorization** - Proper access controls implemented
- [ ] **Security scan passed** - Automated security tools show no issues

## ⚡ Performance Considerations

- [ ] **Database queries optimized** - Efficient queries, proper indexing considered
- [ ] **N+1 query problems avoided** - Batch operations where appropriate
- [ ] **Memory usage considered** - Large objects cleaned up properly
- [ ] **Caching strategy reviewed** - Appropriate caching implemented
- [ ] **Performance regression tested** - No significant performance degradation

## 📊 Change Impact Analysis

### Files Changed
<!-- Auto-populated by PR workflow - do not edit manually -->
- **Frontend Changes**: _Auto-calculated_
- **Backend Changes**: _Auto-calculated_
- **Configuration Changes**: _Auto-calculated_
- **Docker Changes**: _Auto-calculated_

### Services Affected
- [ ] **Archon Server** (Port 8181)
- [ ] **MCP Service** (Port 8051)
- [ ] **Agents Service** (Port 8052)
- [ ] **Intelligence Service** (Port 8053)
- [ ] **Frontend** (Port 3737)
- [ ] **Database Schema** (Supabase)

### Breaking Changes
- [ ] **No breaking changes** - Backward compatibility maintained
- [ ] **Breaking changes documented** - Migration guide provided below

<!-- If breaking changes, provide migration guide -->
#### Migration Guide (if applicable)
<!-- Provide step-by-step migration instructions -->

## 🔗 Related Work

### Issues & Work Items
<!-- Link related issues, tickets, or work items -->
- Fixes #
- Related to #
- Blocked by #

### Dependencies  
<!-- List any PRs this depends on or that depend on this -->
- Depends on PR #
- Blocks PR #

## 🎯 Testing Instructions

### How to Test This PR
1. **Setup Steps**:
   <!-- Provide clear setup instructions -->

2. **Test Scenarios**:
   <!-- List specific test cases to verify -->

3. **Expected Results**:
   <!-- Describe what reviewers should see -->

### Manual Testing Completed
- [ ] **Happy path testing** - Core functionality works as expected
- [ ] **Error handling testing** - Edge cases and errors handled gracefully
- [ ] **Integration testing** - Works correctly with other services
- [ ] **UI/UX testing** - Frontend changes tested across browsers (if applicable)

## 📸 Screenshots/Recordings (if applicable)

<!-- Add screenshots or recordings showing the changes -->

## 📝 Reviewer Guidelines

### Review Focus Areas
<!-- Highlight specific areas that need careful review -->
- [ ] **Architecture decisions** - Review design choices and patterns
- [ ] **Performance implications** - Check for potential performance issues
- [ ] **Security considerations** - Validate security measures
- [ ] **Error handling** - Ensure proper error handling
- [ ] **Documentation** - Verify documentation is clear and complete

### Reviewer Checklist
- [ ] **Code follows ONEX standards** - Architecture patterns correctly implemented
- [ ] **Logic is sound** - Implementation approach makes sense
- [ ] **Tests adequately cover changes** - Test quality and coverage acceptable
- [ ] **Documentation updated** - Related docs updated as needed
- [ ] **Performance impact acceptable** - No significant performance regression
- [ ] **Security implications reviewed** - Security measures appropriate

## 🚀 Deployment Notes

### Pre-deployment Checklist
- [ ] **Database migrations ready** - Scripts prepared and tested
- [ ] **Configuration changes documented** - Environment variable changes noted
- [ ] **Rollback plan prepared** - Rollback procedure documented
- [ ] **Monitoring alerts reviewed** - Alerting configured for new functionality

### Post-deployment Verification
- [ ] **Health checks pass** - All services respond correctly
- [ ] **Metrics are normal** - Performance metrics within expected ranges
- [ ] **Logs are clean** - No unexpected errors in logs
- [ ] **User acceptance testing** - Key workflows tested in production

## 🎉 Additional Notes

<!-- Any additional context, decisions, or information for reviewers -->

---

## ⚠️ For Reviewers

This PR has been processed through automated quality gates including:
- ✅ ONEX compliance validation
- ✅ Security scanning  
- ✅ Performance impact analysis
- ✅ Test coverage verification

**Quality Gate Status**: _Auto-populated by PR workflow_

### Review Assignment Strategy
- **Small changes**: Any team member can review
- **Medium changes**: Requires domain expert review
- **Large changes**: Requires architecture review + domain expert
- **Critical changes**: Requires architecture review + 2 domain experts

---

**Template Version**: 1.0.0 | **Last Updated**: 2025-09-03
