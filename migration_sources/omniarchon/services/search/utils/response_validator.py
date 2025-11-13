"""
Response Validation Utility

Provides validation functions for external API responses with:
- Pydantic model validation
- Graceful error handling
- Confidence scoring based on validation success
- Partial validation support
- Detailed error reporting
"""

import logging
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

from models.external_validation import (
    BridgeHealthResponse,
    BridgeMappingStats,
    IntelligenceHealthResponse,
    IntelligenceQualityResponse,
    MemgraphHealthResponse,
    MemgraphQueryResult,
    OllamaEmbeddingResponse,
    OllamaHealthResponse,
    QdrantCollectionInfo,
    QdrantScoredPoint,
    QdrantSearchResponse,
    ValidationResult,
    ValidationStatus,
)
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ResponseValidator:
    """
    Validates external API responses using Pydantic models.

    Provides graceful degradation by:
    1. Attempting full validation first
    2. Collecting validation errors
    3. Calculating confidence based on error severity
    4. Returning partial data when possible
    """

    @staticmethod
    def validate_response(
        response_data: Union[Dict[str, Any], List[Dict[str, Any]]],
        model_class: Type[T],
        service_name: str,
        allow_partial: bool = True,
    ) -> ValidationResult:
        """
        Validate response data against Pydantic model.

        Args:
            response_data: Raw response data from external API
            model_class: Pydantic model class to validate against
            service_name: Name of the service for logging
            allow_partial: Allow partial validation with reduced confidence

        Returns:
            ValidationResult with status, validated data, and confidence score
        """
        errors = []
        warnings = []
        validated_data = None
        status = ValidationStatus.FAILED

        try:
            # Attempt full validation
            validated_data = model_class.model_validate(response_data)
            status = ValidationStatus.VALID
            confidence = 1.0

            logger.debug(
                f"✅ {service_name}: Response validation successful ({model_class.__name__})"
            )

            return ValidationResult(
                status=status,
                confidence=confidence,
                validated_data=validated_data,
                errors=[],
                warnings=[],
                raw_response=response_data if isinstance(response_data, dict) else None,
                service_name=service_name,
            )

        except ValidationError as e:
            # Collect validation errors
            for error in e.errors():
                error_msg = f"{error['loc']}: {error['msg']}"
                errors.append(error_msg)

            logger.warning(
                f"⚠️  {service_name}: Validation failed - {len(errors)} errors found"
            )

            # Attempt partial validation if allowed
            if allow_partial:
                partial_data, partial_warnings = (
                    ResponseValidator._extract_partial_data(
                        response_data, model_class, errors
                    )
                )

                if partial_data:
                    validated_data = partial_data
                    warnings = partial_warnings
                    status = ValidationStatus.PARTIAL
                    confidence = ResponseValidator._calculate_confidence(
                        errors, warnings, response_data
                    )

                    logger.info(
                        f"✓ {service_name}: Partial validation successful (confidence: {confidence:.2f})"
                    )
                else:
                    status = ValidationStatus.INVALID
                    confidence = 0.0
            else:
                status = ValidationStatus.INVALID
                confidence = 0.0

        except Exception as e:
            # Unexpected error during validation
            error_msg = f"Validation exception: {str(e)}"
            errors.append(error_msg)
            status = ValidationStatus.FAILED
            confidence = 0.0

            logger.error(f"❌ {service_name}: Validation failed with exception: {e}")

        return ValidationResult(
            status=status,
            confidence=confidence,
            validated_data=validated_data,
            errors=errors,
            warnings=warnings,
            raw_response=response_data if isinstance(response_data, dict) else None,
            service_name=service_name,
        )

    @staticmethod
    def _extract_partial_data(
        response_data: Union[Dict[str, Any], List],
        model_class: Type[T],
        validation_errors: List[str],
    ) -> tuple[Optional[T], List[str]]:
        """
        Attempt to extract valid data from partially invalid response.

        Args:
            response_data: Raw response data
            model_class: Pydantic model class
            validation_errors: List of validation errors

        Returns:
            Tuple of (partial_data, warnings)
        """
        warnings = []

        if not isinstance(response_data, dict):
            return None, warnings

        # Create a copy and fill in missing required fields with defaults
        partial_data = response_data.copy()

        try:
            # Get model fields and their defaults
            model_fields = model_class.model_fields

            for field_name, field_info in model_fields.items():
                # Skip if field already exists in data
                if field_name in partial_data:
                    continue

                # Check if field is required
                if field_info.is_required():
                    # Try to provide a sensible default based on type
                    field_type = field_info.annotation
                    default_value = ResponseValidator._get_type_default(field_type)

                    if default_value is not None:
                        partial_data[field_name] = default_value
                        warnings.append(
                            f"Missing required field '{field_name}' filled with default: {default_value}"
                        )

            # Attempt validation with partial data
            validated = model_class.model_validate(partial_data)
            return validated, warnings

        except Exception as e:
            logger.debug(f"Partial validation failed: {e}")
            return None, warnings

    @staticmethod
    def _get_type_default(field_type: Any) -> Any:
        """
        Get sensible default value for a given type.

        Args:
            field_type: Python type annotation

        Returns:
            Default value for the type
        """
        # Handle common types
        type_defaults = {
            str: "",
            int: 0,
            float: 0.0,
            bool: False,
            list: [],
            dict: {},
        }

        # Get the origin type for generics (List[str] -> list)
        origin = getattr(field_type, "__origin__", None)
        if origin:
            return type_defaults.get(origin, None)

        return type_defaults.get(field_type, None)

    @staticmethod
    def _calculate_confidence(
        errors: List[str], warnings: List[str], response_data: Any
    ) -> float:
        """
        Calculate confidence score based on validation results.

        Args:
            errors: List of validation errors
            warnings: List of validation warnings
            response_data: Original response data

        Returns:
            Confidence score between 0.0 and 1.0
        """
        base_confidence = 1.0

        # Reduce confidence for each error (20% penalty)
        error_penalty = len(errors) * 0.20

        # Reduce confidence for each warning (5% penalty)
        warning_penalty = len(warnings) * 0.05

        # Calculate final confidence
        confidence = max(0.0, base_confidence - error_penalty - warning_penalty)

        # Boost confidence if critical fields are present
        if isinstance(response_data, dict):
            critical_fields = ["status", "result", "data", "success"]
            present_critical = sum(
                1 for field in critical_fields if field in response_data
            )

            if present_critical > 0:
                boost = present_critical * 0.05
                confidence = min(1.0, confidence + boost)

        return round(confidence, 2)

    @staticmethod
    def validate_list_response(
        response_data: List[Dict[str, Any]],
        item_model_class: Type[T],
        service_name: str,
        allow_partial: bool = True,
    ) -> ValidationResult:
        """
        Validate a list of items from external API.

        Args:
            response_data: List of response items
            item_model_class: Pydantic model for each item
            service_name: Service name for logging
            allow_partial: Allow partial validation

        Returns:
            ValidationResult with list of validated items
        """
        validated_items = []
        errors = []
        warnings = []

        for idx, item_data in enumerate(response_data):
            try:
                validated_item = item_model_class.model_validate(item_data)
                validated_items.append(validated_item)
            except ValidationError as e:
                if allow_partial:
                    # Log error but continue with other items
                    error_msg = f"Item {idx}: validation failed"
                    warnings.append(error_msg)
                    logger.warning(f"⚠️  {service_name}: {error_msg}")
                else:
                    error_msg = f"Item {idx}: {str(e)}"
                    errors.append(error_msg)

        # Determine status based on results
        total_items = len(response_data)
        validated_count = len(validated_items)

        if validated_count == 0:
            status = ValidationStatus.INVALID
            confidence = 0.0
        elif validated_count == total_items:
            status = ValidationStatus.VALID
            confidence = 1.0
        else:
            status = ValidationStatus.PARTIAL
            # Confidence proportional to successful validation rate
            confidence = round(validated_count / total_items, 2)

        logger.info(
            f"{service_name}: Validated {validated_count}/{total_items} items (confidence: {confidence:.2f})"
        )

        return ValidationResult(
            status=status,
            confidence=confidence,
            validated_data=validated_items,
            errors=errors,
            warnings=warnings,
            raw_response=None,  # Too large for lists
            service_name=service_name,
        )


