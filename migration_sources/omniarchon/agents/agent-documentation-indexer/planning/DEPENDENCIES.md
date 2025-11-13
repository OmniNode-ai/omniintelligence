# Documentation Indexer Agent - Dependencies Configuration

## Architecture Overview

The documentation indexer agent requires a simple, focused dependency setup optimized for file system operations, content processing, and Archon MCP integration. This is a tool-based agent that processes documentation files and indexes them into the Archon RAG system.

## Dependency Structure

```
dependencies/
├── __init__.py
├── settings.py       # Environment configuration
├── providers.py      # Model provider setup
├── dependencies.py   # Agent dependencies
├── agent.py         # Agent initialization
├── .env.example     # Environment template
└── requirements.txt # Python dependencies
```

## Core Configuration Files

### settings.py - Environment Configuration

```python
"""
Configuration management for documentation indexer agent.
"""

import os
from typing import Optional, List, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ConfigDict
from dotenv import load_dotenv
import json
from pathlib import Path

# Load environment variables from .env file
load_dotenv()


class IndexerConfig(BaseSettings):
    """Indexing configuration with file patterns and processing rules."""

    # File Discovery Patterns
    include_patterns: List[str] = Field(
        default=[
            "**/*.md", "**/*.txt", "**/*.rst", "**/*.adoc",
            "**/*.yaml", "**/*.yml", "**/README*", "**/CLAUDE.md",
            "docs/**/*"
        ],
        description="File patterns to include in indexing"
    )

    exclude_patterns: List[str] = Field(
        default=[
            "node_modules/**/*", ".git/**/*", "dist/**/*", "build/**/*",
            "__pycache__/**/*", ".venv/**/*", "*.log", ".env*",
            "venv/**/*", ".pytest_cache/**/*"
        ],
        description="File patterns to exclude from indexing"
    )

    # Content Processing
    chunk_size: int = Field(default=1500, description="Target tokens per chunk")
    chunk_overlap: int = Field(default=200, description="Token overlap between chunks")
    batch_size: int = Field(default=10, description="Documents per batch operation")
    max_file_size_mb: int = Field(default=10, description="Maximum file size to process")

    # Project Detection
    project_types: Dict[str, bool] = Field(
        default={
            "detect_claude_code": True,
            "detect_python": True,
            "detect_node": True,
            "detect_archon": True
        },
        description="Project type detection flags"
    )

    # Special File Handling
    special_files: Dict[str, str] = Field(
        default={
            "CLAUDE.md": "high_priority",
            "README.md": "high_priority",
            "agent-*.yaml": "agent_spec",
            "agent-*.md": "agent_documentation"
        },
        description="Special file handling rules"
    )


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # LLM Configuration
    llm_provider: str = Field(default="openai", description="LLM provider")
    llm_api_key: str = Field(..., description="API key for LLM provider")
    llm_model: str = Field(default="gpt-4o-mini", description="Model for content processing")
    llm_base_url: Optional[str] = Field(
        default="https://api.openai.com/v1",
        description="Base URL for LLM API"
    )

    # Archon Integration
    archon_mcp_port: int = Field(default=8051, description="Archon MCP server port")
    archon_mcp_host: str = Field(default="localhost", description="Archon MCP server host")
    archon_mcp_url: Optional[str] = Field(None, description="Full Archon MCP URL")

    # Agent Configuration
    indexer_config_path: Optional[str] = Field(
        default=".claude/indexing-config.json",
        description="Path to indexing configuration file"
    )

    # Processing Configuration
    max_concurrent_files: int = Field(default=5, description="Max concurrent file processing")
    retry_attempts: int = Field(default=3, description="Max retry attempts for failed operations")
    retry_delay_seconds: int = Field(default=1, description="Delay between retry attempts")

    # Application Settings
    app_env: str = Field(default="development", description="Environment")
    log_level: str = Field(default="INFO", description="Logging level")
    debug: bool = Field(default=False, description="Debug mode")
    progress_reporting: bool = Field(default=True, description="Enable progress reporting")

    @field_validator("llm_api_key")
    @classmethod
    def validate_llm_key(cls, v):
        """Ensure LLM API key is not empty."""
        if not v or v.strip() == "":
            raise ValueError("LLM API key cannot be empty")
        return v

    @property
    def computed_archon_mcp_url(self) -> str:
        """Compute full Archon MCP URL."""
        if self.archon_mcp_url:
            return self.archon_mcp_url
        return f"http://{self.archon_mcp_host}:{self.archon_mcp_port}"

    def load_indexer_config(self) -> IndexerConfig:
        """Load indexer configuration from file or defaults."""
        if self.indexer_config_path and Path(self.indexer_config_path).exists():
            try:
                with open(self.indexer_config_path, 'r') as f:
                    config_data = json.load(f)
                return IndexerConfig(**config_data)
            except Exception as e:
                print(f"Warning: Failed to load indexer config: {e}, using defaults")

        return IndexerConfig()


def load_settings() -> Settings:
    """Load settings with proper error handling."""
    try:
        return Settings()
    except Exception as e:
        error_msg = f"Failed to load settings: {e}"
        if "llm_api_key" in str(e).lower():
            error_msg += "\nMake sure to set LLM_API_KEY in your .env file"
        raise ValueError(error_msg) from e


# Global settings instance
settings = load_settings()
```

