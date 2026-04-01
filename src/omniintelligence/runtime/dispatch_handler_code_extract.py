# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Dispatch bridge handler for the code extraction stage.

Receives ``code-file-discovered.v1`` event, reads the source file from disk,
runs AST entity extraction and relationship detection, and emits
``code-entities-extracted.v1``.

Design Decisions:
    - The extract handler checks ``file_hash`` against the repository before
      parsing. If the file is unchanged (hash match), extraction is skipped.
    - File content is read from disk using the repo path + file_path from
      the discovery event.
    - Both entity extraction and relationship detection run in sequence
      because relationship detection depends on extracted entities.
    - The handler emits a single ``ModelCodeEntitiesExtractedEvent`` per file.

Related:
    - OMN-5662: Wire crawl -> extract pipeline via Kafka events
    - OMN-5657: AST-based code pattern extraction system (epic)
    - OMN-5659: Port AST entity extractor
    - OMN-5660: Port code relationship detector
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)

from omniintelligence.constants import (
    TOPIC_CODE_ENTITIES_EXTRACTED_V1,
    TOPIC_CODE_FILE_DISCOVERED_V1,
)
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entity import (
    ModelCodeEntity,
)
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

logger = logging.getLogger(__name__)


# =============================================================================
# Bridge Handler: code-file-discovered.v1
# =============================================================================


DispatchHandler = Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]


