# Archon Guides

Comprehensive guides for developers, operators, and users of the Archon intelligence platform.

---

## 🧪 Development & Debugging

### [Test-Driven Debugging](./TEST_DRIVEN_DEBUGGING.md) ⭐ NEW
**Case study**: How test-driven debugging identified the orphan prevention bug in 1-2 hours vs 4-6 hours of speculation.
- When to use test-driven debugging
- 5-step process for debugging with tests
- Real examples from production bug fixes
- Before/after comparisons
- Success metrics and patterns

### [Handler Development Guide](./HANDLER_DEVELOPMENT_GUIDE.md)
Comprehensive guide for developing event handlers in the Archon system.
- Handler architecture and patterns
- Event processing best practices
- Error handling and retries
- Testing strategies
- Integration with Kafka/Redpanda

### [Developer Guide](./DEVELOPER_GUIDE.md)
Core development standards and practices.
- Code style and conventions
- Project structure
- Testing requirements
- CI/CD workflows

---

## 🏗️ Architecture & Integration

### [Intelligence-Enriched Stamping](./INTELLIGENCE_ENRICHED_STAMPING.md)
OmniNode metadata stamping integration with Archon intelligence.
- BLAKE3 hash-based file identification
- ONEX metadata generation
- Event-driven stamping workflow
- Integration with OmniNode services

### [Pattern Integration Guide](./PATTERN_INTEGRATION_GUIDE.md)
Integrating pattern learning and analytics into applications.
- Pattern extraction and matching
- Hybrid scoring system
- Traceability and lineage tracking
- Analytics and insights

### [Multi-Repo Setup](./MULTI_REPO_SETUP.md)
Setting up Archon across multiple repositories.
- Repository structure
- Shared infrastructure configuration
- Cross-repo dependencies
- Environment synchronization

### [Kafka External Access](./KAFKA_EXTERNAL_ACCESS.md)
Configuring external access to Kafka/Redpanda event bus.
- Network topology
- Port configuration (9092 vs 29092)
- DNS resolution setup
- Connection patterns for Docker vs host

### [MCP Knowledge Base](./MCP_KNOWLEDGE_BASE.md)
Model Context Protocol (MCP) integration knowledge base.
- MCP server architecture
- Tool definitions and contracts
- Integration patterns
- Best practices

---

## 🔧 Operations & Deployment

### [Operational Runbook](./OPERATIONAL_RUNBOOK.md)
Day-to-day operational procedures and commands.
- Service health monitoring
- Database operations
- Event bus management
- Troubleshooting workflows

### [Deployment Guide](./DEPLOYMENT.md)
Production deployment procedures.
- Environment setup
- Service deployment
- Database migrations
- Rollback procedures

### [Production Rollout Procedures](./PRODUCTION_ROLLOUT_PROCEDURES.md)
Step-by-step procedures for production rollouts.
- Pre-deployment checklist
- Deployment execution
- Validation and smoke tests
- Post-deployment monitoring

### [Monitoring Integration Guide](./MONITORING_INTEGRATION_GUIDE.md)
Integrating monitoring and observability tools.
- Health check endpoints
- Metrics collection
- Alerting configuration
- Dashboard setup

### [Performance Monitoring Setup](./PERFORMANCE_MONITORING_SETUP.md)
Setting up performance monitoring and optimization.
- Baseline establishment
- Performance metrics
- Optimization opportunities
- Trend analysis

### [Pipeline Monitoring Operations](./PIPELINE_MONITORING_OPERATIONS.md)
Monitoring data pipeline operations.
- Pipeline health metrics
- Consumer lag monitoring
- Event processing rates
- Error tracking

---

## 🛠️ Specialized Guides

### [Tree Stamping Troubleshooting](./TREE_STAMPING_TROUBLESHOOTING.md)
Troubleshooting file tree and stamping issues.
- Common tree building problems
- Orphan detection and prevention
- Relationship validation
- Graph structure verification