# ============================================================================
# Service-Specific Validation Functions
# ============================================================================


def validate_ollama_embedding(
    response_data: Dict[str, Any], allow_partial: bool = True
) -> ValidationResult:
    """Validate Ollama embedding API response"""
    return ResponseValidator.validate_response(
        response_data, OllamaEmbeddingResponse, "Ollama", allow_partial
    )


def validate_ollama_health(
    response_data: Dict[str, Any], allow_partial: bool = True
) -> ValidationResult:
    """Validate Ollama health check response"""
    return ResponseValidator.validate_response(
        response_data, OllamaHealthResponse, "Ollama", allow_partial
    )


def validate_qdrant_search(
    response_data: Dict[str, Any], allow_partial: bool = True
) -> ValidationResult:
    """Validate Qdrant search response"""
    return ResponseValidator.validate_response(
        response_data, QdrantSearchResponse, "Qdrant", allow_partial
    )


def validate_qdrant_points(
    response_data: List[Dict[str, Any]], allow_partial: bool = True
) -> ValidationResult:
    """Validate list of Qdrant points"""
    return ResponseValidator.validate_list_response(
        response_data, QdrantScoredPoint, "Qdrant", allow_partial
    )


def validate_qdrant_collection_info(
    response_data: Dict[str, Any], allow_partial: bool = True
) -> ValidationResult:
    """Validate Qdrant collection info response"""
    return ResponseValidator.validate_response(
        response_data, QdrantCollectionInfo, "Qdrant", allow_partial
    )


