# Intelligence Service - Quality Gates Configuration

This directory contains comprehensive quality gates configuration for the Archon Intelligence Service.

## 📁 Directory Structure

```
config/
├── README.md                              # This file
├── quality_gates.yaml                     # Main configuration file
├── quality_gates.schema.json              # JSON Schema for validation
├── QUALITY_GATES_DOCUMENTATION.md         # Comprehensive documentation
├── QUALITY_GATES_CHANGELOG.md             # Version history and changes
├── environments/                          # Environment-specific configs
│   ├── development.yaml                   # Development environment
│   ├── staging.yaml                       # Staging environment
│   └── production.yaml                    # Production environment
└── validators/                            # Configuration validators (planned)
```

## 🚀 Quick Start

### 1. Choose Your Environment

```bash
# Development (relaxed thresholds)
export QUALITY_GATES_ENV=development

# Staging (production-like)
export QUALITY_GATES_ENV=staging

# Production (strictest)
export QUALITY_GATES_ENV=production
```

### 2. Validate Configuration

```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('quality_gates.yaml'))"

# Validate against schema (requires jsonschema)
python -c "
import yaml, json
from jsonschema import validate
config = yaml.safe_load(open('quality_gates.yaml'))
schema = json.load(open('quality_gates.schema.json'))
validate(config, schema)
print('✅ Configuration valid')
"
```

### 3. Use in Code

```python
from intelligence.quality_gates import load_config

# Load environment-specific config
config = load_config(environment="production")

# Access gate settings
onex_threshold = config.quality_gates.onex_compliance.threshold
print(f"ONEX Compliance Threshold: {onex_threshold}")
```

## 📊 Quality Gates Overview

| Gate | Priority | Blocking | Threshold | Purpose |
|------|----------|----------|-----------|---------|
| ONEX Compliance | 1 | Yes* | 95% | Architectural consistency |
| Test Coverage | 2 | Yes* | 90% | Prevent regressions |
| Code Quality | 3 | Yes* | 70% | Maintainability |
| Performance | 4 | Yes** | Varies | System responsiveness |
| Security | 5 | Yes | Medium+ | Vulnerability prevention |
| Multi-Model Consensus | 6 | Yes* | 67% | Quality decisions |

*Blocking in staging/production only
**Blocking in production only

## 🔧 Configuration Files

### Main Configuration

**`quality_gates.yaml`** - Primary configuration with default settings

- All 6 quality gates configured
- Global settings and defaults
- Exemption rules and approval workflows
- Notification and reporting configuration

### JSON Schema

**`quality_gates.schema.json`** - Validation schema

- Ensures configuration correctness
- Validates data types and ranges
- Enforces required fields
- Provides configuration structure

### Environment Configurations

Located in `environments/` directory:

#### Development (`development.yaml`)
- **Purpose**: Rapid iteration and learning
- **Thresholds**: Relaxed (50-75% of production)
- **Blocking**: Mostly warnings only
- **AI Consensus**: Disabled for speed
- **Use Case**: Local development, prototyping

#### Staging (`staging.yaml`)
- **Purpose**: Production-like validation
- **Thresholds**: Near-production (85-90% of production)
- **Blocking**: Most gates blocking
- **AI Consensus**: Enabled with lower thresholds
- **Use Case**: Final testing, integration validation

#### Production (`production.yaml`)
- **Purpose**: Zero tolerance for critical issues
- **Thresholds**: Strictest (100%)
- **Blocking**: All gates blocking
- **AI Consensus**: Required for critical changes
- **Use Case**: Production deployments only

### Threshold Comparison

| Gate | Development | Staging | Production |
|------|-------------|---------|------------|
| ONEX Compliance | 75% | 90% | 95% |
| Test Coverage | 70% | 85% | 90% |
| Code Quality | 50% | 65% | 70% |
| Performance | Relaxed | Near-prod | Strict |
| Security | High+ only | Medium+ | Medium+ |
| AI Consensus | Disabled | 67% | 67-80% |

## 📖 Documentation

### Comprehensive Docs

**`QUALITY_GATES_DOCUMENTATION.md`** - Complete guide covering:

1. **Overview**: System architecture and features
2. **Gate Descriptions**: Detailed explanation of each gate
3. **Threshold Explanations**: Why these numbers were chosen
4. **Environment Configurations**: When to use each environment
5. **Exemption Process**: How to request and approve exemptions
6. **Integration Guide**: CI/CD, pre-commit hooks, IDE integration
7. **Troubleshooting**: Common issues and solutions

### Changelog

**`QUALITY_GATES_CHANGELOG.md`** - Version history

- All configuration changes tracked
- Version numbering scheme
- Migration guides for breaking changes
- Future roadmap

## 🔐 Security Considerations

### Secrets Management

Configuration files should **NOT** contain secrets. Use environment variables:

```yaml
# ❌ BAD
slack:
  webhook_url: "https://hooks.slack.com/services/T00/B00/XXX"

# ✅ GOOD
slack:
  webhook_url: "${SLACK_WEBHOOK_URL}"
```

### Access Control

- **Development**: All developers can modify
- **Staging**: Requires code review
- **Production**: Requires approval from Tech Lead + Principal Engineer

