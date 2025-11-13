# Intelligence Ingestion Patterns

**Manual Repository Ingestion + Pre-Push Hook Integration**

This document provides patterns for **manual repository ingestion** and **automated pre-push hook intelligence** for comprehensive code analysis and continuous intelligence updates.

## 🎯 Hybrid Intelligence System Architecture

### Manual Ingestion (Phase 1)
- **Developer-Controlled**: Manual analysis when needed
- **Targeted Analysis**: Focus on specific components or issues
- **Immediate Feedback**: Real-time intelligence insights
- **Deep Analysis**: Comprehensive repository-wide assessment

### Pre-Push Hook (Phase 2)  
- **Automated Updates**: Intelligence system stays current with code changes
- **Non-Intrusive**: Integrates with natural development workflow
- **Continuous Learning**: Builds knowledge base from all changes
- **Early Detection**: Catches issues before they reach production

## 📥 Manual Ingestion Capabilities

### agent-code-quality-analyzer --ingest-mode

**Repository-Wide Quality Analysis**:
```bash
@agent-code-quality-analyzer --ingest-repository /path/to/repo

# Comprehensive quality assessment:
# - Scan entire codebase for quality patterns
# - Establish ONEX compliance baseline across all files
# - Identify architectural inconsistencies  
# - Build quality trend database
# - Generate quality improvement roadmap
```

**Component-Specific Analysis**:
```bash
@agent-code-quality-analyzer --ingest-component /path/to/component

# Focused component analysis:
# - Deep dive into specific module or service
# - Component-level compliance scoring
# - Inter-component dependency quality assessment
# - Component-specific improvement recommendations
```

**Quality Pattern Discovery**:
```bash
@agent-code-quality-analyzer --discover-patterns /path/to/codebase

# Pattern mining and analysis:
# - Extract successful quality patterns from existing code
# - Identify anti-patterns and their frequency
# - Build pattern library for future recommendations
# - Generate coding standards based on successful patterns
```

### agent-performance --ingest-mode

**Performance Baseline Establishment**:
```bash
@agent-performance --ingest-repository /path/to/repo

# System-wide performance analysis:
# - Establish performance baselines for all components
# - Identify performance-critical code paths
# - Build performance trend tracking database
# - Generate optimization priority matrix
```

**Critical Path Analysis**:
```bash
@agent-performance --ingest-critical-paths /path/to/performance-sensitive

# Performance hotspot analysis:
# - Deep analysis of performance-critical components
# - Resource utilization pattern identification
# - Scalability bottleneck detection
# - Performance optimization opportunity mapping
```

**Performance Trend Analysis**:
```bash
@agent-performance --analyze-trends /path/to/repo --time-window 30d

# Historical performance analysis:
# - Analyze performance evolution over time
# - Identify performance regression patterns
# - Build predictive performance models
# - Generate proactive optimization recommendations
```

### agent-debug-intelligence --ingest-mode

**Bug Pattern Mining**:
```bash
@agent-debug-intelligence --ingest-repository /path/to/repo

# Historical bug analysis:
# - Analyze commit history for bug fix patterns
# - Correlate code quality issues with historical bugs
# - Build predictive bug detection models
# - Generate prevention pattern library
```

**Problem Area Analysis**:
```bash
@agent-debug-intelligence --ingest-problem-area /path/to/buggy-code

# Focused problem investigation:
# - Deep analysis of historically problematic code
# - Root cause pattern identification
# - Prevention strategy development
# - Quality correlation analysis
```

**Issue Correlation Analysis**:
```bash
@agent-debug-intelligence --correlate-issues /path/to/repo

# Multi-dimensional issue analysis:
# - Correlate quality metrics with bug frequency
# - Identify performance issues leading to bugs
# - Build comprehensive issue prediction models
# - Generate proactive debugging strategies
```

## 🔄 Pre-Push Hook Integration

### Universal Hook Installation

**One-Time Setup** (any repository):
```bash
# Install intelligence hook in any git repository
./install-hook.sh /path/to/your/repository

# Files created:
# - .git/hooks/pre-push (executable hook)
# - intelligence-hook-config.json (configuration)
# - .git/intelligence-knowledge/ (storage directory)
```

