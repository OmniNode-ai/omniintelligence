# Claude Code Repository Crawler - Usage Guide

## 🎯 Overview

The **Claude Code Repository Crawler** is a specialized subagent designed for intelligent repository analysis with comprehensive intelligence service integration. It provides deep codebase insights, quality assessment, and documentation indexing specifically optimized for Claude Code workflows.

## Features

- **🔍 Intelligent File Discovery**: Advanced file discovery with quality-based filtering
- **🧠 Intelligence Service Integration**: Real-time code quality and document analysis
- **📊 Technology Stack Detection**: Automatic language and framework identification
- **⚡ Performance Optimized**: Concurrent processing with intelligent resource management
- **📈 Comprehensive Metrics**: Detailed processing statistics and quality insights
- **🔄 Flexible Configuration**: Dry-run mode, verbose output, and customizable parameters

## Quick Start

### Basic Usage

```bash
# Crawl current directory
python3 python/src/agents/repository_crawler.py

# Crawl specific repository
python3 python/src/agents/repository_crawler.py --repo-path /path/to/repository

# Dry run without intelligence service calls
python3 python/src/agents/repository_crawler.py --repo-path /path/to/repo --dry-run

# Verbose output for debugging
python3 python/src/agents/repository_crawler.py --repo-path /path/to/repo --verbose
```

### Command Line Options

```bash
python3 python/src/agents/repository_crawler.py [OPTIONS]

Options:
  --repo-path, -r PATH    Path to repository to crawl (default: current directory)
  --dry-run              Perform dry run without calling intelligence services
  --project-id, -p ID    Archon project ID for integration
  --verbose, -v          Enable verbose output for debugging
  --help, -h             Show help message
```

## Integration with Claude Code

### As MCP Subagent

Add to your Claude Code workflow:

```typescript
// Use repository crawler for comprehensive codebase analysis
"Crawl this repository and add all relevant documents to the intelligence services using the repository crawler subagent"

// Research codebase patterns
"Use the repository crawler to analyze the codebase structure and identify key architectural patterns"

// Quality assessment workflow
"Run the repository crawler with intelligence analysis to assess code quality across the entire project"
```

### With Archon Project Integration

```bash
# Link crawler results to specific Archon project
python3 python/src/agents/repository_crawler.py \
  --repo-path /path/to/repository \
  --project-id "550e8400-e29b-41d4-a716-446655440000"
```

## Intelligence Service Features

### Code Analysis
- **Quality Assessment**: ONEX compliance scoring and architectural analysis
- **Complexity Analysis**: Code complexity and maintainability metrics  
- **Pattern Detection**: Anti-pattern identification and best practice validation
- **Language-Specific Analysis**: Python, TypeScript, JavaScript, Java, Rust, Go support

### Document Processing
- **Entity Extraction**: Semantic entity discovery and relationship mapping
- **Content Quality**: Documentation completeness and clarity assessment
- **Knowledge Graph Integration**: Automatic knowledge graph population
- **Metadata Enrichment**: Enhanced document metadata and categorization

### Repository Intelligence
- **Technology Stack Detection**: Automatic framework and language identification
- **Project Classification**: Repository type and architectural pattern recognition
- **Dependency Analysis**: Technology stack and build tool discovery
- **Health Metrics**: Overall repository health and quality scoring

## Processing Workflow

### Phase 1: Repository Discovery
```
🚀 Starting comprehensive repository crawling
📁 Repository context established: [repo-name] ([file-count] files)
```
- Git repository information extraction
- Technology stack detection
- Initial file counting and categorization

### Phase 2: Intelligent File Discovery  
```
🔍 Scanning repository structure...
🔍 Files discovered: [count]
```
- Recursive file system traversal
- File categorization (code, documentation, configuration, other)
- Size and type-based filtering

### Phase 3: Quality-Based Filtering
```
⚡ Applying intelligent filtering...
⚡ Files filtered for processing: [count]
```
- **Quality Score Calculation**: File relevance and importance scoring
- **Intelligent Prioritization**: Focus on high-value files first
- **Resource Optimization**: Limit processing to top candidates

### Phase 4: Intelligence Integration
```
🧠 Processing files with intelligence integration...
📄 Analyzing document: [file-path]
🔍 Analyzing code file: [file-path]
🧠 Files processed with intelligence: [count]
```
- **Real-time Analysis**: Direct intelligence service integration
- **Content Processing**: Document entity extraction and code quality assessment
- **Concurrent Execution**: Parallel processing for optimal performance

### Phase 5: Repository-Level Intelligence
```
📊 Extracting repository-level intelligence...
📊 Intelligence insights extracted
```
- **Aggregate Analysis**: Repository-wide quality and technology insights
- **Pattern Recognition**: Cross-file architectural pattern detection
- **Health Assessment**: Overall repository health scoring

### Phase 6: Results Compilation
```
✅ Repository crawling completed in [time]s
📄 Detailed results saved to: repository_crawl_results.json
```

## Output and Results

### Console Output Summary
```
============================================================
🎉 REPOSITORY CRAWLING COMPLETE
============================================================
📁 Repository: [name]
⏱️ Processing Time: [time]s  
📊 Files Discovered: [count]
✅ Files Processed: [count]
🧠 Intelligence Assessments: [count]
📈 Success Rate: [percentage]%
🔍 Intelligence Coverage: [percentage]%
💻 Repository Type: [type]
📝 Primary Languages: [languages]
```

### Detailed JSON Results

The crawler generates `repository_crawl_results.json` with:

