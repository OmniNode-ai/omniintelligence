"""Output model for Entity Extraction Compute."""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from omniintelligence.models.model_entity import ModelEntity


class ModelEntityExtractionOutput(BaseModel):
    """Output model for entity extraction operations.

    This model represents the result of extracting entities from code.
    Uses typed ModelEntity instances for proper validation and type safety.

    The entity_count field is auto-computed from the entities list if not
    explicitly provided, ensuring consistency between the count and actual
    entities.

    Example:
        >>> from omniintelligence.enums import EnumEntityType
        >>> output = ModelEntityExtractionOutput(
        ...     success=True,
        ...     entities=[
        ...         ModelEntity(
        ...             entity_id="ent_1",
        ...             entity_type=EnumEntityType.CLASS,
        ...             name="MyClass",
        ...         )
        ...     ],
        ... )
        >>> output.entity_count  # Auto-computed
        1
    """

    success: bool = Field(
        ...,
        description="Whether entity extraction succeeded",
    )
    entities: list[ModelEntity] = Field(
        default_factory=list,
        description="List of extracted entities with their metadata",
    )
    entity_count: int = Field(
        default=-1,
        ge=-1,
        description="Total number of extracted entities (auto-computed if not set)",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the extraction",
    )

    @model_validator(mode="after")
    def validate_and_compute_entity_count(self) -> Self:
        """Validate and auto-compute entity_count from entities list.

        This validator runs after all fields are populated (mode="after"),
        ensuring it fires even when the entities list is empty.

        Behavior:
            - If entity_count is -1 (default), auto-compute from len(entities)
            - If entity_count is explicitly set, validate it matches len(entities)

        Returns:
            Self with validated/computed entity_count.

        Raises:
            ValueError: If explicitly provided entity_count doesn't match.
        """
        actual_count = len(self.entities)

        # Auto-compute if using default sentinel value (-1)
        if self.entity_count == -1:
            # Use object.__setattr__ since model is frozen
            object.__setattr__(self, "entity_count", actual_count)
        elif self.entity_count != actual_count:
            raise ValueError(
                f"entity_count ({self.entity_count}) must match "
                f"len(entities) ({actual_count})"
            )
        return self

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelEntityExtractionOutput"]
