#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pattern Ingestion Script for Archon Intelligence

Indexes ~1000 code and execution patterns into Qdrant archon_vectors collection.

Configuration:
    Uses centralized config from config/settings.py
    Override with environment variables (QDRANT_URL, EMBEDDING_MODEL_URL, etc.)

Usage:
    python3 scripts/ingest_patterns.py
    python3 scripts/ingest_patterns.py --dry-run
    python3 scripts/ingest_patterns.py --limit 100
"""

import argparse
import asyncio
import hashlib
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Project setup
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

env_path = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=env_path)

# Import centralized configuration
from config import settings

# Import dependencies
try:
    import httpx
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct
except ImportError as e:
    print(f"Error: Required packages not installed: {e}")
    sys.exit(1)

# Configuration (from centralized settings with environment overrides)
OMNICLAUDE_PATH = Path("/Volumes/PRO-G40/Code/omniclaude")
QDRANT_URL = os.getenv("QDRANT_URL", settings.qdrant_url)
COLLECTION = "archon_vectors"
EMBEDDING_MODEL_URL = os.getenv("EMBEDDING_MODEL_URL", "http://192.168.86.201:8002")

# Read embedding config from .env
# Default to 1536 to match main .env configuration (Alibaba-NLP/gte-Qwen2-1.5B-instruct)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "Alibaba-NLP/gte-Qwen2-1.5B-instruct")
EMBEDDING_SIZE = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
PROGRESS_INTERVAL = 10
MAX_CONTENT_LENGTH = 2000
BATCH_SIZE = 10

ONEX_NODE_PATTERNS = {
    "effect": ["_effect.py", "effect_"],
    "compute": ["_compute.py", "compute_"],
    "reducer": ["_reducer.py", "reducer_"],
    "orchestrator": ["_orchestrator.py", "orchestrator_"],
}

# Initialize logger
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def extract_code_patterns(
    base_path: Path, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Extract code patterns from omniclaude codebase."""
    logger.info(f"Extracting code patterns from: {base_path}")
    patterns = []
    file_count = 0

    py_files = list(base_path.rglob("*.py"))
    logger.info(f"Found {len(py_files)} Python files")

    for py_file in py_files:
        if limit and file_count >= limit:
            break

        try:
            if "__pycache__" in str(py_file) or ".pyc" in str(py_file):
                continue

            with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(MAX_CONTENT_LENGTH)

            node_type = "general"
            confidence = 0.70

            for onex_type, patterns_list in ONEX_NODE_PATTERNS.items():
                if any(pattern in py_file.name.lower() for pattern in patterns_list):
                    node_type = onex_type
                    confidence = 0.85
                    break

            relative_path = py_file.relative_to(base_path)
            pattern = {
                "type": "code",
                "name": str(relative_path),
                "file_path": str(py_file.absolute()),
                "content": content,
                "node_type": node_type,
                "confidence": confidence,
                "file_type": ".py",
                "indexed_at": datetime.utcnow().isoformat() + "Z",
                "project_name": "omniclaude",
                "domains": ["ai_agents", "development"],
                "pattern_types": [node_type] if node_type != "general" else ["general"],
            }

            patterns.append(pattern)
            file_count += 1

            if file_count % 100 == 0:
                logger.info(f"Extracted {file_count} code patterns...")

        except Exception as e:
            logger.warning(f"Failed to extract pattern from {py_file}: {e}")
            continue

    logger.info(f"Extracted {len(patterns)} code patterns")
    return patterns


