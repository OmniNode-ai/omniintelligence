"""
Dependencies and configuration for the Documentation Indexer Agent.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Set


@dataclass
class AgentDependencies:
    """
    Dependencies and configuration for the Documentation Indexer Agent.

    This class provides all the configuration and external dependencies
    needed for the agent to function properly.
    """

    # Core Configuration
    project_root: str = "."
    archon_mcp_available: bool = False

    # File Processing Configuration
    max_file_size_mb: int = 10
    supported_extensions: Optional[Set[str]] = None

    # Chunking Configuration
    chunk_size_target: int = 1000
    chunk_overlap: int = 200
    min_chunk_size: int = 50
    max_chunk_size: int = 3000

    # Processing Configuration
    parallel_processing: bool = True
    max_workers: int = 4
    encoding_fallbacks: tuple = ("utf-8", "latin-1", "cp1252")

    # Quality Configuration
    min_metadata_completeness: float = 0.7
    min_cross_reference_ratio: float = 0.3
    min_semantic_tag_ratio: float = 0.5

    # Archon Integration Configuration
    archon_project_id: Optional[str] = None
    archon_base_url: str = "http://localhost:8051"
    archon_timeout: int = 30

    # Error Handling Configuration
    max_retry_attempts: int = 3
    continue_on_error: bool = True
    log_processing_errors: bool = True

    def __post_init__(self):
        """Initialize default values and validate configuration."""
        if self.supported_extensions is None:
            self.supported_extensions = {
                ".md",  # Markdown
                ".yaml",  # YAML configuration
                ".yml",  # YAML configuration (alternate)
                ".txt",  # Plain text
                ".rst",  # reStructuredText
                ".adoc",  # AsciiDoc
            }

        # Validate chunk size configuration
        if self.chunk_size_target < self.min_chunk_size:
            raise ValueError(
                f"chunk_size_target ({self.chunk_size_target}) must be >= min_chunk_size ({self.min_chunk_size})"
            )

        if self.chunk_size_target > self.max_chunk_size:
            raise ValueError(
                f"chunk_size_target ({self.chunk_size_target}) must be <= max_chunk_size ({self.max_chunk_size})"
            )

        # Validate quality thresholds
        for attr in [
            "min_metadata_completeness",
            "min_cross_reference_ratio",
            "min_semantic_tag_ratio",
        ]:
            value = getattr(self, attr)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{attr} ({value}) must be between 0.0 and 1.0")

        # Ensure project root is a Path object internally
        self._project_root_path = Path(self.project_root)

    @property
    def project_root_path(self) -> Path:
        """Get project root as a Path object."""
        return self._project_root_path

    def get_exclude_patterns(self) -> Set[str]:
        """Get default exclude patterns for file discovery."""
        return {
            # Version control
            ".git",
            ".svn",
            ".hg",
            ".bzr",
            # Dependencies and packages
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            "venv",
            "env",
            ".venv",
            ".env",
            "vendor",
            "deps",
            # Build outputs
            "dist",
            "build",
            "target",
            "out",
            "bin",
            ".next",
            ".nuxt",
            ".output",
            # IDE and editor files
            ".vscode",
            ".idea",
            ".vs",
            "*.swp",
            "*.swo",
            "*~",
            # Coverage and testing
            "coverage",
            "htmlcov",
            ".coverage",
            ".tox",
            ".nox",
            # Logs and temporary files
            "logs",
            "*.log",
            "tmp",
            "temp",
            # OS specific
            ".DS_Store",
            "Thumbs.db",
        }

    def get_include_patterns(self) -> Set[str]:
        """Get default include patterns for file discovery."""
        return {
            # Documentation directories
            "docs",
            "documentation",
            "doc",
            "README*",
            "readme*",
            # Agent specifications
            "agents",
            "agent-*",
            # Configuration files
            "config",
            "configs",
            "conf",
            # Project root files
            "CHANGELOG*",
            "LICENSE*",
            "CONTRIBUTING*",
        }

    def is_supported_file(self, file_path: Path) -> bool:
        """Check if a file is supported for processing."""
        return (
            file_path.suffix.lower() in self.supported_extensions
            and file_path.stat().st_size <= self.max_file_size_mb * 1024 * 1024
        )

    def should_exclude_path(self, file_path: Path) -> bool:
        """Check if a path should be excluded from processing."""
        exclude_patterns = self.get_exclude_patterns()
        path_str = str(file_path)

        return any(pattern in path_str for pattern in exclude_patterns)

    def get_chunking_config(self) -> Dict[str, Any]:
        """Get chunking configuration as a dictionary."""
        return {
            "target_size": self.chunk_size_target,
            "overlap": self.chunk_overlap,
            "min_size": self.min_chunk_size,
            "max_size": self.max_chunk_size,
        }

    def get_quality_thresholds(self) -> Dict[str, float]:
        """Get quality thresholds as a dictionary."""
        return {
            "metadata_completeness": self.min_metadata_completeness,
            "cross_reference_ratio": self.min_cross_reference_ratio,
            "semantic_tag_ratio": self.min_semantic_tag_ratio,
        }

    def get_archon_config(self) -> Dict[str, Any]:
        """Get Archon integration configuration."""
        return {
            "available": self.archon_mcp_available,
            "project_id": self.archon_project_id,
            "base_url": self.archon_base_url,
            "timeout": self.archon_timeout,
        }

    def validate_dependencies(self) -> Dict[str, bool]:
        """Validate that all dependencies are available."""
        validation_results = {
            "project_root_exists": self.project_root_path.exists(),
            "project_root_readable": self.project_root_path.is_dir(),
            "archon_configured": self.archon_mcp_available
            and self.archon_project_id is not None,
        }

        # Check optional dependencies
        try:
            import yaml

            validation_results["yaml_available"] = True
        except ImportError:
            validation_results["yaml_available"] = False

        try:
            import markdown

            validation_results["markdown_available"] = True
        except ImportError:
            validation_results["markdown_available"] = False

        try:
            from bs4 import BeautifulSoup

            validation_results["beautifulsoup_available"] = True
        except ImportError:
            validation_results["beautifulsoup_available"] = False

        return validation_results

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics configuration."""
        return {
            "parallel_processing": self.parallel_processing,
            "max_workers": self.max_workers,
            "max_retry_attempts": self.max_retry_attempts,
            "continue_on_error": self.continue_on_error,
            "log_errors": self.log_processing_errors,
        }


