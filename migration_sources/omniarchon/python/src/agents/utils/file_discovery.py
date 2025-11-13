#!/usr/bin/env python3
"""
File Discovery and Prioritization Utilities

Handles intelligent file discovery, metadata analysis, and priority scoring
for repository crawling operations.

Version: 1.0.0
Author: Archon Intelligence Services
"""

from pathlib import Path
from typing import Any, Optional


class FileDiscoveryEngine:
    """
    Intelligent file discovery and prioritization engine.

    Provides file scanning, metadata extraction, and priority scoring
    based on file types, patterns, and directory locations.
    """

    def __init__(
        self,
        supported_extensions: dict[str, dict[str, Any]],
        high_value_patterns: dict[str, float],
        exclude_patterns: set[str],
        max_file_size: int = 5 * 1024 * 1024,
    ):
        """
        Initialize file discovery engine.

        Args:
            supported_extensions: Mapping of file extensions to type info
            high_value_patterns: Patterns that boost file priority
            exclude_patterns: Patterns to exclude from discovery
            max_file_size: Maximum file size to process (default: 5MB)
        """
        self.supported_extensions = supported_extensions
        self.high_value_patterns = high_value_patterns
        self.exclude_patterns = exclude_patterns
        self.max_file_size = max_file_size
        self.verbose = False

    async def discover_and_prioritize_files(
        self, repo_path: Path, max_files: int
    ) -> list[dict[str, Any]]:
        """
        Discover files and prioritize them using intelligent scoring.

        Args:
            repo_path: Root path of repository to scan
            max_files: Maximum number of files to return

        Returns:
            List of file info dictionaries sorted by priority
        """
        discovered_files = []

        # Recursive file discovery
        for file_path in repo_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Skip excluded files/directories
            if self.should_exclude_file(file_path):
                continue

            # Skip files that are too large
            try:
                if file_path.stat().st_size > self.max_file_size:
                    if self.verbose:
                        print(f"⚠️ Skipping large file: {file_path.name}")
                    continue
            except OSError as e:
                if self.verbose:
                    print(f"⚠️ Cannot stat file {file_path.name}: {e}")
                continue

            file_info = await self.analyze_file_metadata(file_path, repo_path)
            if file_info:
                discovered_files.append(file_info)

        # Sort by priority score and limit results
        discovered_files.sort(key=lambda x: x["priority_score"], reverse=True)
        limited_files = discovered_files[:max_files]

        if self.verbose:
            print("📊 File Discovery Summary:")
            print(f"   Total files found: {len(discovered_files)}")
            print(f"   Files selected for processing: {len(limited_files)}")
            if limited_files:
                avg_priority = sum(f["priority_score"] for f in limited_files) / len(
                    limited_files
                )
                print(f"   Average priority score: {avg_priority:.2f}")

        return limited_files

    async def analyze_file_metadata(
        self, file_path: Path, repo_root: Path
    ) -> Optional[dict[str, Any]]:
        """
        Analyze file metadata and calculate priority score.

        Args:
            file_path: Path to file to analyze
            repo_root: Root path of repository

        Returns:
            Dictionary with file metadata and priority score, or None if analysis fails
        """
        try:
            relative_path = file_path.relative_to(repo_root)
            extension = file_path.suffix.lower()
            name = file_path.name.lower()

            # Get file info from supported extensions
            file_type_info = self.supported_extensions.get(
                extension, {"type": "other", "language": "unknown", "priority": 0.1}
            )

            # Calculate priority score
            priority_score = file_type_info["priority"]

            # Boost score for high-value file patterns
            for pattern, boost in self.high_value_patterns.items():
                if pattern in name:
                    priority_score = min(1.0, priority_score + boost * 0.3)
                    break

            # Boost score for files in important directories
            path_str = str(relative_path).lower()
            if any(
                important_dir in path_str
                for important_dir in ["src", "lib", "app", "main"]
            ):
                priority_score = min(1.0, priority_score + 0.1)
            if any(doc_dir in path_str for doc_dir in ["docs", "doc", "documentation"]):
                priority_score = min(1.0, priority_score + 0.2)

            # Penalize files in less important directories
            if any(
                low_dir in path_str
                for low_dir in ["test", "tests", "__tests__", "spec"]
            ):
                priority_score = max(0.1, priority_score - 0.2)

            return {
                "path": file_path,
                "relative_path": str(relative_path),
                "name": file_path.name,
                "extension": extension,
                "size": file_path.stat().st_size,
                "modified": file_path.stat().st_mtime,
                "file_type": file_type_info["type"],
                "language": file_type_info["language"],
                "priority_score": priority_score,
            }

        except Exception as e:
            if self.verbose:
                print(f"⚠️ Error analyzing {file_path}: {e}")
            return None

    def should_exclude_file(self, file_path: Path) -> bool:
        """
        Check if file should be excluded from processing.

        Args:
            file_path: Path to file to check

        Returns:
            True if file should be excluded, False otherwise
        """
        path_str = str(file_path)

        # Check exclude patterns
        for pattern in self.exclude_patterns:
            if pattern in path_str:
                return True

        # Check if file is binary (simple heuristic)
        try:
            if file_path.suffix.lower() in {
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".ico",
                ".svg",
                ".pdf",
                ".zip",
                ".tar",
                ".gz",
                ".exe",
                ".dll",
                ".so",
                ".dylib",
                ".whl",
                ".egg",
            }:
                return True
        except (OSError, ValueError) as e:
            if self.verbose:
                print(f"⚠️ Error checking file extension for {file_path}: {e}")
            return True

        return False