def extract_execution_patterns() -> List[Dict[str, Any]]:
    """Extract ONEX execution patterns."""
    logger.info("Defining ONEX execution patterns...")

    patterns = [
        {
            "type": "execution",
            "name": "Node State Management (FSM)",
            "content": "ONEX Pattern: Finite State Machine for node lifecycle management. States: IDLE, INITIALIZING, READY, PROCESSING, ERROR, SHUTDOWN. Transitions with guards, state persistence in Valkey/Redis, event emission to event bus.",
            "node_types": ["effect", "reducer", "orchestrator"],
            "use_cases": [
                "Long-running operations",
                "Multi-step workflows",
                "Error recovery",
                "State persistence",
            ],
            "confidence": 0.95,
            "domains": ["state_management", "workflow"],
            "pattern_types": ["execution", "state_machine"],
        },
        {
            "type": "execution",
            "name": "Async Event Bus Communication",
            "content": "ONEX Pattern: Event-driven communication via Kafka/Redpanda. Producer publishes events with correlation ID, consumer subscribes with group ID, schema validation with Pydantic, DLQ for failed messages, idempotency tracking.",
            "node_types": ["effect", "orchestrator"],
            "use_cases": [
                "Service integration",
                "Event-driven architecture",
                "Async workflows",
                "Message queuing",
            ],
            "confidence": 0.95,
            "domains": ["event_bus", "messaging"],
            "pattern_types": ["execution", "async_communication"],
        },
        {
            "type": "execution",
            "name": "Error Handling & Recovery",
            "content": "ONEX Pattern: Robust error handling with retry logic. Try-except blocks, exponential backoff retry, circuit breaker pattern, fallback strategies for graceful degradation, detailed error context capture.",
            "node_types": ["effect", "compute", "reducer", "orchestrator"],
            "use_cases": [
                "External API calls",
                "Database operations",
                "Network resilience",
                "Service reliability",
            ],
            "confidence": 0.95,
            "domains": ["reliability", "error_handling"],
            "pattern_types": ["execution", "error_handling"],
        },
        {
            "type": "execution",
            "name": "Quality Gates Validation",
            "content": "ONEX Pattern: Multi-stage quality validation. Input validation before processing, process validation during execution, output validation before returning, quality scoring 0.0-1.0, ONEX compliance checking.",
            "node_types": ["compute", "reducer"],
            "use_cases": [
                "Code quality assessment",
                "Data validation",
                "Compliance checking",
                "Production readiness",
            ],
            "confidence": 0.93,
            "domains": ["quality_assurance", "validation"],
            "pattern_types": ["execution", "quality_gates"],
        },
        {
            "type": "execution",
            "name": "Performance Threshold Checking",
            "content": "ONEX Pattern: Performance monitoring with thresholds. Baseline establishment, metric collection for timing and resources, threshold checking against defined limits, alert generation on violations, trend analysis over time.",
            "node_types": ["effect", "compute", "orchestrator"],
            "use_cases": [
                "Performance monitoring",
                "SLA compliance",
                "Resource optimization",
                "Alert generation",
            ],
            "confidence": 0.92,
            "domains": ["performance", "monitoring"],
            "pattern_types": ["execution", "performance_monitoring"],
        },
        {
            "type": "execution",
            "name": "Multi-Agent Coordination",
            "content": "ONEX Pattern: Parallel agent execution with dependencies. Agent registry with capabilities, task decomposition into subtasks, parallel dispatch for independent tasks, dependency tracking, result aggregation.",
            "node_types": ["orchestrator"],
            "use_cases": [
                "Parallel development",
                "Multi-agent systems",
                "Task orchestration",
                "Agent collaboration",
            ],
            "confidence": 0.93,
            "domains": ["agent_coordination", "orchestration"],
            "pattern_types": ["execution", "multi_agent"],
        },
        {
            "type": "execution",
            "name": "RAG Intelligence Integration",
            "content": "ONEX Pattern: Retrieval-Augmented Generation for context-aware intelligence. Vector search with Qdrant, semantic analysis for concepts/themes, context aggregation from multiple sources, confidence scoring, query caching.",
            "node_types": ["effect", "compute"],
            "use_cases": [
                "Pattern matching",
                "Code search",
                "Documentation retrieval",
                "Intelligent recommendations",
            ],
            "confidence": 0.94,
            "domains": ["rag", "intelligence"],
            "pattern_types": ["execution", "rag_integration"],
        },
        {
            "type": "execution",
            "name": "Contract-Based Communication",
            "content": "ONEX Pattern: Type-safe communication with Pydantic contracts. Contract definition for all I/O, automatic validation, Python type hints, version support, detailed validation errors.",
            "node_types": ["effect", "compute", "reducer", "orchestrator"],
            "use_cases": [
                "API communication",
                "Data validation",
                "Type safety",
                "Service contracts",
            ],
            "confidence": 0.95,
            "domains": ["contracts", "validation"],
            "pattern_types": ["execution", "contract_based"],
        },
        {
            "type": "execution",
            "name": "Workflow Orchestration",
            "content": "ONEX Pattern: Complex workflow execution with steps. Step definition with inputs/outputs, sequential execution, conditional branching, checkpointing between steps, rollback on failure.",
            "node_types": ["orchestrator"],
            "use_cases": [
                "Data processing pipelines",
                "Business workflows",
                "CI/CD automation",
                "ETL processes",
            ],
            "confidence": 0.94,
            "domains": ["orchestration", "workflow"],
            "pattern_types": ["execution", "workflow"],
        },
        {
            "type": "execution",
            "name": "Data Pipeline Processing",
            "content": "ONEX Pattern: Stream processing with transformation stages. Pipeline stages for transformations, batch processing, backpressure handling, error isolation per item, throughput and latency metrics.",
            "node_types": ["compute", "reducer"],
            "use_cases": [
                "Data transformation",
                "ETL pipelines",
                "Stream processing",
                "Batch operations",
            ],
            "confidence": 0.92,
            "domains": ["data_pipeline", "stream_processing"],
            "pattern_types": ["execution", "data_pipeline"],
        },
    ]

    logger.info(f"Defined {len(patterns)} ONEX execution patterns")
    return patterns


