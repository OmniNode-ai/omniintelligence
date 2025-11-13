"""
File Writer Effect Node

Handles writing .tree files to {project_root}/.archon/trees/ directory.
Implements atomic writes (write to temp, then rename) for safety.

ONEX Pattern: Effect (File I/O)
Performance Target: <1ms per file write
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

from src.effects.base_effect import BaseEffect
from src.models.effect_result import EffectResult
from src.models.file_location import FileMetadata

logger = logging.getLogger(__name__)


class FileWriterEffect(BaseEffect):
    """
    Effect node for writing .tree files with file metadata and intelligence.

    Output format:
    - Location: {project_root}/.archon/trees/{relative_path}.tree
    - Format: JSON with file metadata, quality scores, intelligence
    - Safety: Atomic writes (temp file + rename)

    Examples:
        Write single file:
        >>> effect = FileWriterEffect()
        >>> result = await effect.execute({
        ...     "file_metadata": file_info,
        ...     "project_root": "/path/to/project",
        ...     "output_dir": "/path/to/project/.archon/trees"
        ... })

        Batch write multiple files:
        >>> result = await effect.execute({
        ...     "files": [file1, file2, file3],
        ...     "project_root": "/path/to/project",
        ...     "output_dir": "/path/to/project/.archon/trees"
        ... })
    """

    def __init__(self, **kwargs):
        """Initialize FileWriterEffect with default retry settings."""
        super().__init__(
            max_retries=3,
            retry_delay_ms=50.0,
            retry_backoff=2.0,
            **kwargs,
        )

    def get_effect_name(self) -> str:
        """Get effect identifier."""
        return "FileWriterEffect"

    async def execute(self, input_data: Dict[str, Any]) -> EffectResult:
        """
        Write .tree files to disk.

        Input data format:
        {
            "files": List[FileMetadata],  # List of files to write
            "project_root": str,           # Project root directory
            "output_dir": str,             # Output directory (.archon/trees)
        }

        OR single file:
        {
            "file_metadata": FileMetadata,
            "project_root": str,
            "output_dir": str,
        }

        Args:
            input_data: File metadata and output configuration

        Returns:
            EffectResult with write statistics
        """
        start_time = time.perf_counter()
        errors = []
        warnings = []
        files_written = 0

        try:
            # Extract input parameters
            project_root = input_data.get("project_root")
            output_dir = input_data.get("output_dir")

            if not project_root or not output_dir:
                return EffectResult(
                    success=False,
                    items_processed=0,
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                    errors=["Missing required parameters: project_root, output_dir"],
                )

            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)

            # Handle single file or batch
            files = input_data.get("files")
            if not files:
                # Single file mode
                file_metadata = input_data.get("file_metadata")
                if file_metadata:
                    files = [file_metadata]
                else:
                    return EffectResult(
                        success=False,
                        items_processed=0,
                        duration_ms=(time.perf_counter() - start_time) * 1000,
                        errors=["No files provided (need 'files' or 'file_metadata')"],
                    )

            # Write each file
            for file_meta in files:
                try:
                    success = await self._write_tree_file(
                        file_metadata=file_meta,
                        project_root=project_root,
                        output_dir=output_dir,
                    )

                    if success:
                        files_written += 1
                    else:
                        warnings.append(
                            f"Failed to write tree file for {file_meta.get('absolute_path', 'unknown')}"
                        )

                except Exception as e:
                    error_msg = f"Error writing {file_meta.get('absolute_path', 'unknown')}: {e}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

            # Determine success
            duration_ms = (time.perf_counter() - start_time) * 1000
            total_files = len(files)
            success = files_written > 0  # Partial success allowed

            logger.info(
                f"FileWriterEffect: {files_written}/{total_files} files written "
                f"in {duration_ms:.1f}ms"
            )

            return EffectResult(
                success=success,
                items_processed=files_written,
                duration_ms=duration_ms,
                errors=errors,
                warnings=warnings,
                metadata={
                    "total_attempted": total_files,
                    "output_dir": output_dir,
                    "project_root": project_root,
                },
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"FileWriterEffect failed: {e}", exc_info=True)

            return EffectResult(
                success=False,
                items_processed=files_written,
                duration_ms=duration_ms,
                errors=[f"FileWriterEffect failed: {e}"],
                warnings=warnings,
            )

    async def _write_tree_file(
        self,
        file_metadata: Dict[str, Any],
        project_root: str,
        output_dir: str,
    ) -> bool:
        """
        Write single .tree file with atomic operation.

        Uses temp file + rename for atomicity to prevent partial writes.

        Args:
            file_metadata: File metadata dictionary
            project_root: Project root path
            output_dir: Output directory

        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract file path
            absolute_path = file_metadata.get("absolute_path")
            if not absolute_path:
                logger.warning("File metadata missing absolute_path")
                return False

            # Calculate relative path and tree file path
            relative_path = absolute_path.replace(project_root, "").lstrip("/")
            tree_file_path = os.path.join(output_dir, f"{relative_path}.tree")

            # Ensure parent directory exists
            tree_file_dir = os.path.dirname(tree_file_path)
            os.makedirs(tree_file_dir, exist_ok=True)

            # Prepare tree data
            tree_data = {
                "file_path": absolute_path,
                "relative_path": relative_path,
                "project_root": project_root,
                **file_metadata,  # Include all metadata fields
            }

            # Write to temporary file first (atomic operation)
            temp_fd, temp_path = tempfile.mkstemp(
                suffix=".tree.tmp",
                dir=tree_file_dir,
                text=True,
            )

            try:
                # Write JSON data
                with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                    json.dump(tree_data, f, indent=2, ensure_ascii=False)

                # Atomic rename (replaces existing file)
                os.replace(temp_path, tree_file_path)

                logger.debug(f"✅ Wrote tree file: {tree_file_path}")
                return True

            except Exception as e:
                # Clean up temp file on error
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
                raise e

        except Exception as e:
            logger.warning(f"Failed to write tree file: {e}")
            return False

    async def write_project_index(
        self,
        project_name: str,
        project_root: str,
        files: List[Dict[str, Any]],
        output_dir: str,
    ) -> bool:
        """
        Write project-level index file with all file references.

        Creates .archon/trees/project_index.json with:
        - Project metadata
        - File count
        - List of indexed files
        - Quality statistics

        Args:
            project_name: Project identifier
            project_root: Project root path
            files: List of file metadata dictionaries
            output_dir: Output directory

        Returns:
            True if successful, False otherwise
        """
        try:
            index_path = os.path.join(output_dir, "project_index.json")

            # Calculate statistics
            total_files = len(files)
            avg_quality = (
                sum(f.get("quality_score", 0.0) for f in files) / total_files
                if total_files > 0
                else 0.0
            )
            avg_compliance = (
                sum(f.get("onex_compliance", 0.0) for f in files) / total_files
                if total_files > 0
                else 0.0
            )

            # Build index data
            index_data = {
                "project_name": project_name,
                "project_root": project_root,
                "total_files": total_files,
                "avg_quality_score": avg_quality,
                "avg_onex_compliance": avg_compliance,
                "files": [
                    {
                        "path": f.get("absolute_path"),
                        "relative_path": f.get("relative_path"),
                        "quality_score": f.get("quality_score", 0.0),
                        "onex_type": f.get("onex_type"),
                    }
                    for f in files
                ],
                "generated_at": time.time(),
            }

            # Atomic write
            temp_fd, temp_path = tempfile.mkstemp(
                suffix=".json.tmp",
                dir=output_dir,
                text=True,
            )

            try:
                with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                    json.dump(index_data, f, indent=2, ensure_ascii=False)

                os.replace(temp_path, index_path)

                logger.info(
                    f"✅ Wrote project index: {index_path} ({total_files} files)"
                )
                return True

            except Exception as e:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
                raise e

        except Exception as e:
            logger.error(f"Failed to write project index: {e}", exc_info=True)
            return False


__all__ = ["FileWriterEffect"]