### providers.py - Model Provider Configuration

```python
"""
Model provider configuration for documentation indexer agent.
Optimized for cost-effective content processing.
"""

from typing import Optional, Union
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.openai import OpenAIProvider
from .settings import settings


def get_llm_model(model_choice: Optional[str] = None) -> Union[OpenAIModel, AnthropicModel]:
    """
    Get LLM model configuration optimized for content processing.

    Args:
        model_choice: Optional override for model choice

    Returns:
        Configured LLM model instance
    """
    provider = settings.llm_provider.lower()
    model_name = model_choice or settings.llm_model

    if provider == "openai":
        provider_instance = OpenAIProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key
        )
        return OpenAIModel(model_name, provider=provider_instance)

    elif provider == "anthropic":
        return AnthropicModel(
            model_name,
            api_key=settings.llm_api_key
        )

    else:
        raise ValueError(f"Unsupported provider: {provider}")


def get_fallback_model() -> Optional[OpenAIModel]:
    """
    Get fallback model for reliability (cheaper model).

    Returns:
        Fallback model for content processing
    """
    if settings.llm_provider == "openai":
        return OpenAIModel(
            "gpt-4o-mini",  # Most cost-effective for content processing
            api_key=settings.llm_api_key
        )
    return None
```

### dependencies.py - Agent Dependencies

