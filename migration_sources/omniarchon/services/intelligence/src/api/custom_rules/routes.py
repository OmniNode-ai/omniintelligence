"""
Custom Quality Rules API Routes

FastAPI endpoints for custom quality rules configuration and evaluation.
Part of Phase 5B: Quality Intelligence Upgrades.

Endpoints:
- POST /evaluate - Evaluate code against custom project rules
- GET /project/{project_id}/rules - Get all rules for a project
- POST /project/{project_id}/load-config - Load rules from YAML configuration
- POST /project/{project_id}/rule - Register a new custom rule
- PUT /project/{project_id}/rule/{rule_id}/enable - Enable a rule
- PUT /project/{project_id}/rule/{rule_id}/disable - Disable a rule
- GET /health - Health check
"""

import logging
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from src.api.utils.response_formatters import (
    created_response,
    health_response,
    list_response,
    success_response,
    updated_response,
)
from src.archon_services.quality.custom_rules import CustomQualityRulesEngine

logger = logging.getLogger(__name__)

# Initialize custom rules engine (singleton)
custom_rules_engine = CustomQualityRulesEngine()

# Allowed directory for configuration files (security: prevent path traversal)
ALLOWED_CONFIG_DIR = Path("/app/config/quality_rules").resolve()

# Create router
router = APIRouter(prefix="/api/custom-rules", tags=["Custom Quality Rules"])


class CustomRuleEvaluationRequest(BaseModel):
    """Request model for custom rule evaluation"""

    project_id: str = Field(..., description="Project identifier", max_length=255)
    code: str = Field(
        ...,
        description="Code content to evaluate",
        max_length=1_000_000,  # 1MB limit - reasonable for code files
    )
    file_path: Optional[str] = Field(
        None, description="Optional file path for context", max_length=500
    )


class LoadConfigRequest(BaseModel):
    """Request model for loading rules configuration"""

    config_path: str = Field(..., description="Path to YAML configuration file")


class RuleRegistrationRequest(BaseModel):
    """Request model for registering a custom rule"""

    rule_id: str = Field(..., description="Unique rule identifier")
    rule_type: str = Field(..., description="Rule type: pattern, metric, architectural")
    description: str = Field(..., description="Human-readable description")
    severity: str = Field(..., description="Severity: critical, warning, suggestion")
    weight: float = Field(default=0.1, ge=0.0, le=1.0, description="Rule weight (0-1)")
    enabled: bool = Field(default=True, description="Whether rule is enabled")

    # Rule-specific configuration
    pattern: Optional[str] = Field(None, description="Regex pattern for pattern rules")
    forbids: Optional[str] = Field(None, description="Pattern to forbid")
    requires: Optional[str] = Field(
        None, description="Required base class for architectural rules"
    )
    max_complexity: Optional[int] = Field(
        None, description="Max complexity for metric rules"
    )
    max_length: Optional[int] = Field(None, description="Max length for metric rules")
    min_docstring_coverage: Optional[float] = Field(
        None, description="Min docstring coverage"
    )


