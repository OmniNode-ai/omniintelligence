# Custom Quality Rules Configuration

Project-specific quality validation rules for Archon Intelligence Service.

## Overview

Custom quality rules enable per-project quality validation with:
- **Pattern-based rules**: Regex matching for code patterns
- **Metric-based rules**: Quantitative thresholds (complexity, length, coverage)
- **Architectural rules**: Structural requirements (inheritance, methods)
- **Weighted scoring**: Configurable impact on quality scores
- **Severity levels**: Critical violations, warnings, suggestions

## Configuration Files

### Project Configurations

- **`omniclaude.yaml`**: ONEX-focused validation rules
  - Node architecture compliance
  - Contract-driven patterns
  - Pydantic v2 enforcement
  - ONEX best practices

- **`omniarchon.yaml`**: Service architecture rules
  - Event handler patterns
  - FastAPI conventions
  - Kafka integration
  - Async patterns

- **`template.yaml`**: Template for new projects
  - Example rules for all types
  - Configuration guidelines
  - Pattern examples
  - Best practices

## Rule Types

### 1. Architectural Rules

Validate structural patterns:

```yaml
- rule_id: "require_node_base"
  rule_type: "architectural"
  severity: "critical"
  pattern: "class.*Node.*NodeBase"
  weight: 0.2
```

### 2. Pattern Rules

Match or forbid text patterns:

```yaml
- rule_id: "forbid_any_types"
  rule_type: "pattern"
  severity: "critical"
  forbids: ":\\s*Any\\b"
  weight: 0.15
```

### 3. Metric Rules

Quantitative thresholds:

```yaml
- rule_id: "max_function_complexity"
  rule_type: "metric"
  severity: "warning"
  max_complexity: 15
  weight: 0.12
```

## Severity Levels

| Severity | Impact | Use Case |
|----------|--------|----------|
| **critical** | Blocks validation | Security issues, architecture violations |
| **warning** | Should be fixed | Code quality issues, best practice violations |
| **suggestion** | Nice to have | Minor improvements, optimizations |

## Weight Guidelines

| Weight Range | Priority | Example Rules |
|--------------|----------|---------------|
| 0.15-0.25 | Critical | Security, architecture compliance |
| 0.10-0.15 | High | Major patterns, error handling |
| 0.05-0.10 | Medium | Best practices, conventions |
| 0.03-0.05 | Low | Minor suggestions, optimizations |

**Recommendation**: Total project weights should sum to 1.0-2.0 for balanced scoring.

## Usage

### Load Rules Programmatically

```python
from services.quality import CustomQualityRulesEngine
from pathlib import Path

# Initialize engine
engine = CustomQualityRulesEngine()

# Load project rules
await engine.load_project_rules(
    project_id="omniclaude",
    rules_config_path=Path("config/quality_rules/omniclaude.yaml")
)

# Evaluate code
result = await engine.evaluate_rules(
    project_id="omniclaude",
    code=code_content,
    file_path="src/node_example.py"
)

print(f"Custom Score: {result['custom_score']:.2f}")
print(f"Violations: {len(result['violations'])}")
```

### API Integration

```bash
# Assess with custom rules
POST /assess/code
{
  "content": "...",
  "source_path": "src/node.py",
  "language": "python",
  "project_id": "omniclaude",
  "use_custom_rules": true
}
```

## Pattern Examples

### Common Patterns

```yaml
# Class inheritance
pattern: "class\\s+\\w+\\(BaseClass\\)"

# Method signature
pattern: "async\\s+def\\s+method_name\\s*\\("

# Import statement
pattern: "from\\s+module\\s+import\\s+Class"

# Type annotation
pattern: ":\\s*Type\\["

# Forbidden pattern (use "forbids")
forbids: "\\.dict\\s*\\("  # Forbid Pydantic v1 .dict()
```

### Advanced Patterns

```yaml
# Node types with inheritance
pattern: "class\\s+\\w*Node\\w*.*(?:NodeBase|NodeEffect|NodeCompute)"

# Async event handlers
pattern: "async\\s+def\\s+handle_event\\s*\\("

# Correlation ID usage
pattern: "(?:correlation_id|envelope\\.correlation_id)"

# SQL injection prevention
forbids: "f['\"]SELECT.*\\{|%s.*SELECT"
```