```python
"""
Dependencies for Documentation Indexer agent.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Set
from pathlib import Path
import logging
import asyncio
import aiofiles
import aiohttp
from .settings import IndexerConfig

logger = logging.getLogger(__name__)


@dataclass
class IndexerDependencies:
    """
    Dependencies for documentation indexer agent.

    Handles file system operations, content processing,
    and Archon MCP integration.
    """

    # Configuration
    indexer_config: IndexerConfig
    archon_mcp_url: str
    max_concurrent_files: int = 5
    retry_attempts: int = 3
    retry_delay: int = 1
    debug: bool = False

    # Runtime State
    session_id: Optional[str] = None
    project_root: Optional[Path] = None
    target_project_id: Optional[str] = None

    # Processing Tracking
    processed_files: Set[str] = field(default_factory=set)
    failed_files: Dict[str, str] = field(default_factory=dict)
    total_chunks_created: int = 0

    # HTTP Client for Archon MCP
    _http_session: Optional[aiohttp.ClientSession] = field(default=None, init=False, repr=False)

    # File Processing Semaphore
    _file_semaphore: Optional[asyncio.Semaphore] = field(default=None, init=False, repr=False)

    @property
    def http_session(self) -> aiohttp.ClientSession:
        """Lazy initialization of HTTP session for Archon MCP."""
        if self._http_session is None:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self._http_session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Archon-DocumentationIndexer/1.0"
                }
            )
        return self._http_session

    @property
    def file_semaphore(self) -> asyncio.Semaphore:
        """Semaphore for controlling concurrent file processing."""
        if self._file_semaphore is None:
            self._file_semaphore = asyncio.Semaphore(self.max_concurrent_files)
        return self._file_semaphore

    def is_file_included(self, file_path: Path) -> bool:
        """
        Check if a file should be included based on patterns.

        Args:
            file_path: Path to check

        Returns:
            True if file should be processed
        """
        file_str = str(file_path)

        # Check exclude patterns first
        for pattern in self.indexer_config.exclude_patterns:
            if file_path.match(pattern):
                return False

        # Check include patterns
        for pattern in self.indexer_config.include_patterns:
            if file_path.match(pattern):
                return True

        return False

    def get_file_priority(self, file_path: Path) -> str:
        """
        Get processing priority for a file.

        Args:
            file_path: File to check

        Returns:
            Priority level (high_priority, agent_spec, agent_documentation, normal)
        """
        file_name = file_path.name

        for pattern, priority in self.indexer_config.special_files.items():
            if file_path.match(pattern):
                return priority

        return "normal"

    def should_process_file(self, file_path: Path) -> bool:
        """
        Check if file should be processed considering size and type.

        Args:
            file_path: Path to check

        Returns:
            True if file should be processed
        """
        try:
            # Check if file exists and is readable
            if not file_path.exists() or not file_path.is_file():
                return False

            # Check file size
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.indexer_config.max_file_size_mb:
                logger.warning(f"Skipping large file: {file_path} ({file_size_mb:.1f}MB)")
                return False

            # Check if it's a text file (basic check)
            try:
                with open(file_path, 'rb') as f:
                    sample = f.read(1024)
                    # Check if it's mostly text (allow some binary chars)
                    text_chars = sum(1 for c in sample if c < 128 and c >= 32 or c in [9, 10, 13])
                    if len(sample) > 0 and text_chars / len(sample) < 0.7:
                        logger.debug(f"Skipping likely binary file: {file_path}")
                        return False
            except Exception:
                return False

            return self.is_file_included(file_path)

        except Exception as e:
            logger.error(f"Error checking file {file_path}: {e}")
            return False

    async def discover_documentation_files(self, root_path: Path) -> List[Path]:
        """
        Discover all documentation files in project.

        Args:
            root_path: Project root directory

        Returns:
            List of discovered documentation files
        """
        self.project_root = root_path
        discovered_files = []

        logger.info(f"Discovering documentation files in: {root_path}")

        # Recursively find all files
        for pattern in self.indexer_config.include_patterns:
            try:
                for file_path in root_path.rglob(pattern.lstrip("*/")):
                    if self.should_process_file(file_path):
                        discovered_files.append(file_path)
            except Exception as e:
                logger.error(f"Error processing pattern {pattern}: {e}")

        # Remove duplicates and sort by priority
        unique_files = list(set(discovered_files))

        # Sort by priority (high priority first)
        def sort_key(file_path):
            priority = self.get_file_priority(file_path)
            priority_order = {
                "high_priority": 0,
                "agent_spec": 1,
                "agent_documentation": 2,
                "normal": 3
            }
            return priority_order.get(priority, 3)

        unique_files.sort(key=sort_key)

        logger.info(f"Discovered {len(unique_files)} documentation files")
        return unique_files

    async def cleanup(self):
        """Cleanup resources when done."""
        if self._http_session:
            await self._http_session.close()
            self._http_session = None

        # Log final statistics
        logger.info(f"Indexing complete: {len(self.processed_files)} files processed, "
                   f"{self.total_chunks_created} chunks created, "
                   f"{len(self.failed_files)} files failed")

        if self.failed_files:
            logger.warning(f"Failed files: {list(self.failed_files.keys())}")

    @classmethod
    def from_settings(cls, settings, **kwargs):
        """
        Create dependencies from settings with overrides.

        Args:
            settings: Settings instance
            **kwargs: Override values

        Returns:
            Configured IndexerDependencies instance
        """
        indexer_config = settings.load_indexer_config()

        return cls(
            indexer_config=indexer_config,
            archon_mcp_url=kwargs.get('archon_mcp_url', settings.computed_archon_mcp_url),
            max_concurrent_files=kwargs.get('max_concurrent_files', settings.max_concurrent_files),
            retry_attempts=kwargs.get('retry_attempts', settings.retry_attempts),
            retry_delay=kwargs.get('retry_delay', settings.retry_delay_seconds),
            debug=kwargs.get('debug', settings.debug),
            **{k: v for k, v in kwargs.items()
               if k not in ['archon_mcp_url', 'max_concurrent_files', 'retry_attempts', 'retry_delay', 'debug']}
        )
```

### agent.py - Agent Initialization

