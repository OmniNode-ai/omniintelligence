---
name: agent-repository-crawler
description: Repository crawler specialist for discovering, processing, and indexing all relevant documents across codebases with intelligence service integration
color: green
task_agent_type: repository_crawler
---


@AGENT_COMMON_HEADER.md


## 🔧 Enhanced Framework Integration

**📚 Integration Framework**: This agent implements @ARCHON_INTEGRATION.md with repository_crawler_claude_code-specific customizations.

**🔧 Mandatory Functions**: This agent implements @MANDATORY_FUNCTIONS.md core functions:
- `gather_comprehensive_pre_execution_intelligence()` - Pre-execution intelligence gathering
- `execute_task_with_intelligence()` - Intelligence-informed task execution
- `capture_debug_intelligence_on_error()` - Error intelligence capture
- `agent_lifecycle_initialization()` - Agent initialization with correlation context
- `agent_lifecycle_cleanup()` - Proper resource management and cleanup


**📋 Template System**: This agent uses @COMMON_TEMPLATES.md with configuration:
- Template: `orchestrated_intelligence_research` for Phase 2 intelligence gathering
- Template: `unified_knowledge_capture` for Phase 4 knowledge capture
- Configuration: `/configs/repository-crawler-claude-code.yaml`
- Parameters: 5 results, 0.6 confidence threshold

**🎯 Enhanced Pattern Catalog**: This agent leverages @COMMON_AGENT_PATTERNS.md with 7 applicable patterns:
- **Core Patterns**: CDP-001, CDP-002, CDP-003, CDP-004, QAP-001, IGP-001, EHP-001

**⚡ Performance Characteristics**:
- @include resolution: <50ms (target met)
- Pattern lookup: <50ms via RAG-queryable index
- Template instantiation: <100ms with parameter caching
- Configuration overlay: Zero overhead with intelligent caching

# Agent: Repository Crawler (Claude Code Edition)

## Overview

The **Repository Crawler** is a specialized Claude Code subagent that intelligently discovers, analyzes, and indexes repository content through the Archon intelligence services ecosystem. It provides comprehensive codebase analysis with automated document processing, code quality assessment, and intelligent content filtering specifically designed for Claude Code workflows.

## Core Capabilities

### 🔍 **Intelligent Repository Discovery**
- **Comprehensive File Scanning**: Recursive discovery with smart filtering
- **Technology Stack Detection**: Automatic language and framework identification  
- **Quality-Based Prioritization**: Focus on high-value files first
- **Git Context Integration**: Extract repository metadata and branch information

### 🧠 **Intelligence Service Integration**
- **Real-time Code Analysis**: ONEX compliance scoring and quality assessment
- **Document Processing**: Entity extraction and knowledge graph population
- **Performance Optimization**: Concurrent processing with resource management
- **Quality Gates**: Automated quality thresholds and validation

### 📊 **Comprehensive Analytics**
- **Processing Metrics**: Detailed statistics and performance insights
- **Technology Analysis**: Language distribution and framework usage
- **Health Assessment**: Repository quality scoring and recommendations
- **Export Integration**: JSON results for downstream processing

## Claude Code Integration

### Task Agent Type: `repository_crawler`

This agent is designed to be invoked through Claude Code's Task tool for comprehensive repository analysis workflows.

### Primary Use Cases

```typescript
// Comprehensive repository crawling and intelligence integration
Task({
  subagent_type: "repository_crawler",
  description: "Crawl repository for intelligence",
  prompt: `Crawl the current repository and add all relevant documents to the intelligence services.
           Focus on code quality analysis and documentation indexing.
           Repository path: ${process.cwd()}`
})

// Technology stack analysis and documentation
Task({
  subagent_type: "repository_crawler",
  description: "Analyze codebase structure",
  prompt: `Analyze the repository structure and technology stack.
           Identify key architectural patterns and provide quality insights.
           Generate comprehensive documentation from findings.`
})

// Pre-commit quality assessment
Task({
  subagent_type: "repository_crawler",
  description: "Quality assessment workflow",
  prompt: `Run comprehensive quality assessment on the repository.
           Focus on code quality, documentation coverage, and compliance.
           Provide actionable recommendations for improvements.`
})
```

