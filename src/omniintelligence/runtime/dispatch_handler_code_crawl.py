# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Dispatch bridge handler for the code crawl stage.

Receives ``code-crawl-requested.v1`` command, reads repo configuration from
the ``node_code_crawler_effect`` contract YAML, runs OnexTree generator per
repository, and emits ``code-file-discovered.v1`` per Python file found.

Design Decisions:
    - Repo configuration is read from the contract YAML at handler call time
      (not cached) so that config changes are picked up on next crawl.
    - The handler supports optional ``--repo`` filtering via the command
      payload to crawl a single repository.
    - Disabled repos (``enabled: false``) are skipped.
    - The handler is async because OnexTreeGenerator.generate_tree() is async.

Related:
    - OMN-5662: Wire crawl -> extract pipeline via Kafka events
    - OMN-5657: AST-based code pattern extraction system (epic)
    - OMN-5658: Port OnexTree generator and models
"""

from __future__ import annotations

import importlib.resources
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

import yaml
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)

from omniintelligence.constants import (
    TOPIC_CODE_CRAWL_REQUESTED_V1,
    TOPIC_CODE_FILE_DISCOVERED_V1,
)
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

logger = logging.getLogger(__name__)


# =============================================================================
# Contract config reader
# =============================================================================


def _load_repos_config() -> list[dict[str, Any]]:
    """Load repo configuration from the code crawler contract YAML.

    Returns:
        List of repo config dicts, each with keys: name, path, include,
        exclude, and optionally enabled.
    """
    package = "omniintelligence.nodes.node_code_crawler_effect"
    contract_ref = importlib.resources.files(package).joinpath("contract.yaml")
    contract_text = contract_ref.read_text(encoding="utf-8")
    contract = yaml.safe_load(contract_text)
    return contract.get("config", {}).get("repos", [])


# =============================================================================
# Bridge Handler: code-crawl-requested.v1
# =============================================================================


DispatchHandler = Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]


def create_code_crawl_dispatch_handler(
    *,
    kafka_publisher: Any | None = None,
    publish_topic: str | None = None,
    correlation_id: UUID | None = None,
) -> DispatchHandler:
    """Create a dispatch engine handler for code-crawl-requested commands.

    The handler reads repo configuration from the code crawler contract YAML,
    runs OnexTree generator per repo, and returns discovered file events.
    If a Kafka publisher is provided, each ModelCodeFileDiscoveredEvent is
    published to the ``code-file-discovered.v1`` topic.

    Args:
        kafka_publisher: Optional Kafka publisher for emitting file-discovered
            events. When None, events are returned but not published.
        publish_topic: Topic to publish file-discovered events to.
        correlation_id: Optional fixed correlation ID for tracing.

    Returns:
        Async handler function with signature (envelope, context) -> str.
    """

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        """Bridge handler: envelope -> handle_code_crawl()."""
        from omniintelligence.nodes.node_code_crawler_effect.handlers.handler_onextree_generator import (
            handle_code_crawl,
        )

        ctx_correlation_id = (
            correlation_id or getattr(context, "correlation_id", None) or uuid4()
        )

        payload = envelope.payload

        # Extract optional repo filter from payload
        repo_filter: str | None = None
        if isinstance(payload, dict):
            repo_filter = payload.get("repo")

        # Load repo config from contract YAML
        repos_config = _load_repos_config()

        # Filter disabled repos
        repos_config = [r for r in repos_config if r.get("enabled", True) is not False]

        # Apply optional repo filter
        if repo_filter:
            repos_config = [r for r in repos_config if r["name"] == repo_filter]
            if not repos_config:
                logger.warning(
                    "No matching repo for filter %r (correlation_id=%s)",
                    get_log_sanitizer().sanitize(repo_filter),
                    ctx_correlation_id,
                )
                return "ok"

        crawl_id: str | None = None
        if isinstance(payload, dict):
            crawl_id = payload.get("crawl_id")

        logger.info(
            "Dispatching code-crawl-requested via MessageDispatchEngine "
            "(repos=%d, repo_filter=%s, correlation_id=%s)",
            len(repos_config),
            repo_filter or "all",
            ctx_correlation_id,
        )

        events = await handle_code_crawl(
            repos_config=repos_config,
            crawl_id=crawl_id,
        )

        # Publish each discovered file event to Kafka if publisher available
        if kafka_publisher is not None and publish_topic:
            for event in events:
                try:
                    event_dict = event.model_dump(mode="json")
                    await kafka_publisher.publish(
                        topic=publish_topic,
                        value=event_dict,
                        key=f"{event.repo_name}:{event.file_path}",
                    )
                except Exception:
                    logger.exception(
                        "Failed to publish code-file-discovered event "
                        "(file=%s, repo=%s, correlation_id=%s)",
                        event.file_path,
                        event.repo_name,
                        ctx_correlation_id,
                    )

        logger.info(
            "Code-crawl-requested processed via dispatch engine "
            "(files_discovered=%d, correlation_id=%s)",
            len(events),
            ctx_correlation_id,
        )

        return "ok"

    return _handle


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "TOPIC_CODE_CRAWL_REQUESTED_V1",
    "TOPIC_CODE_FILE_DISCOVERED_V1",
    "create_code_crawl_dispatch_handler",
]