```python
"""
Documentation Indexer Agent - Pydantic AI Agent Implementation
"""

import logging
from typing import Optional
from pydantic_ai import Agent

from .providers import get_llm_model, get_fallback_model
from .dependencies import IndexerDependencies
from .settings import settings

logger = logging.getLogger(__name__)

# System prompt for content processing and chunking
SYSTEM_PROMPT = """
You are a documentation indexer agent specialized in discovering, processing, and indexing documentation files for RAG systems.

Your primary responsibilities:
1. **File Discovery**: Identify relevant documentation files (.md, .txt, .rst, .adoc, .yaml)
2. **Content Processing**: Extract, clean, and chunk content for optimal retrieval
3. **Archon Integration**: Index processed content into Archon's RAG intelligence system

Key principles:
- Preserve source attribution and metadata
- Create optimal chunk sizes (1000-2000 tokens) with natural boundaries
- Handle different file formats and encodings gracefully  
- Provide clear progress reporting and error handling
- Support incremental updates for changed files only

Available tools:
- File system operations (Read, Glob)
- Archon MCP integration (create_document)
- Content processing and chunking utilities

Process files systematically, maintain quality, and ensure all content is properly indexed for future retrieval.
"""

# Initialize the agent with proper configuration
agent = Agent(
    get_llm_model(),
    deps_type=IndexerDependencies,
    system_prompt=SYSTEM_PROMPT,
    retries=settings.retry_attempts
)

# Register fallback model if available
fallback = get_fallback_model()
if fallback:
    agent.models.append(fallback)
    logger.info("Fallback model configured")

# Tools will be registered by tool-integrator subagent
# from .tools import register_tools
# register_tools(agent, IndexerDependencies)


# Convenience functions for agent usage
async def run_indexer(
    project_path: str,
    project_id: Optional[str] = None,
    **dependency_overrides
) -> str:
    """
    Run documentation indexer for a project.

    Args:
        project_path: Path to project root directory
        project_id: Target Archon project ID (auto-detected if None)
        **dependency_overrides: Override default dependencies

    Returns:
        Indexing result summary
    """
    from pathlib import Path

    deps = IndexerDependencies.from_settings(
        settings,
        target_project_id=project_id,
        project_root=Path(project_path),
        **dependency_overrides
    )

    try:
        prompt = f"""
        Index all documentation in project: {project_path}

        Steps:
        1. Discover documentation files using configured patterns
        2. Process and chunk content optimally for RAG
        3. Index chunks into Archon project: {project_id or 'auto-detect'}
        4. Report progress and handle any errors gracefully

        Target project ID: {project_id or 'auto-detect from project structure'}
        """

        result = await agent.run(prompt, deps=deps)
        return result.data
    finally:
        await deps.cleanup()


async def run_incremental_indexer(
    project_path: str,
    project_id: Optional[str] = None,
    **dependency_overrides
) -> str:
    """
    Run incremental documentation indexer (changed files only).

    Args:
        project_path: Path to project root directory
        project_id: Target Archon project ID
        **dependency_overrides: Override default dependencies

    Returns:
        Incremental indexing result summary
    """
    from pathlib import Path

    deps = IndexerDependencies.from_settings(
        settings,
        target_project_id=project_id,
        project_root=Path(project_path),
        **dependency_overrides
    )

    try:
        prompt = f"""
        Perform incremental indexing for project: {project_path}

        Steps:
        1. Check existing indexed documents and their timestamps
        2. Identify files that have been modified since last indexing
        3. Re-process and update only changed content
        4. Remove outdated chunks for deleted or moved files
        5. Report what was updated

        Focus on efficiency - only process what has actually changed.
        """

        result = await agent.run(prompt, deps=deps)
        return result.data
    finally:
        await deps.cleanup()


def create_indexer_with_deps(**dependency_overrides) -> tuple[Agent, IndexerDependencies]:
    """
    Create agent instance with custom dependencies.

    Args:
        **dependency_overrides: Custom dependency values

    Returns:
        Tuple of (agent, dependencies)
    """
    deps = IndexerDependencies.from_settings(settings, **dependency_overrides)
    return agent, deps
```

### .env.example - Environment Template

```bash
# LLM Configuration (REQUIRED)
LLM_PROVIDER=openai
LLM_API_KEY=your-openai-api-key-here
LLM_MODEL=gpt-4o-mini  # Cost-effective for content processing
LLM_BASE_URL=https://api.openai.com/v1

# Archon MCP Integration (REQUIRED)
ARCHON_MCP_PORT=8051
ARCHON_MCP_HOST=localhost
# Optional: Full URL override
# ARCHON_MCP_URL=http://localhost:8051

# Indexer Configuration (Optional)
INDEXER_CONFIG_PATH=.claude/indexing-config.json

# Processing Settings
MAX_CONCURRENT_FILES=5
RETRY_ATTEMPTS=3
RETRY_DELAY_SECONDS=1

# Application Settings
APP_ENV=development
LOG_LEVEL=INFO
DEBUG=false
PROGRESS_REPORTING=true
```