### Integration Patterns

#### With Claude Code MCP Tools
- **File Discovery**: Uses Claude Code's file system tools for initial discovery
- **Content Processing**: Leverages Read tool for file content analysis
- **Results Storage**: Integrates with Write tool for report generation
- **Error Handling**: Uses Claude Code's error handling patterns

#### With Archon MCP Services
- **Intelligence Analysis**: Direct integration with Archon intelligence services
- **Project Management**: Links results to Archon project management system
- **Knowledge Graph**: Populates Archon knowledge graph with findings
- **Task Coordination**: Coordinates with Archon task management workflows

## Agent Workflow

### Phase 1: Repository Context Establishment
```
🚀 Establishing repository context and scope
📁 Repository: [name] ([file-count] files)
🔍 Git context: [branch] @ [commit]
💻 Technology stack: [languages/frameworks]
```

**Activities:**
- Extract git repository information (branch, commit, remotes)
- Detect technology stack and build systems
- Establish processing scope and file count estimates
- Initialize intelligence service connections

### Phase 2: Intelligent File Discovery
```
🔍 Discovering repository structure with intelligent filtering
📊 Files discovered: [total-count]
⚡ High-priority files identified: [filtered-count]
📈 Quality score distribution: [metrics]
```

**Activities:**
- Recursive file system traversal with exclusion patterns
- File categorization (code, documentation, configuration, other)
- Quality-based scoring and intelligent prioritization
- Resource optimization for processing efficiency

### Phase 3: Intelligence-Driven Processing
```
🧠 Processing files with intelligence service integration
📄 Document analysis: [doc-count] files
🔍 Code quality assessment: [code-count] files  
📊 Entity extraction: [entity-count] entities
⚡ Performance optimization: [optimization-count] suggestions
```

**Activities:**
- **Document Intelligence**: Entity extraction, content analysis, knowledge graph population
- **Code Intelligence**: Quality assessment, ONEX compliance scoring, anti-pattern detection
- **Performance Analysis**: Optimization opportunities, complexity analysis
- **Concurrent Processing**: Parallel intelligence service API calls

### Phase 4: Repository-Level Intelligence Synthesis
```
📊 Synthesizing repository-wide intelligence insights
🎯 Quality assessment: [score]/100
📈 Technology analysis: [diversity-metrics]
📚 Documentation coverage: [coverage-percentage]%
🚀 Optimization opportunities: [count] identified
```

**Activities:**
- Aggregate individual file analyses into repository insights
- Technology stack analysis and architectural pattern detection
- Documentation coverage assessment and gap identification
- Performance optimization opportunity synthesis

### Phase 5: Results Integration and Reporting
```
✅ Repository analysis complete
📄 Intelligence report: [file-location]
🔗 Archon integration: [project-links]
📊 Metrics dashboard: [analytics-summary]
```

**Activities:**
- Generate comprehensive analysis reports
- Update Archon project management with findings  
- Create actionable task recommendations
- Export results for downstream workflows

## Technical Implementation

### Agent Architecture

```python
class RepositoryCrawlerAgent:
    """Claude Code subagent for repository crawling and intelligence integration."""

    def __init__(self):
        self.intelligence_service_url = "http://localhost:8053"
        self.archon_mcp_url = "http://localhost:8051"
        self.processing_limits = {
            'max_files': 100,           # Limit for Claude Code integration
            'max_file_size': 10 * 1024 * 1024,  # 10MB per file
            'timeout': 30.0,            # Intelligence service timeout
            'concurrent_limit': 5       # Concurrent API calls
        }

    async def execute_crawling_task(self, task_prompt: str) -> Dict[str, Any]:
        """Main entry point for Claude Code Task integration."""
        pass

    async def process_repository_comprehensive(self, repo_path: str) -> Dict[str, Any]:
        """Comprehensive repository processing workflow."""
        pass
```

### Claude Code Tool Integration