def validate_memgraph_results(
    response_data: List[Dict[str, Any]], allow_partial: bool = True
) -> ValidationResult:
    """Validate Memgraph query results"""
    return ResponseValidator.validate_list_response(
        response_data, MemgraphQueryResult, "Memgraph", allow_partial
    )


def validate_memgraph_health(
    response_data: Dict[str, Any], allow_partial: bool = True
) -> ValidationResult:
    """Validate Memgraph health check response"""
    return ResponseValidator.validate_response(
        response_data, MemgraphHealthResponse, "Memgraph", allow_partial
    )


def validate_bridge_mapping_stats(
    response_data: Dict[str, Any], allow_partial: bool = True
) -> ValidationResult:
    """Validate Bridge service mapping stats response"""
    return ResponseValidator.validate_response(
        response_data, BridgeMappingStats, "Bridge", allow_partial
    )


def validate_bridge_health(
    response_data: Dict[str, Any], allow_partial: bool = True
) -> ValidationResult:
    """Validate Bridge service health check response"""
    return ResponseValidator.validate_response(
        response_data, BridgeHealthResponse, "Bridge", allow_partial
    )


def validate_intelligence_quality(
    response_data: Dict[str, Any], allow_partial: bool = True
) -> ValidationResult:
    """Validate Intelligence service quality assessment response"""
    return ResponseValidator.validate_response(
        response_data, IntelligenceQualityResponse, "Intelligence", allow_partial
    )


def validate_intelligence_health(
    response_data: Dict[str, Any], allow_partial: bool = True
) -> ValidationResult:
    """Validate Intelligence service health check response"""
    return ResponseValidator.validate_response(
        response_data, IntelligenceHealthResponse, "Intelligence", allow_partial
    )
