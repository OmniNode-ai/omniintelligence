# Code Review Checklist

**Status**: 🚧 **Placeholder Document**
**Last Updated**: 2025-10-20

> **Note**: This document is a placeholder. A comprehensive code review checklist will be developed to support the PR workflow process.

## Planned Content

This checklist will include:

### General Review Items
- [ ] Code follows project style guidelines (ruff, black)
- [ ] All functions have type annotations
- [ ] No use of `Any` types
- [ ] Documentation is clear and complete
- [ ] Tests cover new functionality
- [ ] No commented-out code
- [ ] Error handling is appropriate

### ONEX Compliance
- [ ] Follows ONEX architectural patterns
- [ ] Uses proper node types (Effect, Compute, Reducer, Orchestrator)
- [ ] Implements ModelContract interfaces correctly
- [ ] Uses OnexError for exceptions
- [ ] Follows naming conventions

### Security Review
- [ ] No hardcoded secrets or credentials
- [ ] Input validation is implemented
- [ ] SQL injection protection in place
- [ ] Authentication/authorization checked
- [ ] Sensitive data properly handled

### Performance Review
- [ ] No obvious performance bottlenecks
- [ ] Database queries are optimized
- [ ] Caching strategy is appropriate
- [ ] Resource cleanup is handled

### Testing Review
- [ ] Unit tests are present and meaningful
- [ ] Integration tests cover critical paths
- [ ] Edge cases are tested
- [ ] Test coverage meets threshold (80%+)

## Related Documentation

- [PR Workflow Guide](./PR_WORKFLOW_GUIDE.md)
- [ONEX Standards Guide](../../agents/COMMON_ONEX_STANDARDS.md)
- [Security Best Practices](../security/SECURITY.md)

---

**TODO**: Develop comprehensive code review checklist based on project needs and best practices.