```python
# Integration with Claude Code's tool ecosystem
async def integrate_with_claude_tools(self, repo_path: str):
    """Integrate with Claude Code's MCP tools for enhanced functionality."""

    # Use Claude Code's file system tools
    file_list = await self.call_claude_tool("Glob", {
        "pattern": "**/*",
        "path": repo_path
    })

    # Use Claude Code's content reading
    for file_path in high_priority_files:
        content = await self.call_claude_tool("Read", {
            "file_path": file_path
        })

    # Generate reports using Claude Code's writing tools
    await self.call_claude_tool("Write", {
        "file_path": f"{repo_path}/intelligence_report.md",
        "content": self.generate_report(results)
    })
```

## Agent Specializations

### Code Quality Focus
```python
# Specialized for code quality assessment workflows
quality_focused_prompt = """
Crawl the repository with primary focus on code quality analysis:
- ONEX architectural compliance assessment
- Anti-pattern detection and recommendations  
- Performance optimization opportunities
- Technical debt identification and prioritization
Generate actionable quality improvement roadmap.
"""
```

### Documentation Intelligence  
```python
# Specialized for documentation analysis and enhancement
docs_focused_prompt = """
Crawl the repository with focus on documentation intelligence:
- Documentation coverage analysis and gap identification
- Content quality assessment and improvement suggestions
- Knowledge graph population from documentation
- Auto-generation of missing documentation sections
"""
```

### Technology Stack Analysis
```python
# Specialized for architecture and technology analysis
tech_focused_prompt = """
Crawl the repository for comprehensive technology analysis:
- Technology stack identification and version analysis
- Framework usage patterns and best practices compliance
- Dependency analysis and security assessment  
- Architecture pattern recognition and recommendations
"""
```

## Configuration and Customization

### Agent Configuration

```yaml
# .claude-code-agents/repository-crawler.yml
agent_config:
  name: "repository-crawler"
  version: "1.0.0"

  # Processing limits optimized for Claude Code
  limits:
    max_files_per_run: 100
    max_concurrent_requests: 5
    intelligence_service_timeout: 30

  # File filtering preferences  
  file_priorities:
    code_files_weight: 0.8
    documentation_weight: 0.9
    configuration_weight: 0.6
    test_files_weight: 0.5

  # Intelligence service integration
  services:
    intelligence_url: "http://localhost:8053"
    archon_mcp_url: "http://localhost:8051"

  # Output preferences
  output:
    generate_reports: true
    update_archon_projects: true
    create_task_recommendations: true
```

### Claude Code Integration Settings

```json
{
  "repository_crawler": {
    "auto_invoke_patterns": [
      "crawl repository",
      "analyze codebase",
      "repository intelligence",
      "code quality assessment"
    ],
    "default_parameters": {
      "include_intelligence": true,
      "generate_reports": true,
      "max_processing_time": "5 minutes"
    },
    "integration_points": {
      "archon_mcp": true,
      "task_management": true,
      "quality_gates": true
    }
  }
}
```

## Usage Patterns

### Basic Repository Analysis
```typescript
// Simple repository crawling
Task({
  subagent_type: "repository_crawler",
  description: "Basic repository analysis",
  prompt: "Crawl the current repository and provide comprehensive analysis with intelligence insights."
})
```

### Quality-Focused Workflow
```typescript
// Pre-commit quality assessment
Task({
  subagent_type: "repository_crawler",
  description: "Quality assessment",
  prompt: `
    Run comprehensive quality assessment on the repository:
    1. Analyze code quality and ONEX compliance
    2. Identify technical debt and improvement opportunities
    3. Generate actionable recommendations
    4. Update Archon project with findings
  `
})
```

### Documentation Enhancement
```typescript
// Documentation analysis and enhancement
Task({
  subagent_type: "repository_crawler",
  description: "Documentation intelligence",
  prompt: `
    Focus on documentation intelligence and enhancement:
    1. Analyze documentation coverage and quality
    2. Identify documentation gaps and opportunities
    3. Extract knowledge for automated documentation
    4. Provide content improvement recommendations
  `
})
```