# Factory function for creating dependencies with common configurations
def create_test_dependencies(**overrides) -> AgentDependencies:
    """
    Create AgentDependencies instance with test-friendly defaults.

    Args:
        **overrides: Any configuration values to override

    Returns:
        AgentDependencies instance configured for testing
    """
    defaults = {
        "project_root": ".",
        "max_file_size_mb": 1,  # Smaller for testing
        "chunk_size_target": 500,  # Smaller chunks for testing
        "chunk_overlap": 50,
        "max_workers": 2,  # Fewer workers for testing
        "continue_on_error": True,
        "log_processing_errors": True,
    }

    # Merge overrides with defaults
    config = {**defaults, **overrides}

    return AgentDependencies(**config)


def create_production_dependencies(**overrides) -> AgentDependencies:
    """
    Create AgentDependencies instance with production-ready defaults.

    Args:
        **overrides: Any configuration values to override

    Returns:
        AgentDependencies instance configured for production
    """
    defaults = {
        "max_file_size_mb": 10,
        "chunk_size_target": 1000,
        "chunk_overlap": 200,
        "parallel_processing": True,
        "max_workers": 4,
        "continue_on_error": True,
        "log_processing_errors": True,
        "archon_mcp_available": True,
    }

    # Merge overrides with defaults
    config = {**defaults, **overrides}

    return AgentDependencies(**config)