@router.post("/evaluate")
async def evaluate_custom_rules(
    request: CustomRuleEvaluationRequest, correlation_id: Optional[UUID] = None
):
    """
    Evaluate code against custom project rules.

    This endpoint checks code against project-specific quality rules and returns
    violations, warnings, suggestions, and a custom quality score.

    Args:
        request: CustomRuleEvaluationRequest with project_id, code, and optional file_path

    Returns:
        Evaluation result including:
        - custom_score: Overall custom quality score (0-1)
        - violations: Critical issues that block validation
        - warnings: Issues that should be fixed
        - suggestions: Recommendations for improvement
        - rules_evaluated: Number of rules checked
    """
    logger.info(
        f"POST /api/custom-rules/evaluate | project_id={request.project_id} | correlation_id={correlation_id}"
    )

    try:
        result = await custom_rules_engine.evaluate_rules(
            project_id=request.project_id,
            code=request.code,
            file_path=request.file_path,
        )

        return success_response(
            data=result,
            metadata={"project_id": request.project_id, "file_path": request.file_path},
        )

    except (ValueError, KeyError, AttributeError) as e:
        logger.error(
            f"Invalid data for rule evaluation: {e}",
            extra={
                "project_id": request.project_id,
                "file_path": request.file_path,
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(status_code=400, detail=f"Invalid request data: {str(e)}")
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(
            f"Failed to evaluate custom rules: {e}",
            extra={
                "project_id": request.project_id,
                "file_path": request.file_path,
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/project/{project_id}/rules")
async def get_project_rules(project_id: str, correlation_id: Optional[UUID] = None):
    """
    Get all custom rules for a project.

    Args:
        project_id: Project identifier

    Returns:
        List of all rules configured for the project with their details
    """
    logger.info(
        f"GET /api/custom-rules/project/{project_id}/rules | correlation_id={correlation_id}"
    )

    try:
        rules = await custom_rules_engine.get_project_rules(project_id)

        # Serialize rules to dict format
        rules_data = []
        for rule in rules:
            rules_data.append(
                {
                    "rule_id": rule.rule_id,
                    "rule_type": rule.rule_type,
                    "description": rule.description,
                    "severity": rule.severity,
                    "weight": rule.weight,
                    "enabled": rule.enabled,
                    "metadata": rule.metadata,
                }
            )

        return list_response(
            items=rules_data,
            resource_type="quality_rules",
            filters_applied={"project_id": project_id},
        )

    except (ValueError, KeyError, AttributeError) as e:
        logger.error(
            f"Invalid project data: {e}",
            extra={"project_id": project_id, "error_type": type(e).__name__},
        )
        raise HTTPException(status_code=400, detail=f"Invalid project ID: {str(e)}")
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(
            f"Failed to get project rules: {e}",
            extra={"project_id": project_id, "error_type": type(e).__name__},
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/project/{project_id}/load-config")
async def load_rules_configuration(
    project_id: str, request: LoadConfigRequest, correlation_id: Optional[UUID] = None
):
    """
    Load custom rules from YAML configuration file.

    This endpoint loads rules from a YAML file and registers them for the project.
    See config/quality_rules/*.yaml for example configurations.

    Args:
        project_id: Project identifier
        request: LoadConfigRequest with config_path

    Returns:
        Number of rules loaded and list of rule IDs
    """
    logger.info(
        f"POST /api/custom-rules/project/{project_id}/load-config | config_path={request.config_path} | correlation_id={correlation_id}"
    )

    try:
        # Security: Treat config_path as relative to ALLOWED_CONFIG_DIR
        # and verify the resolved path stays within the allowed directory
        config_path = (ALLOWED_CONFIG_DIR / request.config_path).resolve()

        # Verify resolved path is under ALLOWED_CONFIG_DIR using parent checking
        if (
            ALLOWED_CONFIG_DIR not in config_path.parents
            and config_path != ALLOWED_CONFIG_DIR
        ):
            raise HTTPException(
                status_code=400,
                detail="Configuration path must be within config/quality_rules/",
            )

        if not config_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Configuration file not found: {request.config_path}",
            )

        await custom_rules_engine.load_project_rules(project_id, config_path)

        rules = await custom_rules_engine.get_project_rules(project_id)
        rule_ids = [r.rule_id for r in rules]

        return success_response(
            data={
                "rules_loaded": len(rule_ids),
                "rule_ids": rule_ids,
                "config_path": str(config_path),
            },
            metadata={"project_id": project_id},
        )

    except HTTPException:
        raise
    except (FileNotFoundError, IOError, PermissionError) as e:
        logger.error(
            f"File access error loading configuration: {e}",
            extra={
                "project_id": project_id,
                "config_path": request.config_path,
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(
            status_code=400, detail=f"Configuration file error: {str(e)}"
        )
    except (ValueError, KeyError) as e:
        logger.error(
            f"Invalid configuration format: {e}",
            extra={
                "project_id": project_id,
                "config_path": request.config_path,
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(
            f"Failed to load configuration: {e}",
            extra={
                "project_id": project_id,
                "config_path": request.config_path,
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/project/{project_id}/rule")
async def register_custom_rule(
    project_id: str,
    request: RuleRegistrationRequest,
    correlation_id: Optional[UUID] = None,
):
    """
    Register a new custom rule for a project.

    This endpoint allows dynamic registration of custom rules without YAML configuration.
    Rules can be pattern-based, metric-based, or architectural.

    Args:
        project_id: Project identifier
        request: RuleRegistrationRequest with rule configuration

    Returns:
        Success confirmation with rule details
    """
    logger.info(
        f"POST /api/custom-rules/project/{project_id}/rule | rule_id={request.rule_id} | correlation_id={correlation_id}"
    )

    try:
        # Build rule configuration dict
        rule_config = {
            "rule_id": request.rule_id,
            "rule_type": request.rule_type,
            "description": request.description,
            "severity": request.severity,
            "weight": request.weight,
            "enabled": request.enabled,
        }

        # Add type-specific configuration
        if request.pattern:
            rule_config["pattern"] = request.pattern
        if request.forbids:
            rule_config["forbids"] = request.forbids
        if request.requires:
            rule_config["requires"] = request.requires
        if request.max_complexity:
            rule_config["max_complexity"] = request.max_complexity
        if request.max_length:
            rule_config["max_length"] = request.max_length
        if request.min_docstring_coverage:
            rule_config["min_docstring_coverage"] = request.min_docstring_coverage

        # Create rule from configuration
        rule = await custom_rules_engine._create_rule_from_config(
            project_id, rule_config
        )

        if not rule:
            raise HTTPException(
                status_code=400, detail="Failed to create rule from configuration"
            )

        # Register rule
        await custom_rules_engine.register_rule(project_id, rule)

        return created_response(
            resource={
                "rule_id": request.rule_id,
                "rule_type": request.rule_type,
                "description": request.description,
                "severity": request.severity,
                "weight": request.weight,
                "enabled": request.enabled,
                "project_id": project_id,
            },
            resource_type="quality_rule",
            resource_id=request.rule_id,
        )

    except HTTPException:
        raise
    except (ValueError, KeyError, AttributeError, TypeError) as e:
        logger.error(
            f"Invalid rule configuration: {e}",
            extra={
                "project_id": project_id,
                "rule_id": request.rule_id,
                "rule_type": request.rule_type,
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(
            status_code=400, detail=f"Invalid rule configuration: {str(e)}"
        )
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(
            f"Failed to register custom rule: {e}",
            extra={
                "project_id": project_id,
                "rule_id": request.rule_id,
                "rule_type": request.rule_type,
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/project/{project_id}/rule/{rule_id}/enable")
async def enable_rule(
    project_id: str, rule_id: str, correlation_id: Optional[UUID] = None
):
    """
    Enable a custom rule for a project.

    Args:
        project_id: Project identifier
        rule_id: Rule identifier

    Returns:
        Success confirmation
    """
    logger.info(
        f"PUT /api/custom-rules/project/{project_id}/rule/{rule_id}/enable | correlation_id={correlation_id}"
    )

    try:
        success = await custom_rules_engine.enable_rule(project_id, rule_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Rule '{rule_id}' not found for project '{project_id}'",
            )

        return updated_response(
            resource={"rule_id": rule_id, "enabled": True, "project_id": project_id},
            resource_type="quality_rule",
            resource_id=rule_id,
            fields_updated=["enabled"],
        )

    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        logger.error(
            f"Invalid rule or project ID: {e}",
            extra={
                "project_id": project_id,
                "rule_id": rule_id,
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(
            status_code=400, detail=f"Invalid rule or project: {str(e)}"
        )
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(
            f"Failed to enable rule: {e}",
            extra={
                "project_id": project_id,
                "rule_id": rule_id,
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/project/{project_id}/rule/{rule_id}/disable")
async def disable_rule(
    project_id: str, rule_id: str, correlation_id: Optional[UUID] = None
):
    """
    Disable a custom rule for a project.

    Args:
        project_id: Project identifier
        rule_id: Rule identifier

    Returns:
        Success confirmation
    """
    logger.info(
        f"PUT /api/custom-rules/project/{project_id}/rule/{rule_id}/disable | correlation_id={correlation_id}"
    )

    try:
        success = await custom_rules_engine.disable_rule(project_id, rule_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Rule '{rule_id}' not found for project '{project_id}'",
            )

        return updated_response(
            resource={"rule_id": rule_id, "enabled": False, "project_id": project_id},
            resource_type="quality_rule",
            resource_id=rule_id,
            fields_updated=["enabled"],
        )

    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        logger.error(
            f"Invalid rule or project ID: {e}",
            extra={
                "project_id": project_id,
                "rule_id": rule_id,
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(
            status_code=400, detail=f"Invalid rule or project: {str(e)}"
        )
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(
            f"Failed to disable rule: {e}",
            extra={
                "project_id": project_id,
                "rule_id": rule_id,
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check(correlation_id: Optional[UUID] = None):
    """
    Health check endpoint for custom rules service.

    Returns:
        Service status and statistics
    """
    logger.info(f"GET /api/custom-rules/health | correlation_id={correlation_id}")

    try:
        total_projects = len(custom_rules_engine.rules)
        total_rules = sum(len(rules) for rules in custom_rules_engine.rules.values())

        return health_response(
            status="healthy",
            checks={"total_projects": total_projects, "total_rules": total_rules},
            service="custom_quality_rules",
        )

    except Exception as e:
        # Health check should always return, catch all exceptions
        logger.error(
            f"Health check failed: {e}",
            extra={"endpoint": "/health", "error_type": type(e).__name__},
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/project/{project_id}/rules")
async def clear_project_rules(project_id: str, correlation_id: Optional[UUID] = None):
    """
    Clear all custom rules for a project.

    WARNING: This operation cannot be undone.

    Args:
        project_id: Project identifier

    Returns:
        Number of rules cleared
    """
    logger.info(
        f"DELETE /api/custom-rules/project/{project_id}/rules | correlation_id={correlation_id}"
    )

    try:
        if project_id not in custom_rules_engine.rules:
            return success_response(
                data={"rules_cleared": 0, "deleted": True},
                metadata={"project_id": project_id, "resource_type": "quality_rules"},
            )

        rules_count = len(custom_rules_engine.rules[project_id])
        del custom_rules_engine.rules[project_id]

        return success_response(
            data={"rules_cleared": rules_count, "deleted": True},
            metadata={"project_id": project_id, "resource_type": "quality_rules"},
        )

    except (ValueError, KeyError) as e:
        logger.error(
            f"Invalid project ID: {e}",
            extra={"project_id": project_id, "error_type": type(e).__name__},
        )
        raise HTTPException(status_code=400, detail=f"Invalid project ID: {str(e)}")
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(
            f"Failed to clear project rules: {e}",
            extra={"project_id": project_id, "error_type": type(e).__name__},
        )
        raise HTTPException(status_code=500, detail=str(e))
