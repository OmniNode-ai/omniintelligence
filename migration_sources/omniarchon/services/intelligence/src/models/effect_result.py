"""
Effect Result Model

Standardized result format for ONEX effect node operations.
Provides success/failure tracking, performance metrics, and error details.

ONEX Pattern: Compute (pure data model)
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EffectResult(BaseModel):
    """
    Standardized result from effect node execution.

    Effect nodes handle external I/O with graceful degradation:
    - File operations (write, delete)
    - Database operations (index, query)
    - Network operations (API calls)

    Examples:
        Successful file write:
        >>> EffectResult(
        ...     success=True,
        ...     items_processed=10,
        ...     duration_ms=150.5,
        ...     metadata={"output_dir": "/path/to/.archon/trees"}
        ... )

        Partial success with errors:
        >>> EffectResult(
        ...     success=True,
        ...     items_processed=8,
        ...     duration_ms=200.0,
        ...     errors=["Failed to write file_3.tree: Permission denied"],
        ...     warnings=["File file_5.tree already exists, skipped"],
        ...     metadata={"total_attempted": 10, "skipped": 2}
        ... )

        Complete failure:
        >>> EffectResult(
        ...     success=False,
        ...     items_processed=0,
        ...     duration_ms=50.0,
        ...     errors=["Database connection failed: timeout"],
        ...     metadata={"retry_recommended": True}
        ... )
    """

    success: bool = Field(
        ...,
        description="Whether operation completed successfully (partial success allowed)",
    )
    items_processed: int = Field(
        default=0,
        ge=0,
        description="Number of items successfully processed",
    )
    duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Operation duration in milliseconds",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="List of error messages encountered",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="List of warning messages (non-fatal issues)",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional effect-specific metadata",
    )

    @property
    def has_errors(self) -> bool:
        """Check if any errors occurred."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if any warnings occurred."""
        return len(self.warnings) > 0

    @property
    def is_partial_success(self) -> bool:
        """Check if operation partially succeeded (success=True but has errors)."""
        return self.success and self.has_errors

    def add_error(self, error: str) -> None:
        """
        Add error message to result.

        Args:
            error: Error message to add
        """
        self.errors.append(error)

    def add_warning(self, warning: str) -> None:
        """
        Add warning message to result.

        Args:
            warning: Warning message to add
        """
        self.warnings.append(warning)


__all__ = ["EffectResult"]
