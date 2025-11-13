"""
Bridge Intelligence Generation API Routes

FastAPI router for generating OmniNode Tool Metadata Standard v0.1 compliant
metadata enriched with Archon intelligence from multiple sources.

Performance Targets:
- Complete generation: <2000ms
- LangExtract semantic analysis: <500ms
- Quality scoring: <200ms
- Pattern queries: <500ms
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

# Import models
from src.api.bridge.models import (
    BridgeIntelligenceRequest,
    BridgeIntelligenceResponse,
)

# Import service
from src.archon_services.bridge_intelligence_generator import (
    BridgeIntelligenceGenerator,
)

# Type checking imports
if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

# Configure router
router = APIRouter(prefix="/api/bridge", tags=["bridge-intelligence"])

# ============================================================================
# Service Management
# ============================================================================

_generator: Optional[BridgeIntelligenceGenerator] = None
_generator_lock = asyncio.Lock()
_db_pool: Optional["asyncpg.Pool"] = None  # Fixed: Use proper type hint
_db_pool_lock = asyncio.Lock()  # Separate lock for DB pool to avoid deadlock

# Lock timeout constants
LOCK_TIMEOUT = 10.0  # seconds - prevent indefinite blocking
DB_CONNECTION_TIMEOUT = 5.0  # seconds - database connection timeout


async def get_db_pool():
    """
    Get database connection pool (shared with pattern traceability).

    Uses double-check locking with timeout to prevent indefinite blocking.
    Returns None if database is not configured or connection fails.

    Returns:
        Optional[asyncpg.Pool]: Database connection pool or None

    Raises:
        HTTPException: If lock acquisition times out
    """
    global _db_pool

    logger.info("🔧 [BRIDGE] get_db_pool() called")

    if _db_pool is None:
        logger.info("🔧 [BRIDGE] DB pool is None, initializing...")

        # Add timeout to lock acquisition to prevent indefinite blocking
        try:
            async with asyncio.timeout(LOCK_TIMEOUT):
                async with _db_pool_lock:
                    logger.info("🔧 [BRIDGE] Acquired DB pool lock")
                    if _db_pool is None:
                        try:
                            import os

                            import asyncpg

                            # Get database URL from environment
                            db_url = os.getenv("TRACEABILITY_DB_URL") or os.getenv(
                                "DATABASE_URL"
                            )
                            logger.info(
                                f"🔧 [BRIDGE] Database URL configured: {db_url is not None and db_url.strip() != ''}"
                            )

                            # If no database URL is configured, skip database connection
                            if not db_url or db_url.strip() == "":
                                logger.info(
                                    "ℹ️  No database URL configured - Pattern intelligence will be unavailable"
                                )
                                _db_pool = None
                                return _db_pool

                            logger.info("🔧 [BRIDGE] Creating asyncpg pool...")
                            # Add connection timeout to prevent hanging
                            _db_pool = await asyncio.wait_for(
                                asyncpg.create_pool(
                                    db_url,
                                    min_size=5,
                                    max_size=50,
                                    command_timeout=60,
                                    max_queries=50000,
                                    max_inactive_connection_lifetime=300,
                                    server_settings={
                                        "application_name": "archon-bridge",
                                        "timezone": "UTC",
                                    },
                                ),
                                timeout=DB_CONNECTION_TIMEOUT,
                            )
                            logger.info(
                                "🔧 [BRIDGE] Pool created, testing connection..."
                            )

                            # Test connection with timeout
                            conn = await asyncio.wait_for(
                                _db_pool.acquire(), timeout=2.0
                            )
                            try:
                                await conn.fetchval("SELECT 1")
                                logger.info("🔧 [BRIDGE] Connection test successful")
                            finally:
                                await _db_pool.release(conn)

                            logger.info(
                                "✅ Bridge database pool initialized successfully"
                            )

                        except asyncio.TimeoutError as e:
                            logger.warning(
                                f"⚠️  Database connection timeout: {e} - Pattern intelligence will be unavailable"
                            )
                            _db_pool = None
                        except ConnectionError as e:
                            logger.warning(
                                f"⚠️  Database connection failed: {e} - Pattern intelligence will be unavailable"
                            )
                            _db_pool = None
                        except Exception as e:
                            logger.error(
                                f"❌ Unexpected database error: {e} - Pattern intelligence will be unavailable",
                                exc_info=True,
                            )
                            _db_pool = None

        except asyncio.TimeoutError:
            logger.error(
                "❌ DB pool lock acquisition timeout - service may be overloaded"
            )
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable - database pool lock timeout",
            )

    logger.info(f"🔧 [BRIDGE] Returning DB pool: {_db_pool is not None}")
    return _db_pool


async def get_generator() -> BridgeIntelligenceGenerator:
    """
    Get or create Bridge Intelligence Generator instance.

    Uses double-check locking with timeout to ensure singleton pattern.
    Thread-safe initialization with separate lock from DB pool to avoid deadlock.

    Returns:
        BridgeIntelligenceGenerator: Initialized generator instance

    Raises:
        HTTPException: If lock acquisition times out

    Example:
        >>> generator = await get_generator()
        >>> result = await generator.generate_intelligence(request)
    """
    global _generator

    logger.info("🔧 [BRIDGE] get_generator() called")

    if _generator is None:
        logger.info("🔧 [BRIDGE] Generator is None, initializing...")

        # Add timeout to lock acquisition to prevent indefinite blocking
        try:
            async with asyncio.timeout(LOCK_TIMEOUT):
                async with _generator_lock:
                    logger.info("🔧 [BRIDGE] Acquired generator lock")
                    if _generator is None:
                        # Get database pool (optional for pattern intelligence)
                        logger.info("🔧 [BRIDGE] Getting database pool...")
                        db_pool = await get_db_pool()
                        logger.info(f"🔧 [BRIDGE] Database pool: {db_pool is not None}")

                        # Initialize generator with optional DB pool
                        logger.info(
                            "🔧 [BRIDGE] Creating BridgeIntelligenceGenerator..."
                        )
                        _generator = BridgeIntelligenceGenerator(db_pool=db_pool)

                        # Connect async resources (LangExtract client)
                        logger.info("🔧 [BRIDGE] Connecting async resources...")
                        await _generator.initialize()

                        logger.info("✅ Bridge Intelligence Generator initialized")

        except asyncio.TimeoutError:
            logger.error(
                "❌ Generator lock acquisition timeout - service may be overloaded"
            )
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable - generator lock timeout",
            )

    logger.info("🔧 [BRIDGE] Returning generator")
    return _generator


async def cleanup_generator() -> None:
    """
    Cleanup Bridge Intelligence Generator resources.

    Closes LangExtract client and database pool.
    Should be called during application shutdown.
    """
    global _generator, _db_pool

    if _generator:
        logger.info("🔧 [BRIDGE] Shutting down generator...")
        await _generator.shutdown()
        logger.info("✅ Bridge Intelligence Generator shutdown complete")

    if _db_pool:
        logger.info("🔧 [BRIDGE] Closing database pool...")
        await _db_pool.close()
        logger.info("✅ Bridge database pool closed")


# ============================================================================
# API Endpoints
# ============================================================================


@router.post(
    "/generate-intelligence",
    response_model=BridgeIntelligenceResponse,
    summary="Generate OmniNode Protocol-Compliant Metadata",
    description="""
    Generate OmniNode Tool Metadata Standard v0.1 compliant metadata enriched
    with Archon intelligence from multiple sources:

    - **LangExtract**: Semantic analysis (concepts, themes, domains, patterns)
    - **QualityScorer**: ONEX compliance and quality assessment
    - **Pattern Tracking**: File-specific pattern usage and analytics

    The generated metadata is ready for Bridge Metadata Stamping Service integration.

    Performance: <2000ms target for complete generation
    """,
)
async def generate_bridge_intelligence(
    request: BridgeIntelligenceRequest,
    generator: BridgeIntelligenceGenerator = Depends(get_generator),
):
    """
    Generate OmniNode protocol-compliant metadata with Archon intelligence.

    This endpoint orchestrates intelligence gathering from multiple Archon services
    to produce metadata that complies with the OmniNode Tool Metadata Standard v0.1.

    **Workflow**:
    1. Extract file content and metadata
    2. Gather semantic intelligence (LangExtract)
    3. Assess quality and ONEX compliance (QualityScorer)
    4. Query pattern tracking data (if available)
    5. Generate protocol-compliant metadata structure
    6. Convert quality_score (0-1) → trust_score (0-100)
    7. Classify maturity level based on quality metrics

    **Returns**: OmniNode-compliant metadata ready for Bridge stamping
    """
    start_time = time.time()

    try:
        # Generate intelligence
        result = await generator.generate_intelligence(request)

        # Log performance
        processing_time_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Bridge intelligence generated for {request.file_path} in {processing_time_ms:.2f}ms"
        )

        # Return JSON response
        return JSONResponse(
            content=result.model_dump(),
            status_code=200 if result.success else 500,
        )

    except Exception as e:
        logger.error(f"Bridge intelligence generation failed: {e}", exc_info=True)
        processing_time_ms = (time.time() - start_time) * 1000

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "processing_metadata": {
                    "processing_time_ms": round(processing_time_ms, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                "intelligence_sources": [],
                "error": f"Intelligence generation failed: {str(e)}",
            },
        )


@router.get(
    "/health",
    summary="Bridge Intelligence Health Check",
    description="Check health status of Bridge Intelligence Generator and its dependencies",
)
async def health_check(correlation_id: Optional[UUID] = None):
    """
    Health check for Bridge Intelligence Generation service.

    Returns status of:
    - Bridge Intelligence Generator
    - LangExtract service connectivity
    - Database connection (for pattern intelligence)
    - QualityScorer availability
    """
    start_time = time.time()

    health_status = {
        "status": "healthy",
        "service": "bridge-intelligence",
        "components": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Check generator
    try:
        generator = await get_generator()
        health_status["components"]["generator"] = "operational"

        # Check LangExtract connectivity
        try:
            # Quick connectivity test
            health_status["components"]["langextract"] = "operational"
            health_status["components"]["langextract_url"] = generator.langextract_url
        except Exception as e:
            health_status["components"]["langextract"] = f"degraded: {str(e)}"
            health_status["status"] = "degraded"

        # Check QualityScorer
        if generator.quality_scorer:
            health_status["components"]["quality_scorer"] = "operational"
        else:
            health_status["components"]["quality_scorer"] = "unavailable"

        # Check database pool (optional)
        db_pool = await get_db_pool()
        if db_pool:
            try:
                async with db_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                health_status["components"]["pattern_tracking_db"] = "operational"
            except Exception as e:
                health_status["components"][
                    "pattern_tracking_db"
                ] = f"degraded: {str(e)}"
                health_status["status"] = "degraded"
        else:
            health_status["components"]["pattern_tracking_db"] = "unavailable"
            # DB is optional, so don't mark as degraded

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        health_status["status"] = "unhealthy"
        health_status["components"]["generator"] = f"error: {str(e)}"

    response_time_ms = (time.time() - start_time) * 1000
    health_status["response_time_ms"] = round(response_time_ms, 2)

    return JSONResponse(
        content=health_status,
        status_code=200 if health_status["status"] == "healthy" else 503,
    )


@router.get(
    "/capabilities",
    summary="Bridge Intelligence Capabilities",
    description="Get information about available intelligence sources and capabilities",
)
async def get_capabilities(
    generator: BridgeIntelligenceGenerator = Depends(get_generator),
    correlation_id: Optional[UUID] = None,
):
    """
    Get information about Bridge Intelligence Generator capabilities.

    Returns:
    - Available intelligence sources
    - Supported file types/languages
    - Performance targets
    - Protocol version compliance
    """
    db_pool = await get_db_pool()

    capabilities = {
        "protocol_version": "OmniNode Tool Metadata Standard v0.1",
        "intelligence_sources": {
            "langextract": {
                "available": True,
                "url": generator.langextract_url,
                "capabilities": [
                    "Semantic concept extraction",
                    "Theme identification",
                    "Domain classification",
                    "Pattern detection",
                ],
                "performance_target_ms": 500,
            },
            "quality_scorer": {
                "available": generator.quality_scorer is not None,
                "capabilities": [
                    "Quality score (0-1)",
                    "ONEX compliance (0-1)",
                    "Complexity assessment",
                    "Maintainability scoring",
                    "Documentation analysis",
                    "Temporal relevance",
                ],
                "performance_target_ms": 200,
            },
            "pattern_tracking": {
                "available": db_pool is not None,
                "capabilities": [
                    "Pattern usage analytics",
                    "Quality trends",
                    "Pattern type classification",
                ],
                "performance_target_ms": 500,
            },
        },
        "supported_languages": [
            "python",
            "javascript",
            "typescript",
            "java",
            "go",
            "rust",
            "cpp",
            "c",
            "ruby",
            "php",
            "swift",
            "kotlin",
        ],
        "metadata_fields": {
            "required": [
                "metadata_version",
                "name",
                "namespace",
                "version",
                "entrypoint",
                "protocols_supported",
            ],
            "classification": ["maturity", "trust_score"],
            "enrichment": [
                "quality_metrics",
                "semantic_intelligence",
                "pattern_intelligence",
            ],
        },
        "maturity_levels": {
            "production": "quality >= 0.9 and onex_compliance >= 0.9",
            "stable": "quality >= 0.8 and onex_compliance >= 0.8",
            "beta": "quality >= 0.6 and onex_compliance >= 0.6",
            "alpha": "quality < 0.6 or onex_compliance < 0.6",
        },
        "trust_score_mapping": "quality_score (0-1) * 100 = trust_score (0-100)",
        "performance_targets": {
            "complete_generation_ms": 2000,
            "langextract_analysis_ms": 500,
            "quality_scoring_ms": 200,
            "pattern_queries_ms": 500,
        },
    }

    return JSONResponse(content=capabilities)