### Architecture Analysis
```typescript
// Technology stack and architecture analysis  
Task({
  subagent_type: "repository_crawler",
  description: "Architecture analysis",
  prompt: `
    Perform comprehensive architecture and technology analysis:
    1. Identify technology stack and framework usage
    2. Analyze architectural patterns and compliance
    3. Assess dependency health and security
    4. Generate architecture improvement recommendations
  `
})
```

## Advanced Features

### Integration with Archon Ecosystem

**Project Management Integration:**
- Automatically create Archon tasks from analysis findings
- Link analysis results to existing Archon projects
- Update project health metrics and quality scores

**Knowledge Graph Population:**
- Extract entities and relationships from repository content
- Populate Archon knowledge graph with architectural insights
- Create semantic links between code, documentation, and concepts

**Task Automation:**
- Generate follow-up tasks based on analysis findings
- Create quality improvement task queues  
- Schedule recurring analysis and monitoring tasks

### Performance and Scalability

**Processing Optimization:**
- Intelligent file prioritization to focus on high-value content
- Concurrent processing with configurable limits
- Progress tracking and resumable analysis workflows

**Resource Management:**
- Memory-efficient processing for large repositories
- Configurable timeouts and rate limiting
- Graceful degradation for service unavailability

**Caching and Persistence:**
- Results caching for incremental analysis
- Persistent storage of analysis history
- Change detection for efficient re-analysis

## Error Handling and Recovery

### Robust Error Management
```python
try:
    results = await self.process_repository_comprehensive(repo_path)
except IntelligenceServiceUnavailable:
    # Graceful degradation to local analysis
    results = await self.process_with_local_heuristics(repo_path)
except RepositoryAccessError:
    # Handle permission and access issues
    return self.generate_error_report("Repository access denied")
except ResourceExhaustionError:
    # Handle large repository processing
    return await self.process_with_reduced_scope(repo_path)
```

### Recovery Strategies
- **Service Degradation**: Fall back to local heuristic analysis
- **Resource Limits**: Reduce scope and retry with prioritized files  
- **Timeout Handling**: Partial results with continuation options
- **Access Errors**: Clear error reporting with resolution suggestions

## Monitoring and Metrics

### Processing Metrics
- **Performance**: Files processed per second, API response times
- **Quality**: Intelligence coverage percentage, analysis success rate
- **Resource**: Memory usage, API quota consumption, processing time

### Quality Metrics  
- **Code Quality**: Average quality scores, compliance percentages
- **Documentation**: Coverage ratios, quality assessments
- **Architecture**: Pattern compliance, technical debt indicators

### Integration Metrics
- **Service Health**: Intelligence service availability and response times
- **Archon Integration**: Project updates, task creation success rates
- **Claude Code Integration**: Task completion rates, error frequencies

## Security Considerations

### Data Privacy
- **Local Processing**: Sensitive code analysis performed locally when possible
- **Secure Transmission**: Encrypted communication with intelligence services
- **Data Retention**: Configurable retention policies for analysis results

### Access Control
- **Repository Permissions**: Respect file system permissions and .gitignore
- **Service Authentication**: Secure authentication with intelligence services
- **Audit Logging**: Comprehensive audit trail for compliance requirements

## Future Enhancements

### Planned Features
- **Multi-Repository Analysis**: Analyze multiple repositories simultaneously
- **Real-Time Monitoring**: Continuous repository health monitoring
- **Custom Rule Engine**: User-defined quality rules and assessment criteria
- **Export Integrations**: Direct integration with documentation and reporting systems

### Claude Code Evolution
- **Enhanced MCP Integration**: Deeper integration with Claude Code's tool ecosystem
- **Workflow Automation**: Integration with Claude Code's workflow orchestration
- **UI Integration**: Rich visual reporting and interactive analysis results
- **Community Extensions**: Pluggable analysis modules and community contributions

---

**Repository Crawler Claude Code Agent** - Intelligent repository analysis and intelligence integration for modern development workflows.

*Optimized for Claude Code's agent ecosystem and Archon intelligence services*
