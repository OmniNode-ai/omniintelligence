"""
Documentation Indexer Agent - Pydantic AI Implementation

Discovers, processes, and indexes documentation across diverse project structures
for enhanced RAG knowledge systems with comprehensive Archon MCP integration.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

try:
    import yaml
    from bs4 import BeautifulSoup
    from markdown import markdown

    FULL_PROCESSING = True
except ImportError:
    # Fallback for testing environments
    FULL_PROCESSING = False
    yaml = None
    markdown = None
    BeautifulSoup = None


@dataclass
class AgentDependencies:
    """Dependencies for the Documentation Indexer Agent."""

    archon_mcp_available: bool = False
    project_root: str = "."
    max_file_size_mb: int = 10
    chunk_size_target: int = 1000
    chunk_overlap: int = 200
    supported_extensions: set = None

    def __post_init__(self):
        if self.supported_extensions is None:
            self.supported_extensions = {
                ".md",
                ".yaml",
                ".yml",
                ".txt",
                ".rst",
                ".adoc",
            }


class DocumentChunk(BaseModel):
    """Represents a processed document chunk."""

    chunk_id: str = Field(description="Unique identifier for the chunk")
    file_path: str = Field(description="Source file path")
    file_type: str = Field(description="Document format type")
    title: str = Field(description="Document or chunk title")
    chunk_index: int = Field(description="Position within source document")
    chunk_header: Optional[str] = Field(description="Section header for this chunk")
    content: str = Field(description="Chunk content")
    size: int = Field(description="Content size in characters")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Enhanced metadata"
    )
    cross_references: List[str] = Field(
        default_factory=list, description="References to other documents"
    )
    semantic_tags: List[str] = Field(
        default_factory=list, description="Semantic tags for categorization"
    )


class IndexingResult(BaseModel):
    """Results from documentation indexing operation."""

    files_discovered: int = Field(description="Total files discovered")
    files_processed: int = Field(description="Files successfully processed")
    files_failed: int = Field(description="Files that failed processing")
    chunks_created: int = Field(description="Total content chunks created")
    processing_time_seconds: float = Field(description="Total processing time")
    success_rate: float = Field(description="Processing success rate percentage")
    knowledge_categories: List[str] = Field(
        default_factory=list, description="Identified knowledge categories"
    )
    error_summary: List[str] = Field(
        default_factory=list, description="Summary of processing errors"
    )


class DocumentationIndexerRequest(BaseModel):
    """Request for documentation indexing."""

    target_path: str = Field(description="Root path to index documentation")
    include_patterns: List[str] = Field(
        default_factory=list, description="File patterns to include"
    )
    exclude_patterns: List[str] = Field(
        default_factory=list, description="File patterns to exclude"
    )
    processing_mode: str = Field(
        default="comprehensive",
        description="Processing mode: basic, comprehensive, or semantic",
    )
    enable_cross_references: bool = Field(
        default=True, description="Enable cross-reference extraction"
    )
    archon_integration: bool = Field(
        default=True, description="Enable Archon MCP integration"
    )


# Initialize the Documentation Indexer Agent
agent = Agent(
    model="gpt-4o",  # Can be overridden for testing
    system_prompt="""You are the Documentation Indexer Agent, a specialist in discovering, processing,
    and indexing documentation across diverse project structures for enhanced RAG knowledge systems.

    Your core responsibilities:
    1. Discover documentation files across various formats (Markdown, YAML, text, etc.)
    2. Process content with format-specific handling and intelligent chunking
    3. Extract comprehensive metadata and semantic relationships
    4. Build optimized indexes for RAG retrieval systems
    5. Integrate with Archon MCP for enhanced knowledge management

    Always prioritize:
    - Comprehensive discovery across supported formats
    - Semantic coherence in content chunking
    - Rich metadata extraction for enhanced search
    - Error handling and graceful degradation
    - Progress tracking and detailed reporting

    Respond with structured results that can be used for validation and optimization.""",
    deps_type=AgentDependencies,
    result_type=IndexingResult,
)


class DocumentationProcessor:
    """Core documentation processing functionality."""

    def __init__(self, deps: AgentDependencies):
        self.deps = deps
        self.supported_extensions = deps.supported_extensions
        self.max_file_size = deps.max_file_size_mb * 1024 * 1024

    async def discover_documentation_files(
        self,
        root_path: str,
        include_patterns: List[str] = None,
        exclude_patterns: List[str] = None,
    ) -> List[Path]:
        """Discover all documentation files in the specified path."""
        root = Path(root_path)
        if not root.exists():
            raise ValueError(f"Root path does not exist: {root_path}")

        documentation_files = []

        # Default exclude patterns
        default_excludes = {
            "node_modules",
            ".git",
            "__pycache__",
            "venv",
            "env",
            ".venv",
            ".pytest_cache",
            "coverage",
            "dist",
            "build",
            ".next",
            ".nuxt",
        }

        exclude_set = set(exclude_patterns or []) | default_excludes
        include_set = set(include_patterns or [])

        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue

            # Check if file should be excluded
            if any(pattern in str(file_path) for pattern in exclude_set):
                continue

            # Check file extension
            if file_path.suffix.lower() not in self.supported_extensions:
                continue

            # Check file size
            if file_path.stat().st_size > self.max_file_size:
                continue

            # Check include patterns if specified
            if include_set and not any(
                pattern in str(file_path) for pattern in include_set
            ):
                continue

            documentation_files.append(file_path)

        return sorted(documentation_files)

    async def process_documentation_file(
        self, file_path: Path
    ) -> Optional[Dict[str, Any]]:
        """Process individual documentation file with format-specific handling."""
        try:
            content = file_path.read_text(encoding="utf-8")

            # Format-specific processing
            if file_path.suffix.lower() == ".md":
                return await self.process_markdown_file(file_path, content)
            elif file_path.suffix.lower() in {".yaml", ".yml"}:
                return await self.process_yaml_file(file_path, content)
            elif file_path.suffix.lower() == ".txt":
                return await self.process_text_file(file_path, content)
            elif file_path.suffix.lower() == ".rst":
                return await self.process_rst_file(file_path, content)
            elif file_path.suffix.lower() == ".adoc":
                return await self.process_asciidoc_file(file_path, content)

        except UnicodeDecodeError:
            # Try with different encoding
            try:
                content = file_path.read_text(encoding="latin-1")
                return await self.process_text_file(file_path, content)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                return None
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return None

    async def process_markdown_file(
        self, file_path: Path, content: str
    ) -> Dict[str, Any]:
        """Process Markdown files with enhanced metadata extraction."""
        # Extract frontmatter if present
        frontmatter = {}
        processed_content = content

        if content.startswith("---"):
            try:
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    if FULL_PROCESSING and yaml:
                        frontmatter = yaml.safe_load(parts[1])
                    else:
                        # Basic frontmatter parsing without yaml
                        frontmatter = self._parse_simple_yaml(parts[1])
                    processed_content = parts[2].strip()
            except Exception:
                pass

        # Extract headers for structure
        headers = self._extract_headers(processed_content)

        # Extract cross-references
        cross_references = self._extract_cross_references(processed_content)

        return {
            "file_path": str(file_path),
            "file_type": "markdown",
            "content": processed_content,
            "title": (
                frontmatter.get("name")
                or frontmatter.get("title")
                or headers[0]["text"]
                if headers
                else file_path.stem
            ),
            "description": frontmatter.get("description", ""),
            "headers": headers,
            "metadata": frontmatter,
            "cross_references": cross_references,
            "semantic_tags": self._extract_semantic_tags(processed_content, "markdown"),
            "size": len(processed_content),
            "modified": file_path.stat().st_mtime,
        }

    async def process_yaml_file(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Process YAML files (agent specs, configs) with structure awareness."""
        try:
            if FULL_PROCESSING and yaml:
                yaml_data = yaml.safe_load(content)
            else:
                yaml_data = self._parse_simple_yaml(content)

            title = yaml_data.get("name") or yaml_data.get("title", file_path.stem)
            description = yaml_data.get("description", "")

            return {
                "file_path": str(file_path),
                "file_type": "yaml",
                "content": content,
                "title": title,
                "description": description,
                "structured_data": yaml_data,
                "metadata": {
                    "agent_type": yaml_data.get("task_agent_type"),
                    "color": yaml_data.get("color"),
                    "version": yaml_data.get("version"),
                },
                "cross_references": self._extract_cross_references(content),
                "semantic_tags": self._extract_semantic_tags(str(yaml_data), "yaml"),
                "size": len(content),
                "modified": file_path.stat().st_mtime,
            }
        except Exception:
            # Treat as plain text if YAML parsing fails
            return await self.process_text_file(file_path, content)

    async def process_text_file(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Process plain text files."""
        lines = content.split("\n")
        title = lines[0].strip() if lines else file_path.stem

        return {
            "file_path": str(file_path),
            "file_type": "text",
            "content": content,
            "title": title,
            "description": lines[1].strip() if len(lines) > 1 else "",
            "metadata": {},
            "cross_references": self._extract_cross_references(content),
            "semantic_tags": self._extract_semantic_tags(content, "text"),
            "size": len(content),
            "modified": file_path.stat().st_mtime,
        }

    async def process_rst_file(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Process reStructuredText files."""
        # Basic RST processing (without full RST parser)
        headers = self._extract_rst_headers(content)

        return {
            "file_path": str(file_path),
            "file_type": "rst",
            "content": content,
            "title": headers[0]["text"] if headers else file_path.stem,
            "description": "",
            "headers": headers,
            "metadata": {},
            "cross_references": self._extract_cross_references(content),
            "semantic_tags": self._extract_semantic_tags(content, "rst"),
            "size": len(content),
            "modified": file_path.stat().st_mtime,
        }

    async def process_asciidoc_file(
        self, file_path: Path, content: str
    ) -> Dict[str, Any]:
        """Process AsciiDoc files."""
        # Basic AsciiDoc processing
        headers = self._extract_asciidoc_headers(content)

        return {
            "file_path": str(file_path),
            "file_type": "asciidoc",
            "content": content,
            "title": headers[0]["text"] if headers else file_path.stem,
            "description": "",
            "headers": headers,
            "metadata": {},
            "cross_references": self._extract_cross_references(content),
            "semantic_tags": self._extract_semantic_tags(content, "asciidoc"),
            "size": len(content),
            "modified": file_path.stat().st_mtime,
        }

    def _extract_headers(self, content: str) -> List[Dict[str, Any]]:
        """Extract headers from Markdown content."""
        headers = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                text = line.lstrip("# ").strip()
                if text:
                    headers.append(
                        {
                            "level": level,
                            "text": text,
                            "id": self._generate_header_id(text),
                        }
                    )
        return headers

    def _extract_rst_headers(self, content: str) -> List[Dict[str, Any]]:
        """Extract headers from reStructuredText content."""
        headers = []
        lines = content.split("\n")

        for i, line in enumerate(lines):
            if i > 0 and i < len(lines) - 1:
                # Check for underlined headers
                if lines[i + 1] and all(c in '=-~`#"^+*' for c in lines[i + 1].strip()):
                    if (
                        len(lines[i + 1].strip()) >= len(line.strip()) * 0.8
                    ):  # Reasonable underline length
                        headers.append(
                            {
                                "level": self._get_rst_header_level(
                                    lines[i + 1].strip()[0]
                                ),
                                "text": line.strip(),
                                "id": self._generate_header_id(line.strip()),
                            }
                        )

        return headers

    def _extract_asciidoc_headers(self, content: str) -> List[Dict[str, Any]]:
        """Extract headers from AsciiDoc content."""
        headers = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("="):
                level = len(line) - len(line.lstrip("="))
                text = line.lstrip("= ").strip()
                if text:
                    headers.append(
                        {
                            "level": level,
                            "text": text,
                            "id": self._generate_header_id(text),
                        }
                    )
        return headers

    def _extract_cross_references(self, content: str) -> List[str]:
        """Extract cross-references to other documents."""
        references = []

        # Markdown links: [text](file.md) or [text](file.md#section)
        md_links = re.findall(
            r"\[([^\]]+)\]\(([^)]+\.(?:md|yaml|yml|txt|rst|adoc)(?:#[^)]*)?)\)", content
        )
        references.extend([link[1] for link in md_links])

        # Direct file references: file.md, ../docs/file.yaml
        file_refs = re.findall(
            r"[\w./]+\.(?:md|yaml|yml|txt|rst|adoc)(?:#[\w-]+)?", content
        )
        references.extend(file_refs)

        # Remove duplicates and filter out current file references
        return list(
            set([ref for ref in references if ref and not ref.startswith("http")])
        )

    def _extract_semantic_tags(self, content: str, file_type: str) -> List[str]:
        """Extract semantic tags based on content analysis."""
        tags = []
        content_lower = content.lower()

        # Technical domain tags
        if any(
            term in content_lower for term in ["api", "endpoint", "rest", "graphql"]
        ):
            tags.append("api")
        if any(term in content_lower for term in ["docker", "container", "kubernetes"]):
            tags.append("infrastructure")
        if any(term in content_lower for term in ["test", "testing", "pytest", "jest"]):
            tags.append("testing")
        if any(
            term in content_lower for term in ["config", "configuration", "settings"]
        ):
            tags.append("configuration")
        if any(
            term in content_lower for term in ["setup", "install", "getting started"]
        ):
            tags.append("setup")
        if any(term in content_lower for term in ["architecture", "design", "system"]):
            tags.append("architecture")

        # File type specific tags
        if file_type == "yaml" and "agent" in content_lower:
            tags.append("agent-specification")

        return tags

    def _generate_header_id(self, text: str) -> str:
        """Generate a URL-friendly ID from header text."""
        return re.sub(r"[^a-zA-Z0-9-]", "-", text.lower()).strip("-")

    def _get_rst_header_level(self, char: str) -> int:
        """Get header level for reStructuredText."""
        level_map = {
            "=": 1,
            "-": 2,
            "~": 3,
            "`": 4,
            "#": 5,
            '"': 6,
            "^": 7,
            "+": 8,
            "*": 9,
        }
        return level_map.get(char, 1)

    def _parse_simple_yaml(self, yaml_content: str) -> Dict[str, Any]:
        """Simple YAML parsing fallback when yaml library not available."""
        result = {}
        for line in yaml_content.split("\n"):
            line = line.strip()
            if ":" in line and not line.startswith("#"):
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip().strip("\"'")
                result[key] = value
        return result

    async def apply_intelligent_chunking(
        self, content_list: List[Dict[str, Any]]
    ) -> List[DocumentChunk]:
        """Apply intelligent chunking with semantic boundary preservation."""
        chunked_content = []

        for content_item in content_list:
            if content_item["file_type"] == "markdown":
                chunks = await self.chunk_markdown_content(content_item)
            elif content_item["file_type"] == "yaml":
                chunks = await self.chunk_yaml_content(content_item)
            else:
                chunks = await self.chunk_text_content(content_item)

            chunked_content.extend(chunks)

        return chunked_content

    async def chunk_markdown_content(
        self, content_item: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """Chunk Markdown content using header boundaries."""
        content = content_item["content"]
        headers = content_item.get("headers", [])
        chunks = []

        if not headers:
            # No headers, use paragraph-based chunking
            return await self.chunk_by_paragraphs(content_item)

        # Use headers as chunk boundaries
        lines = content.split("\n")
        current_chunk = []
        current_header = None
        chunk_index = 0

        for line in lines:
            if line.strip().startswith("#"):
                # Found header, save current chunk if it exists
                if current_chunk:
                    chunk_content = "\n".join(current_chunk)
                    if len(chunk_content.strip()) > 50:  # Minimum chunk size
                        chunks.append(
                            self._create_chunk(
                                content_item, chunk_content, current_header, chunk_index
                            )
                        )
                        chunk_index += 1

                current_chunk = [line]
                current_header = line.strip()
            else:
                current_chunk.append(line)

        # Add final chunk
        if current_chunk:
            chunk_content = "\n".join(current_chunk)
            if len(chunk_content.strip()) > 50:
                chunks.append(
                    self._create_chunk(
                        content_item, chunk_content, current_header, chunk_index
                    )
                )

        # Update total chunks in metadata
        for chunk in chunks:
            chunk.metadata["total_chunks"] = len(chunks)

        return chunks

    async def chunk_yaml_content(
        self, content_item: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """Chunk YAML content by logical sections."""
        content = content_item["content"]

        # For YAML files, typically treat as single chunk unless very large
        if len(content) <= self.deps.chunk_size_target * 2:
            return [self._create_chunk(content_item, content, content_item["title"], 0)]

        # For large YAML files, split by major sections
        return await self.chunk_by_sections(content_item, content)

    async def chunk_text_content(
        self, content_item: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """Chunk text content by paragraphs."""
        return await self.chunk_by_paragraphs(content_item)

    async def chunk_by_paragraphs(
        self, content_item: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """Chunk content by paragraph boundaries."""
        content = content_item["content"]
        paragraphs = re.split(r"\n\s*\n", content)

        chunks = []
        current_chunk = []
        current_size = 0
        chunk_index = 0

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            # Check if adding this paragraph would exceed chunk size
            if (
                current_size + len(paragraph) > self.deps.chunk_size_target
                and current_chunk
            ):
                # Save current chunk
                chunk_content = "\n\n".join(current_chunk)
                chunks.append(
                    self._create_chunk(
                        content_item,
                        chunk_content,
                        f"Section {chunk_index + 1}",
                        chunk_index,
                    )
                )
                chunk_index += 1
                current_chunk = [paragraph]
                current_size = len(paragraph)
            else:
                current_chunk.append(paragraph)
                current_size += len(paragraph) + 2  # +2 for paragraph separator

        # Add final chunk
        if current_chunk:
            chunk_content = "\n\n".join(current_chunk)
            chunks.append(
                self._create_chunk(
                    content_item,
                    chunk_content,
                    f"Section {chunk_index + 1}",
                    chunk_index,
                )
            )

        # Update total chunks in metadata
        for chunk in chunks:
            chunk.metadata["total_chunks"] = len(chunks)

        return chunks

    async def chunk_by_sections(
        self, content_item: Dict[str, Any], content: str
    ) -> List[DocumentChunk]:
        """Chunk content by logical sections."""
        # Simple section-based chunking
        sections = content.split("\n---\n")  # Common section separator

        chunks = []
        for i, section in enumerate(sections):
            if section.strip():
                chunks.append(
                    self._create_chunk(
                        content_item, section.strip(), f"Section {i + 1}", i
                    )
                )

        if not chunks:  # Fallback to paragraph chunking
            return await self.chunk_by_paragraphs(content_item)

        return chunks

    def _create_chunk(
        self,
        content_item: Dict[str, Any],
        chunk_content: str,
        header: Optional[str],
        chunk_index: int,
    ) -> DocumentChunk:
        """Create standardized chunk structure."""
        chunk_id = self._generate_chunk_id(content_item["file_path"], chunk_index)

        return DocumentChunk(
            chunk_id=chunk_id,
            file_path=content_item["file_path"],
            file_type=content_item["file_type"],
            title=content_item["title"],
            chunk_index=chunk_index,
            chunk_header=header,
            content=chunk_content,
            size=len(chunk_content),
            metadata={
                **content_item.get("metadata", {}),
                "chunk_context": header,
                "source_file_size": content_item.get("size", 0),
                "modified": content_item.get("modified"),
            },
            cross_references=content_item.get("cross_references", []),
            semantic_tags=content_item.get("semantic_tags", []),
        )

    def _generate_chunk_id(self, file_path: str, chunk_index: int) -> str:
        """Generate unique chunk ID."""
        path_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
        return f"{path_hash}_{chunk_index}"


@agent.tool
async def index_documentation(
    ctx: RunContext[AgentDependencies], request: DocumentationIndexerRequest
) -> IndexingResult:
    """
    Index documentation files in the specified path with comprehensive processing.

    Args:
        request: Documentation indexing request with configuration

    Returns:
        IndexingResult with detailed processing statistics and results
    """
    start_time = datetime.now()
    processor = DocumentationProcessor(ctx.deps)

    try:
        # Phase 1: Discover documentation files
        discovered_files = await processor.discover_documentation_files(
            request.target_path, request.include_patterns, request.exclude_patterns
        )

        # Phase 2: Process each discovered file
        processed_content = []
        failed_files = []

        for file_path in discovered_files:
            try:
                content_data = await processor.process_documentation_file(file_path)
                if content_data:
                    processed_content.append(content_data)
                else:
                    failed_files.append(str(file_path))
            except Exception as e:
                failed_files.append(f"{file_path}: {str(e)}")

        # Phase 3: Apply intelligent chunking
        if request.processing_mode in ["comprehensive", "semantic"]:
            chunked_content = await processor.apply_intelligent_chunking(
                processed_content
            )
        else:
            # Basic mode: create single chunks for each file
            chunked_content = []
            for content_item in processed_content:
                chunk = processor._create_chunk(
                    content_item, content_item["content"], content_item["title"], 0
                )
                chunked_content.append(chunk)

        # Phase 4: Extract knowledge categories
        knowledge_categories = set()
        for chunk in chunked_content:
            knowledge_categories.update(chunk.semantic_tags)

        # Calculate processing statistics
        processing_time = (datetime.now() - start_time).total_seconds()
        success_rate = (
            (len(processed_content) / len(discovered_files) * 100)
            if discovered_files
            else 0
        )

        return IndexingResult(
            files_discovered=len(discovered_files),
            files_processed=len(processed_content),
            files_failed=len(failed_files),
            chunks_created=len(chunked_content),
            processing_time_seconds=processing_time,
            success_rate=success_rate,
            knowledge_categories=sorted(list(knowledge_categories)),
            error_summary=failed_files[:10],  # Limit error list
        )

    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        return IndexingResult(
            files_discovered=0,
            files_processed=0,
            files_failed=1,
            chunks_created=0,
            processing_time_seconds=processing_time,
            success_rate=0.0,
            knowledge_categories=[],
            error_summary=[f"Critical error: {str(e)}"],
        )


@agent.tool
async def get_file_preview(
    ctx: RunContext[AgentDependencies], file_path: str, max_lines: int = 20
) -> Dict[str, Any]:
    """
    Get a preview of a documentation file for validation purposes.

    Args:
        file_path: Path to the file to preview
        max_lines: Maximum number of lines to return

    Returns:
        Dictionary with file preview information
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        if not path.is_file():
            return {"error": f"Path is not a file: {file_path}"}

        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")

        return {
            "file_path": str(path),
            "file_type": path.suffix.lower(),
            "size_bytes": path.stat().st_size,
            "total_lines": len(lines),
            "preview_lines": lines[:max_lines],
            "truncated": len(lines) > max_lines,
            "encoding": "utf-8",
        }

    except Exception as e:
        return {"error": f"Error reading file: {str(e)}"}


@agent.tool
async def validate_indexing_quality(
    ctx: RunContext[AgentDependencies], chunks: List[DocumentChunk]
) -> Dict[str, Any]:
    """
    Validate the quality of processed documentation chunks.

    Args:
        chunks: List of document chunks to validate

    Returns:
        Quality validation results and metrics
    """
    if not chunks:
        return {"error": "No chunks provided for validation"}

    # Quality metrics
    metrics = {
        "total_chunks": len(chunks),
        "average_chunk_size": sum(chunk.size for chunk in chunks) / len(chunks),
        "size_distribution": {},
        "format_distribution": {},
        "metadata_completeness": {},
        "cross_reference_coverage": 0,
        "semantic_tag_coverage": 0,
        "quality_score": 0.0,
    }

    # Analyze chunk sizes
    size_ranges = {"small": 0, "medium": 0, "large": 0, "oversized": 0}
    for chunk in chunks:
        if chunk.size < 500:
            size_ranges["small"] += 1
        elif chunk.size < 1500:
            size_ranges["medium"] += 1
        elif chunk.size < 3000:
            size_ranges["large"] += 1
        else:
            size_ranges["oversized"] += 1

    metrics["size_distribution"] = size_ranges

    # Analyze format distribution
    format_counts = {}
    for chunk in chunks:
        format_counts[chunk.file_type] = format_counts.get(chunk.file_type, 0) + 1

    metrics["format_distribution"] = format_counts

    # Analyze metadata completeness
    chunks_with_metadata = sum(1 for chunk in chunks if chunk.metadata)
    chunks_with_cross_refs = sum(1 for chunk in chunks if chunk.cross_references)
    chunks_with_semantic_tags = sum(1 for chunk in chunks if chunk.semantic_tags)

    metrics["metadata_completeness"] = {
        "chunks_with_metadata": chunks_with_metadata,
        "metadata_percentage": (chunks_with_metadata / len(chunks)) * 100,
    }

    metrics["cross_reference_coverage"] = (chunks_with_cross_refs / len(chunks)) * 100
    metrics["semantic_tag_coverage"] = (chunks_with_semantic_tags / len(chunks)) * 100

    # Calculate overall quality score
    quality_factors = [
        metrics["metadata_completeness"]["metadata_percentage"] / 100,
        metrics["cross_reference_coverage"] / 100,
        metrics["semantic_tag_coverage"] / 100,
        1.0 if size_ranges["oversized"] == 0 else 0.8,  # Penalty for oversized chunks
        (
            1.0 if size_ranges["small"] < len(chunks) * 0.3 else 0.7
        ),  # Penalty for too many small chunks
    ]

    metrics["quality_score"] = sum(quality_factors) / len(quality_factors) * 100

    return metrics