async def generate_embedding(text: str, client: httpx.AsyncClient) -> List[float]:
    """Generate embedding for text."""
    try:
        response = await client.post(
            f"{EMBEDDING_MODEL_URL}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": text},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["embedding"]
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise


async def index_patterns_to_qdrant(
    patterns: List[Dict[str, Any]],
    qdrant_client: QdrantClient,
    ollama_client: httpx.AsyncClient,
    dry_run: bool = False,
) -> Dict[str, int]:
    """Index patterns to Qdrant archon_vectors collection."""
    logger.info(f"Indexing {len(patterns)} patterns to Qdrant...")

    stats = {"total_patterns": len(patterns), "successful": 0, "failed": 0}
    batch = []
    point_id = int(datetime.utcnow().timestamp() * 1000)

    for idx, pattern in enumerate(patterns):
        try:
            embedding_text = pattern.get("content", "")
            if not embedding_text:
                logger.warning(f"Skipping pattern {pattern.get('name')} - no content")
                stats["failed"] += 1
                continue

            embedding = await generate_embedding(embedding_text, ollama_client)

            payload = {
                "pattern_type": pattern.get("type"),
                "pattern_name": pattern.get("name"),
                "content_preview": embedding_text[:500],
                "absolute_path": pattern.get("file_path", ""),
                "relative_path": pattern.get("name", ""),
                "file_type": pattern.get("file_type", ""),
                "project_name": pattern.get("project_name", ""),
                "project_root": str(OMNICLAUDE_PATH),
                "onex_type": pattern.get("node_type", "general"),
                "onex_compliance": pattern.get("confidence", 0.7),
                "quality_score": pattern.get("confidence", 0.7),
                "concepts": pattern.get("use_cases", []),
                "themes": pattern.get("domains", []),
                "domains": pattern.get("domains", []),
                "pattern_types": pattern.get("pattern_types", []),
                "indexed_at": datetime.utcnow().isoformat() + "Z",
                "last_modified": datetime.utcnow().isoformat() + "Z",
                "node_types": pattern.get("node_types", []),
                "use_cases": pattern.get("use_cases", []),
                "pattern_confidence": pattern.get("confidence", 0.7),
                "file_hash": (
                    hashlib.sha256(embedding_text.encode()).hexdigest()
                    if embedding_text
                    else ""
                ),
            }

            point = PointStruct(id=point_id, vector=embedding, payload=payload)
            batch.append(point)
            point_id += 1

            if len(batch) >= BATCH_SIZE:
                if not dry_run:
                    qdrant_client.upsert(collection_name=COLLECTION, points=batch)
                stats["successful"] += len(batch)
                batch = []

            if (idx + 1) % PROGRESS_INTERVAL == 0:
                logger.info(
                    f"Progress: {idx + 1}/{len(patterns)} patterns processed..."
                )

        except Exception as e:
            logger.error(f"Failed to index pattern {pattern.get('name')}: {e}")
            stats["failed"] += 1
            continue

    if batch:
        if not dry_run:
            qdrant_client.upsert(collection_name=COLLECTION, points=batch)
        stats["successful"] += len(batch)

    logger.info(f"Indexing complete: {stats}")
    return stats