### Audit Trail

All configuration changes tracked via:
- Git commit history
- Exemption database records
- Notification logs

## 🔄 Updating Configuration

### Process

1. **Make Changes**: Edit appropriate YAML file
2. **Validate**: Run validation script
3. **Test**: Test in development environment
4. **Review**: Submit PR for team review
5. **Deploy**: Merge and deploy to target environment

### Validation Before Commit

```bash
# Add pre-commit hook
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
cd services/intelligence/config
python validate_config.py
if [ $? -ne 0 ]; then
    echo "❌ Configuration validation failed"
    exit 1
fi
echo "✅ Configuration valid"
EOF

chmod +x .git/hooks/pre-commit
```

## 🎯 Common Use Cases

### Case 1: Adjust Threshold

**Scenario**: Test coverage threshold is too strict

```yaml
# In environments/staging.yaml
test_coverage:
  threshold: 0.80  # Reduce from 0.85 to 0.80
```

**Process**:
1. Document reason in PR description
2. Get approval from Tech Lead
3. Monitor impact for 1 week
4. Revert if quality degrades

### Case 2: Add New Gate

**Scenario**: Add documentation coverage gate

```yaml
# In quality_gates.yaml
documentation_coverage:
  enabled: true
  priority: 7
  blocking: false  # Start as warning
  threshold: 0.80
  description: "Ensures API documentation coverage"
```

**Process**:
1. Add to schema first
2. Implement gate logic
3. Start with warnings only
4. Transition to blocking after stabilization

### Case 3: Request Exemption

**Scenario**: Legacy code fails ONEX compliance

```bash
# Create exemption request
cat > exemption_request.yaml << EOF
gate: "onex_compliance"
file: "src/legacy/old_processor.py"
reason: "legacy_migration"
justification: "Migrating to ONEX in Sprint 23"
timeline:
  start: "2025-10-02"
  end: "2025-10-16"
ticket: "ARCH-1234"
EOF

# Submit for approval
python -m intelligence.quality_gates.exemption submit exemption_request.yaml
```

## 🛠️ Maintenance

### Regular Reviews

- **Weekly**: Review active exemptions
- **Monthly**: Review gate effectiveness metrics
- **Quarterly**: Adjust thresholds based on trends
- **Annually**: Major configuration overhaul

### Metrics to Monitor

1. **Pass Rate**: Should be >90% for all gates
2. **Exemption Rate**: Should be <5% of total checks
3. **Execution Time**: Should be <300s for all gates
4. **False Positive Rate**: Should be <10%

### Health Indicators

```yaml
Healthy Configuration:
  - Pass rate: >90%
  - Exemption rate: <5%
  - Average execution time: <180s
  - Team satisfaction: >4/5

Needs Attention:
  - Pass rate: 70-90%
  - Exemption rate: 5-10%
  - Average execution time: 180-300s
  - Team satisfaction: 3-4/5

Critical Issues:
  - Pass rate: <70%
  - Exemption rate: >10%
  - Average execution time: >300s
  - Team satisfaction: <3/5
```

## 📚 Additional Resources

### Internal Documentation
- [ONEX Architecture Patterns](../../../docs/onex/archive/ONEX_ARCHITECTURE_PATTERNS_COMPLETE.md)
- [Intelligence Service Contracts](../../../docs/api/contracts/INTELLIGENCE_SERVICE_CONTRACTS.md)
- [Integration Tests Guide](../tests/integration/README.md)

### External Resources
- [Google Engineering Practices](https://google.github.io/eng-practices/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [SonarQube Quality Gates](https://docs.sonarqube.org/latest/user-guide/quality-gates/)

### Tools
- [PyYAML](https://pyyaml.org/) - YAML parsing
- [jsonschema](https://python-jsonschema.readthedocs.io/) - Schema validation
- [bandit](https://bandit.readthedocs.io/) - Security scanning
- [pytest-cov](https://pytest-cov.readthedocs.io/) - Coverage reporting

## 🤝 Contributing

### Proposing Changes

1. Open GitHub issue describing the change
2. Include justification and impact analysis
3. Gather feedback from team
4. Submit PR with configuration changes
5. Update documentation and changelog

### Change Review Checklist

- [ ] Configuration validates against schema
- [ ] Thresholds are reasonable and justified
- [ ] Documentation updated
- [ ] Changelog updated
- [ ] Tested in development environment
- [ ] Team review completed
- [ ] Approval from Tech Lead (for production)

## 📞 Support

### Getting Help

- **Documentation**: Start with `QUALITY_GATES_DOCUMENTATION.md`
- **Slack**: #quality-gates channel
- **Email**: quality@archon.dev
- **GitHub Issues**: [intelligence/issues](https://github.com/archon/intelligence/issues)

### Reporting Issues

When reporting configuration issues, include:

1. Environment (dev/staging/prod)
2. Configuration file version
3. Error message or unexpected behavior
4. Steps to reproduce
5. Expected vs actual behavior

---

**Configuration Version**: 1.0.0
**Last Updated**: 2025-10-02
**Maintainer**: Archon Quality Team
**Next Review**: 2025-11-02