### Hook Configuration

**intelligence-hook-config.json** (automatically created):
```json
{
  "intelligence_enabled": true,
  "quality_analysis": {
    "enabled": true,
    "file_patterns": ["*.py", "*.js", "*.ts", "*.jsx", "*.tsx"],
    "exclude_patterns": ["node_modules/", "*.test.*", "__pycache__/"],
    "min_quality_score": 0.7,
    "fail_on_quality_drop": false
  },
  "performance_analysis": {
    "enabled": true,
    "critical_paths": ["src/api/", "src/database/"],
    "fail_on_performance_regression": false
  },
  "debug_analysis": {
    "enabled": true,
    "track_patterns": true,
    "learn_from_fixes": true
  },
  "hook_behavior": {
    "update_knowledge_base": true,
    "verbose_output": false,
    "max_analysis_time_seconds": 30
  }
}
```

### Automated Analysis Workflow

**Pre-Push Intelligence Process**:
1. **Change Detection**: Hook identifies files changed since last push
2. **File Filtering**: Applies include/exclude patterns from configuration
3. **Intelligence Analysis**: Runs appropriate agents on changed files
4. **Knowledge Update**: Captures insights in local knowledge base
5. **Results Logging**: Stores analysis results and metrics
6. **Optional Gating**: Can block pushes based on quality thresholds

## 📊 Combined Intelligence Benefits

### Manual + Automated Intelligence
- **Comprehensive Coverage**: Manual for deep analysis + automated for continuous updates
- **Developer Control**: Manual analysis when needed + automatic maintenance
- **Progressive Learning**: Both modes contribute to knowledge base growth
- **Quality Assurance**: Systematic quality monitoring with targeted deep dives

### Knowledge Accumulation
- **Pattern Library Growth**: Both manual and automated analysis contribute patterns
- **Trend Analysis**: Continuous data collection enables predictive capabilities
- **Context Awareness**: Repository-specific intelligence improves over time
- **Cross-Project Learning**: Intelligence patterns shared across repositories

## 🛠️ Implementation Examples

### Repository Onboarding
```bash
# Step 1: Initial comprehensive analysis (manual)
@agent-code-quality-analyzer --ingest-repository .
@agent-performance --ingest-repository .
@agent-debug-intelligence --ingest-repository .

# Step 2: Install automated hook
./install-hook.sh .

# Step 3: Verify setup
git push  # Hook runs automatically on first push
```

### Problem Investigation
```bash
# Manual deep dive into specific issues
@agent-debug-intelligence --ingest-problem-area src/problematic/

# Hook continues to monitor for similar patterns
# Future pushes automatically check for related issues
```

### Performance Monitoring
```bash
# Manual performance baseline establishment
@agent-performance --ingest-critical-paths src/api/

# Hook monitors performance regressions on every push
# Automatic detection of performance degradation
```

## 📈 Success Metrics

### Manual Ingestion Metrics
- **Repository Coverage**: % of codebase analyzed and baselined
- **Pattern Discovery**: Number of quality/performance patterns identified
- **Issue Prediction**: Accuracy of predictive models for bugs/performance
- **Baseline Establishment**: Performance and quality baselines created

### Pre-Push Hook Metrics  
- **Hook Adoption**: Number of repositories with intelligence hooks installed
- **Analysis Frequency**: Intelligence analysis runs per repository per week
- **Knowledge Growth**: Rate of knowledge base expansion from automated analysis
- **Issue Prevention**: Problems caught by hook before production

### Combined Intelligence Growth
- **Pattern Evolution**: Improvement in pattern recognition accuracy over time
- **Predictive Accuracy**: Enhancement in predictive capabilities
- **Cross-Repository Learning**: Intelligence sharing between projects
- **Developer Productivity**: Reduction in debugging time and quality issues

---

**Ready for Hybrid Intelligence?**

1. **Phase 1**: Start with manual ingestion for comprehensive repository analysis
2. **Phase 2**: Install pre-push hooks for continuous intelligence updates  
3. **Optimization**: Fine-tune configuration based on repository needs
4. **Scale**: Deploy across multiple repositories for maximum intelligence growth
