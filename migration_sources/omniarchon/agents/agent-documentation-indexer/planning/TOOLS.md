# Documentation Indexer Agent - Tools Specification

Tools for agent-documentation-indexer - Pydantic AI agent tools implementation.

```python
"""
Tools for Documentation Indexer Agent - Pydantic AI agent tools implementation.
"""

import logging
import asyncio
import aiofiles
import aiohttp
import json
import re
import chardet
import tiktoken
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
from pydantic_ai import RunContext
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Tool parameter models for validation
class FileDiscoveryParams(BaseModel):
    """Parameters for file discovery operations."""
    path: str = Field(..., description="Root path to search")
    include_patterns: List[str] = Field(
        default=["**/*.md", "**/*.txt", "**/*.rst", "**/*.adoc", "**/*.yaml", "**/*.yml"],
        description="File patterns to include"
    )
    exclude_patterns: List[str] = Field(
        default=["node_modules/**", ".git/**", "dist/**", "build/**", "__pycache__/**"],
        description="File patterns to exclude"
    )
    max_files: int = Field(default=1000, description="Maximum files to discover")


class ContentChunkingParams(BaseModel):
    """Parameters for content chunking operations."""
    content: str = Field(..., description="Content to chunk")
    file_type: str = Field(..., description="File type/extension")
    target_size: int = Field(default=1500, description="Target tokens per chunk")
    overlap_size: int = Field(default=200, description="Token overlap between chunks")
    preserve_structure: bool = Field(default=True, description="Preserve document structure")


class ArchonIndexingParams(BaseModel):
    """Parameters for Archon indexing operations."""
    project_id: str = Field(..., description="Target Archon project ID")
    title: str = Field(..., description="Document title")
    content: Dict[str, Any] = Field(..., description="Document content and metadata")
    document_type: str = Field(default="documentation", description="Document type")


# Standalone tool functions for testing and reuse
async def discover_documentation_files_tool(
    root_path: str,
    include_patterns: List[str],
    exclude_patterns: List[str],
    max_files: int = 1000
) -> List[Dict[str, Any]]:
    """
    Discover documentation files in a project directory.

    Args:
        root_path: Root directory to search
        include_patterns: File patterns to include
        exclude_patterns: File patterns to exclude
        max_files: Maximum number of files to return

    Returns:
        List of discovered file information
    """
    import fnmatch
    from pathlib import Path

    root = Path(root_path).resolve()
    if not root.exists():
        raise ValueError(f"Root path does not exist: {root_path}")

    discovered_files = []

    def matches_patterns(file_path: Path, patterns: List[str]) -> bool:
        """Check if file matches any of the patterns."""
        file_str = str(file_path.relative_to(root))
        return any(fnmatch.fnmatch(file_str, pattern) for pattern in patterns)

    def should_process_file(file_path: Path) -> bool:
        """Check if file should be processed."""
        if not file_path.is_file():
            return False

        # Check exclusion patterns first
        if matches_patterns(file_path, exclude_patterns):
            return False

        # Check inclusion patterns
        if not matches_patterns(file_path, include_patterns):
            return False

        # Check file size (skip very large files)
        try:
            if file_path.stat().st_size > 50 * 1024 * 1024:  # 50MB limit
                return False
        except OSError:
            return False

        return True

    # Walk directory tree
    for file_path in root.rglob('*'):
        if len(discovered_files) >= max_files:
            break

        if should_process_file(file_path):
            try:
                stat = file_path.stat()
                discovered_files.append({
                    "path": str(file_path),
                    "relative_path": str(file_path.relative_to(root)),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "extension": file_path.suffix.lower(),
                    "priority": determine_file_priority(file_path)
                })
            except Exception as e:
                logger.warning(f"Error processing file {file_path}: {e}")
                continue

    # Sort by priority and modification time
    discovered_files.sort(key=lambda x: (x['priority'], -x['modified']))

    return discovered_files


def determine_file_priority(file_path: Path) -> int:
    """Determine processing priority for a file."""
    name = file_path.name.lower()

    # High priority files
    if name in ['claude.md', 'readme.md']:
        return 0
    elif name.startswith('agent-') and name.endswith(('.yaml', '.yml', '.md')):
        return 1
    elif file_path.parent.name == 'docs':
        return 2
    else:
        return 3


async def read_file_with_encoding_detection_tool(file_path: str) -> Dict[str, Any]:
    """
    Read a file with automatic encoding detection.

    Args:
        file_path: Path to the file to read

    Returns:
        Dictionary with file content, encoding, and metadata
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # First, detect encoding
    try:
        with open(path, 'rb') as f:
            raw_data = f.read()

        # Try UTF-8 first (most common)
        try:
            content = raw_data.decode('utf-8')
            encoding = 'utf-8'
        except UnicodeDecodeError:
            # Use chardet for detection
            detected = chardet.detect(raw_data)
            encoding = detected.get('encoding', 'utf-8')
            confidence = detected.get('confidence', 0.0)

            if confidence < 0.7:
                # Fall back to latin-1 which can decode any byte sequence
                content = raw_data.decode('latin-1')
                encoding = 'latin-1'
            else:
                content = raw_data.decode(encoding)

    except Exception as e:
        raise RuntimeError(f"Failed to read file {file_path}: {e}")

    # Check if content is likely binary
    if '\x00' in content:
        raise ValueError(f"File appears to be binary: {file_path}")

    # Get file metadata
    stat = path.stat()

    return {
        "content": content,
        "encoding": encoding,
        "size": len(content),
        "lines": content.count('\n') + 1,
        "modified": stat.st_mtime,
        "file_path": str(path.absolute()),
        "extension": path.suffix.lower()
    }


def get_file_metadata_tool(file_path: str) -> Dict[str, Any]:
    """
    Get comprehensive metadata for a file.

    Args:
        file_path: Path to the file

    Returns:
        Dictionary with file metadata
    """
    import mimetypes
    from datetime import datetime

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    stat = path.stat()
    mime_type, _ = mimetypes.guess_type(str(path))

    return {
        "path": str(path.absolute()),
        "name": path.name,
        "stem": path.stem,
        "suffix": path.suffix,
        "parent": str(path.parent),
        "size": stat.st_size,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "created": stat.st_ctime,
        "modified": stat.st_mtime,
        "accessed": stat.st_atime,
        "created_iso": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified_iso": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "mime_type": mime_type,
        "is_text": mime_type and mime_type.startswith('text/'),
        "permissions": oct(stat.st_mode)[-3:]
    }


async def chunk_content_tool(
    content: str,
    file_type: str,
    target_size: int = 1500,
    overlap_size: int = 200
) -> List[Dict[str, Any]]:
    """
    Intelligently chunk content for optimal RAG performance.

    Args:
        content: Content to chunk
        file_type: File type/extension for context-aware chunking
        target_size: Target tokens per chunk
        overlap_size: Token overlap between chunks

    Returns:
        List of content chunks with metadata
    """

    # Initialize tokenizer
    try:
        encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 tokenizer
    except Exception:
        # Fallback to simple word-based estimation
        encoding = None

    def count_tokens(text: str) -> int:
        """Count tokens in text."""
        if encoding:
            return len(encoding.encode(text))
        else:
            # Rough estimation: ~4 characters per token
            return len(text) // 4

    def get_chunk_boundaries(text: str, file_ext: str) -> List[int]:
        """Find natural chunk boundaries based on file type."""
        boundaries = [0]

        if file_ext in ['.md', '.markdown']:
            # Split on headers
            for match in re.finditer(r'^(#{1,6}\s+.*?)$', text, re.MULTILINE):
                boundaries.append(match.start())
        elif file_ext in ['.rst']:
            # RestructuredText headers
            for match in re.finditer(r'^([^\n]+\n[=\-~^"#*+]+\s*$)', text, re.MULTILINE):
                boundaries.append(match.start())
        elif file_ext in ['.yaml', '.yml']:
            # Split on top-level keys
            for match in re.finditer(r'^(\w+:(?:\s|$))', text, re.MULTILINE):
                boundaries.append(match.start())
        else:
            # Generic: split on double newlines (paragraph boundaries)
            for match in re.finditer(r'\n\s*\n', text):
                boundaries.append(match.start())

        boundaries.append(len(text))
        return sorted(set(boundaries))

    # Find natural boundaries
    boundaries = get_chunk_boundaries(content, file_type)
    chunks = []

    current_chunk = ""
    current_start = 0

    for boundary in boundaries[1:]:
        segment = content[current_start:boundary]

        # Check if adding this segment would exceed target size
        potential_chunk = current_chunk + segment

        if count_tokens(potential_chunk) > target_size and current_chunk:
            # Save current chunk
            chunks.append({
                "content": current_chunk.strip(),
                "start_pos": boundaries[len(chunks)],
                "end_pos": current_start,
                "token_count": count_tokens(current_chunk),
                "chunk_index": len(chunks)
            })

            # Start new chunk with overlap
            if overlap_size > 0 and chunks:
                overlap_text = current_chunk[-overlap_size * 4:]  # Rough char estimate
                current_chunk = overlap_text + segment
            else:
                current_chunk = segment
            current_start = boundary
        else:
            current_chunk = potential_chunk

    # Add final chunk if there's content
    if current_chunk.strip():
        chunks.append({
            "content": current_chunk.strip(),
            "start_pos": current_start,
            "end_pos": len(content),
            "token_count": count_tokens(current_chunk),
            "chunk_index": len(chunks)
        })

    return chunks


def extract_metadata_from_content_tool(content: str, file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from document content.

    Args:
        content: Document content
        file_path: Path to the source file

    Returns:
        Extracted metadata dictionary
    """
    path = Path(file_path)
    metadata = {
        "title": None,
        "headings": [],
        "language": None,
        "sections": [],
        "code_blocks": [],
        "links": [],
        "word_count": len(content.split()),
        "char_count": len(content)
    }

    # Extract title
    if path.suffix.lower() in ['.md', '.markdown']:
        # Look for first heading
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            metadata["title"] = title_match.group(1).strip()

        # Extract all headings
        headings = re.findall(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE)
        metadata["headings"] = [
            {"level": len(h[0]), "text": h[1].strip()}
            for h in headings
        ]

        # Extract code blocks
        code_blocks = re.findall(r'```(\w*)\n(.*?)\n```', content, re.DOTALL)
        metadata["code_blocks"] = [
            {"language": lang or "text", "content": code.strip()}
            for lang, code in code_blocks
        ]

        # Extract links
        links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
        metadata["links"] = [
            {"text": text, "url": url}
            for text, url in links
        ]

    elif path.suffix.lower() in ['.yaml', '.yml']:
        # For YAML files, try to parse structure
        try:
            import yaml
            parsed = yaml.safe_load(content)
            if isinstance(parsed, dict):
                metadata["yaml_keys"] = list(parsed.keys())
                if "name" in parsed:
                    metadata["title"] = parsed["name"]
                elif "title" in parsed:
                    metadata["title"] = parsed["title"]
        except Exception:
            pass

    # Detect language/content type
    if "python" in content.lower() or ".py" in content:
        metadata["language"] = "python"
    elif "javascript" in content.lower() or ".js" in content:
        metadata["language"] = "javascript"
    elif "docker" in content.lower() or "dockerfile" in content.lower():
        metadata["language"] = "docker"

    return metadata


def clean_and_normalize_content_tool(content: str, file_type: str) -> str:
    """
    Clean and normalize content for indexing.

    Args:
        content: Raw content to clean
        file_type: File type/extension

    Returns:
        Cleaned and normalized content
    """

    # Remove excessive whitespace
    content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
    content = re.sub(r'[ \t]+', ' ', content)

    # File-type specific cleaning
    if file_type in ['.md', '.markdown']:
        # Clean markdown-specific artifacts
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)  # Remove HTML comments
        content = re.sub(r'\[TOC\]', '', content, flags=re.IGNORECASE)  # Remove TOC markers

    elif file_type in ['.rst']:
        # Clean reStructuredText artifacts
        content = re.sub(r'^\.\. .*$', '', content, flags=re.MULTILINE)  # Remove directives

    elif file_type in ['.yaml', '.yml']:
        # Preserve YAML structure but clean comments
        lines = []
        for line in content.split('\n'):
            # Keep inline comments but remove comment-only lines
            if line.strip() and not line.strip().startswith('#'):
                lines.append(line)
        content = '\n'.join(lines)

    # General cleaning
    content = content.strip()

    # Ensure content isn't empty after cleaning
    if not content or len(content.strip()) < 10:
        raise ValueError("Content too short after cleaning")

    return content


async def index_document_to_archon_tool(
    archon_mcp_url: str,
    project_id: str,
    title: str,
    content: Dict[str, Any],
    document_type: str = "documentation"
) -> Dict[str, Any]:
    """
    Index a document into the Archon RAG system.

    Args:
        archon_mcp_url: Archon MCP server URL
        project_id: Target project ID
        title: Document title
        content: Document content and metadata
        document_type: Type of document

    Returns:
        Indexing result information
    """

    async with aiohttp.ClientSession() as session:
        try:
            payload = {
                "project_id": project_id,
                "title": title,
                "document_type": document_type,
                "content": content
            }

            async with session.post(
                f"{archon_mcp_url}/mcp/tools/create_document",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:

                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "document_id": result.get("document_id"),
                        "project_id": project_id,
                        "title": title,
                        "indexed_at": result.get("created_at"),
                        "chunks_created": content.get("chunk_count", 1)
                    }
                else:
                    error_text = await response.text()
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {error_text}",
                        "project_id": project_id,
                        "title": title
                    }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Request timed out",
                "project_id": project_id,
                "title": title
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "project_id": project_id,
                "title": title
            }


async def verify_archon_connectivity_tool(archon_mcp_url: str) -> Dict[str, Any]:
    """
    Verify connectivity to Archon MCP server.

    Args:
        archon_mcp_url: Archon MCP server URL

    Returns:
        Connectivity status information
    """

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{archon_mcp_url}/health",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:

                if response.status == 200:
                    health_data = await response.json()
                    return {
                        "connected": True,
                        "status": "healthy",
                        "server_info": health_data,
                        "url": archon_mcp_url
                    }
                else:
                    return {
                        "connected": False,
                        "status": f"HTTP {response.status}",
                        "error": await response.text(),
                        "url": archon_mcp_url
                    }

        except asyncio.TimeoutError:
            return {
                "connected": False,
                "status": "timeout",
                "error": "Connection timed out",
                "url": archon_mcp_url
            }
        except Exception as e:
            return {
                "connected": False,
                "status": "error",
                "error": str(e),
                "url": archon_mcp_url
            }


async def get_archon_project_info_tool(
    archon_mcp_url: str,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get or detect Archon project information.

    Args:
        archon_mcp_url: Archon MCP server URL
        project_path: Optional project path for auto-detection

    Returns:
        Project information or detection results
    """

    async with aiohttp.ClientSession() as session:
        try:
            # First, list available projects
            async with session.get(
                f"{archon_mcp_url}/mcp/tools/list_projects",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:

                if response.status != 200:
                    return {
                        "success": False,
                        "error": f"Failed to list projects: HTTP {response.status}",
                        "url": archon_mcp_url
                    }

                projects = await response.json()

                # If project_path provided, try to auto-detect
                if project_path:
                    path = Path(project_path)
                    project_name = path.name

                    # Look for matching project
                    for project in projects.get("projects", []):
                        if project.get("title", "").lower() == project_name.lower():
                            return {
                                "success": True,
                                "auto_detected": True,
                                "project": project,
                                "project_id": project.get("id"),
                                "available_projects": projects.get("projects", [])
                            }

                    # No match found, suggest creating new project
                    return {
                        "success": True,
                        "auto_detected": False,
                        "suggested_name": project_name,
                        "available_projects": projects.get("projects", []),
                        "recommendation": "create_new_project"
                    }

                return {
                    "success": True,
                    "available_projects": projects.get("projects", []),
                    "total_projects": len(projects.get("projects", []))
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "url": archon_mcp_url
            }


# Tool registration functions for agent
def register_tools(agent, deps_type):
    """
    Register all tools with the agent.

    Args:
        agent: Pydantic AI agent instance
        deps_type: Agent dependencies type
    """

    @agent.tool
    async def discover_documentation_files(
        ctx: RunContext[deps_type],
        path: str,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        max_files: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Discover documentation files in a project directory.

        Args:
            path: Root directory to search for documentation
            include_patterns: File patterns to include (default from config)
            exclude_patterns: File patterns to exclude (default from config)
            max_files: Maximum number of files to return

        Returns:
            List of discovered documentation files with metadata
        """
        try:
            # Use config defaults if not provided
            include = include_patterns or ctx.deps.indexer_config.include_patterns
            exclude = exclude_patterns or ctx.deps.indexer_config.exclude_patterns

            files = await discover_documentation_files_tool(
                root_path=path,
                include_patterns=include,
                exclude_patterns=exclude,
                max_files=max_files
            )

            logger.info(f"Discovered {len(files)} documentation files in {path}")
            return files

        except Exception as e:
            logger.error(f"File discovery failed: {e}")
            return {"error": str(e), "files": []}

    @agent.tool
    async def read_file_with_encoding_detection(
        ctx: RunContext[deps_type],
        file_path: str
    ) -> Dict[str, Any]:
        """
        Read a file with automatic encoding detection and validation.

        Args:
            file_path: Path to the file to read

        Returns:
            Dictionary with file content, encoding, and metadata
        """
        try:
            async with ctx.deps.file_semaphore:
                result = await read_file_with_encoding_detection_tool(file_path)
                logger.debug(f"Read file: {file_path} ({result['encoding']}, {result['size']} chars)")
                return result
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return {"error": str(e), "file_path": file_path}

    @agent.tool
    def get_file_metadata(
        ctx: RunContext[deps_type],
        file_path: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive metadata for a file.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with detailed file metadata
        """
        try:
            metadata = get_file_metadata_tool(file_path)
            logger.debug(f"Retrieved metadata for: {file_path}")
            return metadata
        except Exception as e:
            logger.error(f"Failed to get metadata for {file_path}: {e}")
            return {"error": str(e), "file_path": file_path}

    @agent.tool
    async def chunk_content(
        ctx: RunContext[deps_type],
        content: str,
        file_type: str,
        target_size: Optional[int] = None,
        overlap_size: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Intelligently chunk content for optimal RAG performance.

        Args:
            content: Content to chunk
            file_type: File type/extension for context-aware chunking
            target_size: Target tokens per chunk (default from config)
            overlap_size: Token overlap between chunks (default from config)

        Returns:
            List of content chunks with metadata
        """
        try:
            # Use config defaults if not provided
            target = target_size or ctx.deps.indexer_config.chunk_size
            overlap = overlap_size or ctx.deps.indexer_config.chunk_overlap

            chunks = await chunk_content_tool(
                content=content,
                file_type=file_type,
                target_size=target,
                overlap_size=overlap
            )

            logger.info(f"Created {len(chunks)} chunks from content ({len(content)} chars)")
            return chunks

        except Exception as e:
            logger.error(f"Content chunking failed: {e}")
            return {"error": str(e), "chunks": []}

    @agent.tool
    def extract_metadata_from_content(
        ctx: RunContext[deps_type],
        content: str,
        file_path: str
    ) -> Dict[str, Any]:
        """
        Extract metadata from document content.

        Args:
            content: Document content to analyze
            file_path: Path to the source file for context

        Returns:
            Extracted metadata dictionary
        """
        try:
            metadata = extract_metadata_from_content_tool(content, file_path)
            logger.debug(f"Extracted metadata from: {file_path}")
            return metadata
        except Exception as e:
            logger.error(f"Metadata extraction failed for {file_path}: {e}")
            return {"error": str(e), "file_path": file_path}

    @agent.tool
    def clean_and_normalize_content(
        ctx: RunContext[deps_type],
        content: str,
        file_type: str
    ) -> str:
        """
        Clean and normalize content for indexing.

        Args:
            content: Raw content to clean
            file_type: File type/extension for context-specific cleaning

        Returns:
            Cleaned and normalized content string
        """
        try:
            cleaned = clean_and_normalize_content_tool(content, file_type)
            logger.debug(f"Cleaned content ({len(content)} -> {len(cleaned)} chars)")
            return cleaned
        except Exception as e:
            logger.error(f"Content cleaning failed: {e}")
            return content  # Return original if cleaning fails

    @agent.tool
    async def index_document_to_archon(
        ctx: RunContext[deps_type],
        project_id: str,
        title: str,
        content: Dict[str, Any],
        document_type: str = "documentation"
    ) -> Dict[str, Any]:
        """
        Index a document into the Archon RAG system.

        Args:
            project_id: Target Archon project ID
            title: Document title for indexing
            content: Document content and metadata
            document_type: Type of document (default: documentation)

        Returns:
            Indexing result with success status and details
        """
        try:
            result = await index_document_to_archon_tool(
                archon_mcp_url=ctx.deps.archon_mcp_url,
                project_id=project_id,
                title=title,
                content=content,
                document_type=document_type
            )

            if result.get("success"):
                ctx.deps.total_chunks_created += result.get("chunks_created", 1)
                logger.info(f"Successfully indexed: {title} -> {project_id}")
            else:
                logger.error(f"Failed to index {title}: {result.get('error')}")

            return result

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Indexing error for {title}: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "project_id": project_id,
                "title": title
            }

    @agent.tool
    async def verify_archon_connectivity(
        ctx: RunContext[deps_type]
    ) -> Dict[str, Any]:
        """
        Verify connectivity to the Archon MCP server.

        Returns:
            Connectivity status and server information
        """
        try:
            result = await verify_archon_connectivity_tool(ctx.deps.archon_mcp_url)

            if result.get("connected"):
                logger.info(f"Archon MCP server is accessible: {ctx.deps.archon_mcp_url}")
            else:
                logger.warning(f"Archon MCP server connectivity issue: {result.get('error')}")

            return result

        except Exception as e:
            logger.error(f"Connectivity check failed: {e}")
            return {
                "connected": False,
                "error": str(e),
                "url": ctx.deps.archon_mcp_url
            }

    @agent.tool
    async def get_archon_project_info(
        ctx: RunContext[deps_type],
        project_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get or detect Archon project information.

        Args:
            project_path: Optional project path for auto-detection

        Returns:
            Project information or auto-detection results
        """
        try:
            result = await get_archon_project_info_tool(
                archon_mcp_url=ctx.deps.archon_mcp_url,
                project_path=project_path or str(ctx.deps.project_root) if ctx.deps.project_root else None
            )

            if result.get("success"):
                if result.get("auto_detected"):
                    ctx.deps.target_project_id = result.get("project_id")
                    logger.info(f"Auto-detected project: {result.get('project', {}).get('title')}")
                else:
                    logger.info(f"Found {result.get('total_projects', 0)} available projects")

            return result

        except Exception as e:
            logger.error(f"Project info retrieval failed: {e}")
            return {"success": False, "error": str(e)}

    @agent.tool
    def track_indexing_progress(
        ctx: RunContext[deps_type],
        total_files: int,
        processed_files: int,
        errors: int
    ) -> Dict[str, Any]:
        """
        Track and report indexing progress.

        Args:
            total_files: Total number of files to process
            processed_files: Number of files processed so far
            errors: Number of errors encountered

        Returns:
            Progress report with statistics
        """
        try:
            progress_pct = (processed_files / total_files * 100) if total_files > 0 else 0

            report = {
                "total_files": total_files,
                "processed_files": processed_files,
                "remaining_files": total_files - processed_files,
                "error_count": errors,
                "success_rate": ((processed_files - errors) / processed_files * 100) if processed_files > 0 else 0,
                "progress_percentage": round(progress_pct, 1),
                "chunks_created": ctx.deps.total_chunks_created,
                "status": "in_progress" if processed_files < total_files else "completed"
            }

            logger.info(f"Indexing progress: {processed_files}/{total_files} files ({progress_pct:.1f}%)")
            return report

        except Exception as e:
            logger.error(f"Progress tracking error: {e}")
            return {
                "error": str(e),
                "total_files": total_files,
                "processed_files": processed_files
            }

    @agent.tool
    def handle_indexing_error(
        ctx: RunContext[deps_type],
        error: str,
        file_path: str,
        context: str
    ) -> Dict[str, Any]:
        """
        Handle and log indexing errors with recovery suggestions.

        Args:
            error: Error message or exception
            file_path: Path to the file that caused the error
            context: Context where the error occurred

        Returns:
            Error handling result with recovery suggestions
        """
        try:
            # Record the error
            ctx.deps.failed_files[file_path] = f"{context}: {error}"

            # Determine error type and recovery suggestion
            error_lower = error.lower()
            recovery_suggestion = "retry"

            if "encoding" in error_lower or "decode" in error_lower:
                recovery_suggestion = "encoding_detection"
            elif "timeout" in error_lower:
                recovery_suggestion = "retry_with_delay"
            elif "size" in error_lower or "memory" in error_lower:
                recovery_suggestion = "skip_large_file"
            elif "permission" in error_lower:
                recovery_suggestion = "check_permissions"
            elif "not found" in error_lower:
                recovery_suggestion = "skip_missing_file"

            result = {
                "error_recorded": True,
                "file_path": file_path,
                "error_message": error,
                "context": context,
                "recovery_suggestion": recovery_suggestion,
                "total_errors": len(ctx.deps.failed_files)
            }

            logger.error(f"Indexing error in {context} for {file_path}: {error}")
            return result

        except Exception as e:
            logger.error(f"Error handler failed: {e}")
            return {
                "error_recorded": False,
                "handler_error": str(e),
                "file_path": file_path
            }

    logger.info(f"Registered {len([name for name in dir() if not name.startswith('_')])} tools with documentation indexer agent")


# Error handling utilities
class IndexingError(Exception):
    """Custom exception for indexing failures."""
    pass


async def handle_tool_error(error: Exception, context: str) -> Dict[str, Any]:
    """
    Standardized error handling for tools.

    Args:
        error: The exception that occurred
        context: Description of what was being attempted

    Returns:
        Error response dictionary
    """
    logger.error(f"Tool error in {context}: {error}")
    return {
        "success": False,
        "error": str(error),
        "error_type": type(error).__name__,
        "context": context,
        "recovery_actions": [
            "check_file_permissions",
            "verify_archon_connectivity",
            "validate_file_paths",
            "retry_with_smaller_batch"
        ]
    }


# Batch processing utilities
async def process_files_in_batches(
    file_list: List[str],
    batch_size: int,
    processor_func,
    semaphore: Optional[asyncio.Semaphore] = None
):
    """
    Process files in controlled batches with concurrency limits.

    Args:
        file_list: List of file paths to process
        batch_size: Number of files per batch
        processor_func: Async function to process each file
        semaphore: Optional semaphore for concurrency control

    Returns:
        Generator yielding batch results
    """
    sem = semaphore or asyncio.Semaphore(5)

    for i in range(0, len(file_list), batch_size):
        batch = file_list[i:i + batch_size]

        async def process_file(file_path):
            async with sem:
                return await processor_func(file_path)

        batch_tasks = [process_file(fp) for fp in batch]
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        yield batch, batch_results


# Testing utilities
def create_test_tools():
    """Create mock tools for testing."""
    from pydantic_ai.models.test import TestModel

    test_model = TestModel()

    async def mock_discover_files(path: str) -> List[Dict]:
        return [
            {"path": f"{path}/README.md", "priority": 0},
            {"path": f"{path}/docs/guide.md", "priority": 2}
        ]

    async def mock_read_file(file_path: str) -> Dict:
        return {
            "content": f"Mock content for {file_path}",
            "encoding": "utf-8",
            "size": 100
        }

    async def mock_index_document(project_id: str, title: str, content: Dict) -> Dict:
        return {
            "success": True,
            "document_id": "mock-doc-123",
            "project_id": project_id,
            "title": title
        }

    return {
        "discover_files": mock_discover_files,
        "read_file": mock_read_file,
        "index_document": mock_index_document
    }
```