async def ingest_patterns(
    limit: Optional[int] = None, dry_run: bool = False, verbose: bool = False
) -> int:
    """Main pattern ingestion orchestrator."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("=" * 70)
    logger.info("PATTERN INGESTION - ARCHON INTELLIGENCE")
    logger.info("=" * 70)
    logger.info(f"Source: {OMNICLAUDE_PATH}")
    logger.info(f"Destination: Qdrant {QDRANT_URL} / {COLLECTION}")
    logger.info(f"Embedding model: {EMBEDDING_MODEL}")
    logger.info(f"Dry run mode: {dry_run}")
    if limit:
        logger.info(f"Code pattern limit: {limit}")
    logger.info("=" * 70)

    try:
        logger.info("Initializing clients...")
        ollama_client = httpx.AsyncClient()
        qdrant_client = QdrantClient(url=QDRANT_URL)

        try:
            collections = qdrant_client.get_collections()
            if COLLECTION not in [c.name for c in collections.collections]:
                logger.error(f"Collection {COLLECTION} does not exist in Qdrant")
                return 1
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            return 1

        logger.info("=" * 70)
        logger.info("PHASE 1: EXTRACTING CODE PATTERNS")
        logger.info("=" * 70)
        code_patterns = extract_code_patterns(OMNICLAUDE_PATH, limit=limit)

        logger.info("=" * 70)
        logger.info("PHASE 2: DEFINING EXECUTION PATTERNS")
        logger.info("=" * 70)
        execution_patterns = extract_execution_patterns()

        all_patterns = code_patterns + execution_patterns
        logger.info(f"Total patterns: {len(all_patterns)}")

        logger.info("=" * 70)
        logger.info("PHASE 3: GENERATING EMBEDDINGS & INDEXING")
        logger.info("=" * 70)

        stats = await index_patterns_to_qdrant(
            all_patterns, qdrant_client, ollama_client, dry_run=dry_run
        )

        # Close Ollama client
        await ollama_client.aclose()

        logger.info("=" * 70)
        logger.info("FINAL SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Code patterns: {len(code_patterns)}")
        logger.info(f"Execution patterns: {len(execution_patterns)}")
        logger.info(f"Total: {stats['total_patterns']}")
        logger.info(f"Successful: {stats['successful']}")
        logger.info(f"Failed: {stats['failed']}")
        logger.info("=" * 70)

        if stats["failed"] == 0:
            logger.info("[SUCCESS] All patterns indexed successfully!")
            return 0
        elif stats["successful"] > 0:
            logger.warning(
                f"[WARNING] Partial success: {stats['successful']} indexed, {stats['failed']} failed"
            )
            return 1
        else:
            logger.error("[ERROR] All patterns failed to index")
            return 1

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=verbose)
        return 1


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Pattern ingestion script for Archon Intelligence"
    )
    parser.add_argument(
        "--limit", type=int, help="Limit number of code patterns to extract"
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    return parser.parse_args()


async def main_async() -> int:
    """Async main entry point."""
    args = parse_args()

    if not OMNICLAUDE_PATH.exists():
        print(
            f"Error: Omniclaude path does not exist: {OMNICLAUDE_PATH}", file=sys.stderr
        )
        return 1

    return await ingest_patterns(
        limit=args.limit, dry_run=args.dry_run, verbose=args.verbose
    )


def main() -> int:
    """Main entry point."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