```json
{
  "crawling_summary": {
    "repository_name": "project-name",
    "processing_time_seconds": 1.17,
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "statistics": {
    "files_discovered": 780,
    "files_processed": 20,
    "intelligence_assessments": 20,
    "processing_success_rate": 0.026,
    "intelligence_coverage": 1.0
  },
  "intelligence_insights": {
    "quality_assessments": [...],
    "technology_analysis": {
      "primary_languages": ["python", "typescript"],
      "repository_type": "python_project"
    },
    "documentation_coverage": {...},
    "repository_health": {...}
  },
  "performance_metrics": {...}
}
```

## Configuration and Customization

### File Type Support

**Code Files:**
- Python (.py), JavaScript (.js), TypeScript (.ts)
- Java (.java), C++ (.cpp), C (.c), Go (.go)
- Rust (.rs), Ruby (.rb), PHP (.php), C# (.cs)

**Documentation:**
- Markdown (.md), reStructuredText (.rst), Plain text (.txt)
- AsciiDoc (.adoc), Org mode (.org)

**Configuration:**
- YAML (.yaml, .yml), JSON (.json), TOML (.toml)
- INI (.ini), Properties (.properties), Docker (Dockerfile)

### Intelligent Filtering

**Quality Scoring Factors:**
- **File Size**: Optimal size range (100-10,000 bytes)
- **Location**: High-value directories (src/, lib/, docs/)
- **Naming**: Important files (README, tests, config)
- **Category**: Code > Documentation > Configuration > Other

**Filtering Thresholds:**
- Code files: 0.2 (more inclusive)
- Documentation: 0.3
- Configuration: 0.4  
- Other files: 0.6 (more selective)

### Performance Tuning

**Processing Limits:**
- Maximum file size: 50MB (configurable)
- Chunk size target: 1,500 characters
- Chunk overlap: 300 characters
- Request timeout: 30 seconds
- Top files processed: 50 (configurable in filtering)

**Excluded Patterns:**
```python
exclude_patterns = {
    'node_modules', '.git', '__pycache__', 'venv', 'env',
    '.pytest_cache', 'coverage', 'dist', 'build', 'target',
    '.idea', '.vscode', 'vendor', 'bower_components'
}
```

## Troubleshooting

### Common Issues

**Intelligence Service Connection:**
```bash
# Test intelligence service availability
curl -s http://localhost:8053/health

# Expected response: HTTP 200
```

**Permission Errors:**
```bash
# Ensure crawler has read access to repository
ls -la /path/to/repository
```

**Memory Usage:**
```bash
# Monitor memory usage for large repositories
top -p $(pgrep -f repository_crawler)
```

### Debug Mode

Enable verbose output for detailed debugging:
```bash
python3 python/src/agents/repository_crawler.py \
  --repo-path /path/to/repo \
  --verbose
```

**Debug Output Includes:**
- File-by-file processing status
- Intelligence service API call details
- Error details and stack traces
- Performance timing information

### Dry Run Testing

Test crawler logic without intelligence service calls:
```bash
python3 python/src/agents/repository_crawler.py \
  --repo-path /path/to/repo \
  --dry-run
```

**Dry Run Features:**
- Mock intelligence analysis results
- Full processing workflow simulation
- No external API calls
- Perfect for testing and development

## Best Practices

### Repository Selection
- **Medium-sized repositories** (100-5,000 files) work best
- **Well-structured projects** with clear directory organization
- **Active repositories** with recent commits and documentation

### Intelligence Service Optimization  
- **Ensure service availability** before running large crawls
- **Monitor service load** during processing
- **Use dry-run mode** for initial testing

### Result Analysis
- **Review quality assessments** for code improvement opportunities
- **Analyze technology insights** for architecture decisions  
- **Monitor processing metrics** for performance optimization
- **Export results** to other analysis tools as needed

### Integration Workflows
- **Pre-commit analysis**: Crawl repository before major commits
- **Onboarding assistance**: Help new developers understand codebase structure
- **Architecture review**: Identify patterns and improvement opportunities
- **Documentation audits**: Assess documentation coverage and quality

## Advanced Usage

### Programmatic Integration

```python
from agents.repository_crawler import IntelligentRepositoryCrawler
import asyncio

async def custom_crawl():
    crawler = IntelligentRepositoryCrawler()
    crawler.verbose = True

    results = await crawler.crawl_repository_comprehensive(
        '/path/to/repository',
        project_id='your-archon-project-id'
    )

    # Process results
    print(f"Processed {results['statistics']['files_processed']} files")
    return results

# Run crawler
results = asyncio.run(custom_crawl())
```

### Custom Intelligence Workflows

Extend the crawler for specific use cases:
- **Security audits**: Focus on security-sensitive files
- **Documentation generation**: Extract content for automated docs
- **Dependency analysis**: Map technology stack dependencies  
- **Quality gates**: Enforce quality standards in CI/CD

## Support and Extensions

### Getting Help
- Review console output for processing status
- Check `repository_crawl_results.json` for detailed analysis
- Use `--verbose` flag for debugging information
- Verify intelligence service health and connectivity

### Future Enhancements
- **Multi-repository support**: Crawl multiple repositories simultaneously
- **Custom filtering rules**: User-defined file importance criteria
- **Export integrations**: Direct export to documentation systems
- **Real-time monitoring**: Live progress updates and metrics

---

**Repository Crawler** - Intelligent codebase discovery and analysis for modern development workflows.

*Built for the Archon Intelligence Services Ecosystem*