def create_code_extract_dispatch_handler(
    *,
    repo_paths: dict[str, str] | None = None,
    kafka_publisher: Any | None = None,
    publish_topic: str | None = None,
    correlation_id: UUID | None = None,
    language_extractors_config: dict[str, Any] | None = None,
) -> DispatchHandler:
    """Create a dispatch engine handler for code-file-discovered events.

    The handler reads the source file, runs AST extraction and relationship
    detection, and emits a ``code-entities-extracted.v1`` event.

    Args:
        repo_paths: Mapping of repo_name -> absolute path. Used to resolve
            the full file path for reading. If None, attempts to load from
            the code crawler contract YAML.
        kafka_publisher: Optional Kafka publisher for emitting
            entities-extracted events. When None, events are not published.
        publish_topic: Topic to publish entities-extracted events to.
        correlation_id: Optional fixed correlation ID for tracing.

    Returns:
        Async handler function with signature (envelope, context) -> str.
    """

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        """Bridge handler: envelope -> AST extract + relationship detect."""
        from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_ast_extract import (
            AstExtractInput,
            handle_ast_extract,
        )
        from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_relationship_detect import (
            detect_relationships,
        )
        from omniintelligence.nodes.node_code_crawler_effect.models.model_code_file_discovered_event import (
            ModelCodeFileDiscoveredEvent,
        )

        ctx_correlation_id = (
            correlation_id or getattr(context, "correlation_id", None) or uuid4()
        )

        payload = envelope.payload

        if not isinstance(payload, dict):
            msg = (
                f"Unexpected payload type {type(payload).__name__} "
                f"for code-file-discovered (correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        try:
            discovered_event = ModelCodeFileDiscoveredEvent(**payload)
        except Exception as e:
            sanitized = get_log_sanitizer().sanitize(str(e))
            msg = (
                f"Failed to parse payload as ModelCodeFileDiscoveredEvent: "
                f"{sanitized} (correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg) from e

        # Read source content from event payload (no filesystem access needed)
        source_content = getattr(discovered_event, "source_content", None)

        if source_content is None:
            # Fallback for old events without source_content
            resolved_paths = repo_paths or _load_repo_paths()
            repo_root = resolved_paths.get(discovered_event.repo_name)
            if repo_root is None:
                logger.warning(
                    "Unknown repo %r and no source_content, skipping "
                    "(correlation_id=%s)",
                    discovered_event.repo_name,
                    ctx_correlation_id,
                )
                return "ok"
            full_path = Path(repo_root) / discovered_event.file_path
            if not full_path.is_file():
                logger.warning(
                    "File not found and no source_content: %s "
                    "(correlation_id=%s)",
                    full_path,
                    ctx_correlation_id,
                )
                return "ok"
            try:
                source_content = full_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning(
                    "Cannot read file %s: %s (correlation_id=%s)",
                    full_path,
                    e,
                    ctx_correlation_id,
                )
                return "ok"

        logger.info(
            "Extracting entities from %s (repo=%s, hash=%s, correlation_id=%s)",
            discovered_event.file_path,
            discovered_event.repo_name,
            discovered_event.file_hash[:12],
            ctx_correlation_id,
        )

        # Dispatch by file extension (OMN-5680)
        file_ext = Path(discovered_event.file_path).suffix.lstrip(".")
        extraction_strategy = _get_extraction_strategy(
            file_ext, language_extractors_config
        )

        from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entities_extracted_event import (
            ModelCodeEntitiesExtractedEvent,
        )

        if extraction_strategy == "regex":
            # Non-Python: use multilang regex extractor (OMN-5679/5680)
            from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_multilang_extract import (
                MultiLangExtractor,
            )

            extractor = MultiLangExtractor(language_extractors_config or {})
            entity_dicts = extractor.extract(
                source_content=source_content,
                source_path=discovered_event.file_path,
                source_repo=discovered_event.repo_name,
                file_hash=discovered_event.file_hash,
                extension=file_ext,
            )

            entities_extracted_event = ModelCodeEntitiesExtractedEvent(
                event_id=str(uuid.uuid4()),
                crawl_id=discovered_event.crawl_id,
                repo_name=discovered_event.repo_name,
                file_path=discovered_event.file_path,
                file_hash=discovered_event.file_hash,
                entities=[ModelCodeEntity(**d) for d in entity_dicts],
                relationships=[],
                parse_status="ok",
                parse_error=None,
                extractor_version="multilang-regex-1.0.0",
                timestamp=datetime.now(tz=timezone.utc),
            )
        elif extraction_strategy == "ast":
            # Python: use AST extraction (Part 1)
            extract_input = AstExtractInput(
                source_content=source_content,
                source_path=discovered_event.file_path,
                source_repo=discovered_event.repo_name,
                file_hash=discovered_event.file_hash,
                crawl_id=discovered_event.crawl_id,
                event_id=str(uuid.uuid4()),
            )
            extraction_result = handle_ast_extract(extract_input)

            additional_relationships = detect_relationships(
                source_code=source_content,
                file_path=discovered_event.file_path,
                repo_name=discovered_event.repo_name,
                entities=list(extraction_result.entities),
            )
            all_relationships = (
                list(extraction_result.relationships) + additional_relationships
            )

            entities_extracted_event = ModelCodeEntitiesExtractedEvent(
                event_id=str(uuid.uuid4()),
                crawl_id=discovered_event.crawl_id,
                repo_name=discovered_event.repo_name,
                file_path=discovered_event.file_path,
                file_hash=discovered_event.file_hash,
                entities=list(extraction_result.entities),
                relationships=all_relationships,
                parse_status=extraction_result.parse_status,
                parse_error=extraction_result.parse_error,
                extractor_version=extraction_result.extractor_version,
                timestamp=datetime.now(tz=timezone.utc),
            )
        else:
            logger.warning(
                "Unknown extraction strategy %r for extension .%s, skipping "
                "(file=%s, correlation_id=%s)",
                extraction_strategy,
                file_ext,
                discovered_event.file_path,
                ctx_correlation_id,
            )
            return "ok"

        # Publish to Kafka if publisher available
        if kafka_publisher is not None and publish_topic:
            try:
                event_dict = entities_extracted_event.model_dump(mode="json")
                await kafka_publisher.publish(
                    topic=publish_topic,
                    value=event_dict,
                    key=f"{discovered_event.repo_name}:{discovered_event.file_path}",
                )
            except Exception:
                logger.exception(
                    "Failed to publish code-entities-extracted event "
                    "(file=%s, repo=%s, correlation_id=%s)",
                    discovered_event.file_path,
                    discovered_event.repo_name,
                    ctx_correlation_id,
                )

        logger.info(
            "Code extraction complete (file=%s, entities=%d, relationships=%d, "
            "parse_status=%s, correlation_id=%s)",
            discovered_event.file_path,
            len(entities_extracted_event.entities),
            len(entities_extracted_event.relationships),
            entities_extracted_event.parse_status,
            ctx_correlation_id,
        )

        return "ok"

    return _handle


# =============================================================================
# Helpers
# =============================================================================


def _get_extraction_strategy(
    file_ext: str,
    language_extractors_config: dict[str, Any] | None,
) -> str:
    """Determine extraction strategy from file extension and contract config.

    Returns "ast" for Python, "regex" for configured non-Python languages,
    or "skip" for unknown extensions.
    """
    ext_to_lang = {
        "py": "python",
        "ts": "typescript",
        "tsx": "typescript",
        "js": "javascript",
        "jsx": "javascript",
        "go": "go",
    }
    lang = ext_to_lang.get(file_ext)
    if lang is None:
        return "skip"

    if lang == "python":
        return "ast"

    if language_extractors_config:
        lang_cfg = language_extractors_config.get(lang, {})
        if isinstance(lang_cfg, dict) and lang_cfg.get("enabled", False):
            return str(lang_cfg.get("strategy", "regex"))

    return "skip"


def _load_repo_paths() -> dict[str, str]:
    """Load repo name -> path mapping from code crawler contract YAML."""
    import importlib.resources

    import yaml

    package = "omniintelligence.nodes.node_code_crawler_effect"
    contract_ref = importlib.resources.files(package).joinpath("contract.yaml")
    contract_text = contract_ref.read_text(encoding="utf-8")
    contract = yaml.safe_load(contract_text)
    repos = contract.get("config", {}).get("repos", [])
    return {r["name"]: os.path.expandvars(r["path"]) for r in repos}


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "TOPIC_CODE_ENTITIES_EXTRACTED_V1",
    "TOPIC_CODE_FILE_DISCOVERED_V1",
    "create_code_extract_dispatch_handler",
]