## Integration Notes

### File Discovery Strategy
- Uses glob patterns with priority-based sorting
- Automatically excludes common build/cache directories
- Handles file size limits and binary file detection
- Supports incremental processing by tracking modification times

### Content Processing Pipeline
- Automatic encoding detection with fallbacks (UTF-8 → chardet → latin-1)
- Context-aware chunking based on file type (Markdown headers, YAML sections, etc.)
- Intelligent token counting using tiktoken for precise chunk sizing
- Preserves document structure and metadata throughout processing

### Archon MCP Integration
- Direct HTTP API calls to Archon MCP server endpoints
- Batch processing support for efficient indexing operations
- Comprehensive error handling with retry logic and exponential backoff
- Progress tracking and reporting for large documentation sets

### Error Handling & Recovery
- Graceful handling of encoding issues, large files, and network errors
- Detailed error logging with context and recovery suggestions
- Partial success support (continue processing despite individual file failures)
- Resource cleanup and connection management

### Performance Optimizations
- Async file operations with configurable concurrency limits
- Semaphore-controlled parallel processing to prevent resource exhaustion
- Memory-efficient streaming for large files
- Batch operations to minimize network overhead

This tool specification provides comprehensive functionality for discovering, processing, and indexing documentation files into the Archon RAG intelligence system, with robust error handling and performance optimization throughout the pipeline.