### requirements.txt - Python Dependencies

```
# Core dependencies
pydantic-ai>=0.1.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-dotenv>=1.0.0

# LLM Provider
openai>=1.0.0

# Async file and HTTP operations
aiofiles>=23.0.0
aiohttp>=3.8.0
httpx>=0.25.0

# Content processing
markdown>=3.5.0
pyyaml>=6.0
chardet>=5.0.0  # Character encoding detection
python-magic>=0.4.27  # File type detection

# Text processing and chunking
tiktoken>=0.5.0  # Token counting for chunking
beautifulsoup4>=4.12.0  # HTML/XML parsing if needed

# Progress reporting
tqdm>=4.65.0
rich>=13.0.0  # Rich console output

# Development tools
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-aiohttp>=1.0.0
black>=23.0.0
ruff>=0.1.0

# Monitoring and logging
loguru>=0.7.0
```

## File Processing Patterns

### Content Chunking Strategy
- **Target Size**: 1000-2000 tokens per chunk using tiktoken
- **Natural Boundaries**: Split on headings, paragraphs, code blocks
- **Overlap**: 200 tokens between chunks for context continuity
- **Metadata Preservation**: Source file, section titles, timestamps

### File Type Handling
- **Markdown**: Parse headers for section-based chunking
- **YAML**: Extract agent specifications and configuration
- **Text Files**: Plain text processing with paragraph boundaries
- **RestructuredText**: Parse RST directives and sections
- **AsciiDoc**: Handle AsciiDoc formatting and structure

### Error Recovery
- **Encoding Issues**: UTF-8 primary, fallback to chardet detection
- **Large Files**: Stream processing for files > 10MB
- **Binary Detection**: Skip non-text files automatically
- **MCP Failures**: Retry with exponential backoff

## Security Considerations

### File System Security
- Path traversal protection
- File size limits (10MB default)
- Binary file detection and skipping
- Permission checking before file access

### API Security
- No sensitive data in API calls
- Proper HTTP session management
- Request timeout and retry limits
- Error message sanitization

## Testing Configuration

### Test Dependencies
```python
# tests/conftest.py
import pytest
from unittest.mock import Mock, AsyncMock
from pathlib import Path
import tempfile
import aiofiles

@pytest.fixture
def test_project_dir():
    """Create temporary project directory with sample files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # Create sample documentation files
        (project_path / "README.md").write_text("# Test Project\nSample content")
        (project_path / "docs").mkdir()
        (project_path / "docs" / "guide.md").write_text("# Guide\nDetailed guide")

        yield project_path

@pytest.fixture
def test_indexer_deps():
    """Test dependencies with mocked HTTP session."""
    from dependencies import IndexerDependencies, IndexerConfig

    config = IndexerConfig(
        chunk_size=500,  # Smaller chunks for testing
        batch_size=2
    )

    deps = IndexerDependencies(
        indexer_config=config,
        archon_mcp_url="http://test-mcp:8051",
        debug=True
    )

    # Mock HTTP session
    deps._http_session = AsyncMock()

    return deps
```

## Quality Checklist

- ✅ File discovery patterns configured
- ✅ Content processing and chunking logic
- ✅ Archon MCP integration dependencies
- ✅ Async file operations support
- ✅ Error handling and retry logic
- ✅ Progress reporting capabilities
- ✅ Configuration file support
- ✅ Security measures implemented
- ✅ Testing configuration provided
- ✅ Resource cleanup handled

## Integration Points

### With Archon MCP Server
- **Document Creation**: Uses create_document tool for indexing
- **Project Detection**: Auto-detects or creates target projects
- **Batch Operations**: Processes multiple documents efficiently

### With Other Agents
- **agent-rag-query**: Provides indexed content for retrieval
- **agent-documentation-architect**: Can trigger re-indexing after updates
- **agent-knowledge-manager**: Coordinates document lifecycle

This configuration provides a robust foundation for the documentation indexer agent, optimized for file system operations, content processing, and seamless integration with the Archon RAG intelligence system.
