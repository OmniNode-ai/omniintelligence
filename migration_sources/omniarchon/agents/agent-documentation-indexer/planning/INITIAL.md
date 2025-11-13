# Documentation Indexer Agent - Simple Requirements

## What This Agent Does
Automatically discovers, processes, and vectorizes all documentation across any project to populate the Archon RAG intelligence system with local project knowledge.

## Core Features (MVP)
1. **Auto-Discovery**: Find all documentation files (.md, .txt, .rst, .adoc, .yaml specs) in a project
2. **Content Processing**: Extract, clean, and chunk content optimally for RAG retrieval
3. **Batch Indexing**: Use Archon MCP tools to vectorize and store content in the intelligence system

## Technical Setup

### Model
- **Provider**: openai
- **Model**: gpt-4o-mini
- **Why**: Fast and cost-effective for content processing and chunking optimization

### Required Tools
1. **File System Tools**: Read, Glob for discovering documentation files
2. **Archon MCP Integration**: create_document for indexing content into RAG system
3. **Content Processing**: Built-in text processing for cleaning and chunking

### External Services
- **Archon MCP Server**: For indexing documents into the intelligence system
- **File System Access**: For discovering and reading documentation files

## Environment Variables
```bash
# Archon Integration
ARCHON_MCP_PORT=8051

# OpenAI for content processing
OPENAI_API_KEY=your-openai-api-key

# Optional: Configuration
INDEXER_CONFIG_PATH=.claude/indexing-config.json
```

## Core Workflow

### Phase 1: Project Discovery
1. **Root Analysis**: Identify project root and structure type
2. **Documentation Mapping**: Find all relevant documentation files
3. **Filtering Logic**: Skip build directories, node_modules, but include important READMEs

### Phase 2: Content Processing
1. **Content Extraction**: Read and parse different file formats (.md, .txt, .rst, .adoc)
2. **Content Cleaning**: Remove formatting artifacts, normalize encoding
3. **Intelligent Chunking**: Split content for optimal RAG performance (1000-2000 tokens)

### Phase 3: Archon Integration
1. **Project Context**: Create or identify target project in Archon
2. **Batch Indexing**: Use create_document MCP tool to index chunks
3. **Metadata Preservation**: Include source file path, update timestamps, content type

## File Discovery Strategy

### Include Patterns
```
**/*.md        # Markdown files
**/*.txt       # Text files  
**/*.rst       # ReStructuredText
**/*.adoc      # AsciiDoc
**/*.yaml      # Agent specs and configs
**/*.yml       # YAML documentation
**/README*     # All README files
**/CLAUDE.md   # Claude Code project docs
docs/**/*      # Documentation directories
```

### Exclude Patterns
```
node_modules/**/*      # Package dependencies
.git/**/*             # Git internals
dist/**/*             # Build outputs
build/**/*            # Build directories
__pycache__/**/*      # Python cache
.venv/**/*            # Virtual environments
*.log                 # Log files
```

## Content Processing Rules

### Chunking Strategy
- **Target Size**: 1000-2000 tokens per chunk
- **Overlap**: 200 tokens between adjacent chunks
- **Boundary Respect**: Split on natural boundaries (headings, paragraphs)
- **Metadata Inclusion**: Preserve source file, section titles, timestamps

### Special Handling
- **Code Blocks**: Preserve syntax highlighting markers and language tags
- **Agent YAML Files**: Extract system prompts, capabilities, and integration patterns
- **Tables**: Maintain structure for better searchability
- **Links**: Convert relative links to absolute where possible

## Archon MCP Integration

### Document Creation Pattern
```python
# For each processed chunk
mcp__archon__create_document(
    project_id="auto-detected-or-provided",
    title=f"{source_file}#{section_title}",
    document_type="documentation",
    content={
        "text": processed_chunk,
        "source_file": absolute_file_path,
        "source_section": section_title,
        "chunk_index": chunk_number,
        "file_type": file_extension,
        "last_modified": file_mtime,
        "project_structure": detected_structure
    }
)
```

### Batch Processing
- Process files in batches of 10 documents per MCP call
- Handle rate limiting and API failures gracefully
- Provide progress reporting for large documentation sets
- Support incremental updates (only re-index changed files)

## Configuration Support

### Default Configuration (.claude/indexing-config.json)
```json
{
  "include_patterns": ["**/*.md", "**/*.txt", "**/README*"],
  "exclude_patterns": ["node_modules/**", ".git/**", "dist/**"],
  "chunk_size": 1500,
  "chunk_overlap": 200,
  "batch_size": 10,
  "project_types": {
    "detect_claude_code": true,
    "detect_python": true,
    "detect_node": true,
    "detect_archon": true
  },
  "special_files": {
    "CLAUDE.md": "high_priority",
    "README.md": "high_priority",
    "agent-*.yaml": "agent_spec",
    "agent-*.md": "agent_documentation"
  }
}
```

## Success Criteria
- [ ] Discovers all documentation in Archon project (CLAUDE.md, agent specs, docs/)
- [ ] Successfully indexes content into Archon RAG system via MCP tools
- [ ] Handles different file formats and encodings correctly
- [ ] Processes large documentation sets without memory issues
- [ ] Provides clear progress feedback and error reporting
- [ ] Supports incremental updates for changed files only
- [ ] Maintains metadata for source attribution and freshness tracking

## Specific Use Cases

### Archon Project Indexing
- **CLAUDE.md**: Project overview and architecture
- **agents/*.md**: All 39+ agent specifications  
- **docs/****: Technical documentation
- **monitoring/README.md**: Monitoring setup
- **Agent YAML files**: Extract system prompts and capabilities

### General Project Indexing
- **README.md**: Project overview
- **docs/ directory**: Technical documentation
- **API specs**: OpenAPI, AsyncAPI documentation  
- **Configuration docs**: Setup and deployment guides

### Code Documentation
- **Inline comments**: Extract significant code comments
- **Docstrings**: Function and class documentation
- **Type annotations**: API interface documentation

## Error Handling Strategy

### File Processing Errors
- **Encoding Issues**: Try UTF-8, fallback to latin-1, report failures
- **Large Files**: Stream processing for files > 10MB
- **Binary Files**: Skip binary content, log attempts

### Archon Integration Errors
- **MCP Connection**: Retry with exponential backoff
- **Rate Limiting**: Implement request throttling
- **API Failures**: Queue failed operations for retry

### Recovery Mechanisms
- **Partial Success**: Continue processing other files if one fails
- **Resume Capability**: Support resuming interrupted indexing operations
- **Rollback**: Remove partially indexed content on critical failures

## Performance Considerations

### Scalability
- **Memory Management**: Stream large files, process in chunks
- **Parallel Processing**: Process multiple files concurrently
- **Progress Tracking**: Report progress for long-running operations

### Optimization
- **File Change Detection**: Only re-index modified files
- **Content Deduplication**: Skip identical chunks across files
- **Metadata Caching**: Cache file metadata to speed up incremental runs

## Assumptions Made
- Archon MCP server is running and accessible on port 8051
- create_document MCP tool accepts batch operations or can be called repeatedly
- Project structure follows common patterns (docs/, README.md, etc.)
- Files are primarily text-based documentation (not binary)
- Standard text encodings (UTF-8, ASCII) are used for documentation
- Agent will run with sufficient file system permissions to read project files
- Target projects have reasonable documentation sizes (< 100MB total)

---
Generated: 2025-09-04
Note: This is an MVP focused on core indexing functionality. Advanced features like semantic analysis, automatic categorization, and cross-reference detection can be added after the basic indexing works reliably.