## Creating New Project Rules

1. **Copy template**:
   ```bash
   cp config/quality_rules/template.yaml config/quality_rules/your_project.yaml
   ```

2. **Configure project**:
   ```yaml
   project_id: "your_project"
   description: "Your project description"
   ```

3. **Add rules**: Use template examples and pattern guides

4. **Test rules**:
   ```python
   # Load and test
   await engine.load_project_rules("your_project", Path("config/..."))
   result = await engine.evaluate_rules("your_project", test_code)
   ```

5. **Adjust weights**: Balance scoring based on priorities

## Rule Management

### Disable Rule

```python
await engine.disable_rule(
    project_id="omniclaude",
    rule_id="max_function_complexity"
)
```

### Enable Rule

```python
await engine.enable_rule(
    project_id="omniclaude",
    rule_id="max_function_complexity"
)
```

### List Rules

```python
rules = await engine.get_project_rules("omniclaude")
for rule in rules:
    print(f"{rule.rule_id}: {rule.enabled} ({rule.severity})")
```

## Best Practices

### 1. Rule Design
- Keep rules focused and single-purpose
- Use descriptive rule_id and description
- Test patterns thoroughly with sample code
- Balance weight distribution across rules

### 2. Severity Selection
- **Critical**: Security, architecture compliance
- **Warning**: Code quality, best practices
- **Suggestion**: Optimizations, minor improvements

### 3. Weight Balancing
- Critical rules: Higher weights (0.15-0.25)
- Total weights per project: 1.0-2.0
- Adjust based on project priorities

### 4. Pattern Writing
- Test regex patterns before deployment
- Use non-capturing groups: `(?:pattern)`
- Escape special characters: `\\.dict\\(`
- Use multiline mode when needed

### 5. Maintenance
- Review rules quarterly
- Update patterns as codebase evolves
- Disable outdated rules rather than deleting
- Document rule changes

## Integration with Quality Service

Custom rules integrate with `CodegenQualityService`:

```python
# Combined quality assessment
class EnhancedQualityService:
    def __init__(self):
        self.quality_scorer = ComprehensiveONEXScorer()
        self.custom_rules_engine = CustomQualityRulesEngine()

    async def assess_code(self, code: str, project_id: str) -> Dict[str, Any]:
        # Standard quality assessment
        standard_result = self.quality_scorer.analyze_content(code)

        # Custom rules evaluation
        custom_result = await self.custom_rules_engine.evaluate_rules(
            project_id, code
        )

        # Combine scores (weighted)
        combined_score = (
            standard_result["quality_score"] * 0.7 +
            custom_result["custom_score"] * 0.3
        )

        return {
            "quality_score": combined_score,
            "standard_score": standard_result["quality_score"],
            "custom_score": custom_result["custom_score"],
            "violations": custom_result["violations"],
            "warnings": custom_result["warnings"],
            "suggestions": custom_result["suggestions"]
        }
```

## Troubleshooting

### Pattern Not Matching

```python
# Test pattern independently
import re
pattern = re.compile(r"your_pattern", re.MULTILINE)
matches = pattern.findall(test_code)
print(f"Matches: {matches}")
```

### Rule Not Loading

```python
# Check YAML syntax
import yaml
with open("config/quality_rules/your_project.yaml") as f:
    config = yaml.safe_load(f)
    print(config)
```

### Unexpected Failures

```python
# Enable debug logging
import logging
logging.getLogger("services.quality.custom_rules").setLevel(logging.DEBUG)
```

## Future Enhancements

- [ ] Machine learning-based rule suggestions
- [ ] Auto-fix capabilities for violations
- [ ] Cross-project rule inheritance
- [ ] Rule effectiveness analytics
- [ ] IDE integration (VS Code, PyCharm)

## References

- **Custom Rules Engine**: `services/intelligence/src/services/quality/custom_rules.py`
- **Quality Service**: `services/intelligence/src/services/quality/codegen_quality_service.py`
- **MVP Plan**: `MVP_PHASE_5_INTELLIGENCE_FEATURES_PLAN.md` (lines 728-853)

---

**Version**: 1.0.0
**Updated**: 2025-10-15
**Contact**: Archon Intelligence Team