### [Troubleshooting Guide](./TROUBLESHOOTING_GUIDE.md)
General troubleshooting procedures for Archon.
- Common issues and solutions
- Diagnostic commands
- Log analysis
- Recovery procedures

### [Parallel Build Quickstart](./PARALLEL_BUILD_QUICKSTART.md)
Quick start guide for parallel build workflows.
- Parallel agent coordination
- Task decomposition
- Dependency management
- Result aggregation

### [AI Lab Configuration](./AI_LAB_CONFIGURATION.md)
Setting up AI lab environment for experimentation.
- Model configuration
- Experiment tracking
- Resource allocation
- Best practices

### [Secure Build Guide](./SECURE_BUILD_GUIDE.md)
Security best practices for builds and deployments.
- Secrets management
- Dependency scanning
- Container security
- Supply chain security

---

## 📋 Process & Workflow

### [PR Workflow Guide](./PR_WORKFLOW_GUIDE.md)
Pull request workflow and best practices.
- PR creation checklist
- Code review process
- Merge strategies
- Post-merge validation

### [PRD Task Management](./PRD_TASK_MANAGEMENT.md)
Managing tasks and Product Requirement Documents.
- Task breakdown
- Priority management
- Progress tracking
- Delivery planning

### [Template Usage Guide](./TEMPLATE_USAGE_GUIDE.md)
Using code and documentation templates.
- Available templates
- Customization guidelines
- Best practices
- Examples

### [Query UX Design](./QUERY_UX_DESIGN.md)
Designing user experience for query interfaces.
- Query patterns
- Response formatting
- Error handling
- Performance optimization

---

## 🧪 Testing

### [RAG Integration Tests Setup](./RAG_INTEGRATION_TESTS_SETUP.md)
Setting up integration tests for RAG (Retrieval-Augmented Generation).
- Test environment setup
- Test data preparation
- Integration test patterns
- Validation strategies

### [Test Intelligence Creation](./TEST_INTELLIGENCE_CREATION.md)
Creating intelligence for test scenarios.
- Test data generation
- Mock intelligence responses
- Test fixtures
- Validation helpers

---

## 📚 Reference

### [Code Review Checklist](./code-review-checklist.md)
Checklist for code reviews.
- Code quality criteria
- Testing requirements
- Documentation standards
- Performance considerations

### [Security Guidelines](./security-guidelines.md)
Security guidelines for development.
- Secure coding practices
- Vulnerability prevention
- Dependency management
- Security testing

### [Performance Guide](./performance-guide.md)
Performance optimization guide.
- Profiling techniques
- Optimization patterns
- Caching strategies
- Resource management

---

## 📂 Additional Resources

### [Operational Subdirectory](./operational/)
Operational procedures and runbooks for specific scenarios.

---

## Quick Navigation

**New to Archon?**
1. Start with [Developer Guide](./DEVELOPER_GUIDE.md)
2. Review [Operational Runbook](./OPERATIONAL_RUNBOOK.md)
3. Check [Troubleshooting Guide](./TROUBLESHOOTING_GUIDE.md)

**Debugging Issues?**
1. [Test-Driven Debugging](./TEST_DRIVEN_DEBUGGING.md) - Systematic approach
2. [Troubleshooting Guide](./TROUBLESHOOTING_GUIDE.md) - Common issues
3. [Tree Stamping Troubleshooting](./TREE_STAMPING_TROUBLESHOOTING.md) - Tree-specific issues

**Deploying to Production?**
1. [Deployment Guide](./DEPLOYMENT.md)
2. [Production Rollout Procedures](./PRODUCTION_ROLLOUT_PROCEDURES.md)
3. [Monitoring Integration Guide](./MONITORING_INTEGRATION_GUIDE.md)

**Integrating with Archon?**
1. [Pattern Integration Guide](./PATTERN_INTEGRATION_GUIDE.md)
2. [Intelligence-Enriched Stamping](./INTELLIGENCE_ENRICHED_STAMPING.md)
3. [Handler Development Guide](./HANDLER_DEVELOPMENT_GUIDE.md)

---

**Last Updated**: 2025-11-11
