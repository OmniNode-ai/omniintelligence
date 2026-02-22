# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for ChunkClassifierCompute — deterministic chunk type classification.

Classification rules v1 (frozen — first match wins):

  Priority 1 - API_CONSTRAINT:
    URL patterns (http://, https://, ws://), :<port> patterns,
    HOST=, KAFKA_BOOTSTRAP_SERVERS, port-number tables

  Priority 2 - CONFIG_NOTE:
    source .env, POSTGRES_, KAFKA_, env var tables,
    Docker network config patterns

  Priority 3 - RULE:
    "must", "never", "CRITICAL:", "NON-NEGOTIABLE", "PROHIBITED",
    "❌ WRONG:", prohibition lists

  Priority 4 - FAILURE_PATTERN:
    "pitfall", "avoid", "wrong", "❌", "common mistake",
    heading contains "gotcha"

  Priority 5 - EXAMPLE:
    code fence preceded by "Example:", heading contains
    "example" / "usage" / "how to"

  Priority 6 - REPO_MAP:
    "├──", "└──", "│" tree markers,
    heading contains "repository map" / "project layout"

  Priority 7 - DOC_EXCERPT:
    Default fallback (all unmatched chunks)

Tag extraction produces 6 tag types:
  - source_ref (always)
  - section_heading (slugified, if present)
  - repo:{name} (from source_ref or crawl_scope)
  - lang:{language} (from code fence language)
  - svc:{service} (OmniNode service names found in content)
  - doctype:{doc_type}

Fingerprinting:
  - content_fingerprint = sha256(normalized_content)
  - version_hash = sha256(json({content_fingerprint, source_ref, source_version}))

DETERMINISM INVARIANT:
  Rule order is frozen per contract version (v1). A change to rule order or
  trigger strings requires a version bump. Without frozen rule order, promotion
  history is non-replayable.

Ticket: OMN-2391
"""

from __future__ import annotations

import hashlib
import json
import re

from omniintelligence.nodes.node_chunk_classifier_compute.models.enum_context_item_type import (
    EnumContextItemType,
)
from omniintelligence.nodes.node_chunk_classifier_compute.models.model_chunk_classify_input import (
    ModelChunkClassifyInput,
    ModelRawChunkRef,
)
from omniintelligence.nodes.node_chunk_classifier_compute.models.model_chunk_classify_output import (
    ModelChunkClassifyOutput,
)
from omniintelligence.nodes.node_chunk_classifier_compute.models.model_classified_chunk import (
    ModelClassifiedChunk,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RULE_VERSION = "v1"

# Known OmniNode service names for svc: tag extraction
_OMNINODE_SERVICES = frozenset(
    {
        "omniintelligence",
        "omniclaude",
        "omnibase_core",
        "omnibase_infra",
        "omnimemory",
        "omniarchon",
        "omnidash",
    }
)

# ---------------------------------------------------------------------------
# Rule 1: API_CONSTRAINT
# ---------------------------------------------------------------------------

_API_CONSTRAINT_PATTERNS = [
    re.compile(r"https?://"),
    re.compile(r"wss?://"),
    re.compile(r":\d{2,5}\b"),  # :<port> like :9092, :5432, :8080
    re.compile(r"\bHOST\s*="),
    re.compile(r"\bKAFKA_BOOTSTRAP_SERVERS\b"),
    re.compile(r"\bport\s+\d{2,5}\b", re.IGNORECASE),
]


def _is_api_constraint(content: str) -> bool:
    """Return True if content matches API_CONSTRAINT triggers (priority 1)."""
    return any(pattern.search(content) for pattern in _API_CONSTRAINT_PATTERNS)


# ---------------------------------------------------------------------------
# Rule 2: CONFIG_NOTE
# ---------------------------------------------------------------------------

_CONFIG_NOTE_STRINGS = [
    "source .env",
    "POSTGRES_",
    "KAFKA_",
    "docker network",
    "Docker network",
    "env var",
    ".env file",
    "environment variable",
    "DATABASE_URL",
    "REDIS_URL",
    "AWS_",
    "GCP_",
]

_CONFIG_NOTE_PATTERNS = [
    re.compile(r"\b\w+_HOST\b"),
    re.compile(r"\b\w+_PORT\b"),
    re.compile(r"\b\w+_PASSWORD\b"),
    re.compile(r"\b\w+_USER\b"),
    re.compile(r"\bDOCKER_\w+\b"),
]


def _is_config_note(content: str) -> bool:
    """Return True if content matches CONFIG_NOTE triggers (priority 2)."""
    if any(trigger in content for trigger in _CONFIG_NOTE_STRINGS):
        return True
    return any(pattern.search(content) for pattern in _CONFIG_NOTE_PATTERNS)


# ---------------------------------------------------------------------------
# Rule 3: RULE
# ---------------------------------------------------------------------------

_RULE_STRINGS = [
    "must ",
    "Must ",
    "MUST ",
    "never ",
    "Never ",
    "NEVER ",
    "CRITICAL:",
    "NON-NEGOTIABLE",
    "PROHIBITED",
    "❌ WRONG:",
    "❌ DO NOT",
    "Always ensure",
    "always ensure",
    "Do NOT",
    "Do not",
    "invariant",
    "Invariant",
    "INVARIANT",
]


def _is_rule(content: str) -> bool:
    """Return True if content matches RULE triggers (priority 3)."""
    return any(trigger in content for trigger in _RULE_STRINGS)


# ---------------------------------------------------------------------------
# Rule 4: FAILURE_PATTERN
# ---------------------------------------------------------------------------

_FAILURE_PATTERN_STRINGS = [
    "pitfall",
    "Pitfall",
    "PITFALL",
    "avoid ",
    "Avoid ",
    "common mistake",
    "Common mistake",
    "❌",
    "anti-pattern",
    "Anti-pattern",
    "do not use",
    "Do not use",
    "broken",
    "gotcha",
    "Gotcha",
]

_FAILURE_HEADING_PATTERN = re.compile(
    r"gotcha|pitfall|anti.pattern|avoid|wrong", re.IGNORECASE
)


def _is_failure_pattern(content: str, heading: str | None) -> bool:
    """Return True if content matches FAILURE_PATTERN triggers (priority 4)."""
    for trigger in _FAILURE_PATTERN_STRINGS:
        if trigger in content:
            return True
    if heading and _FAILURE_HEADING_PATTERN.search(heading):
        return True
    return False


# ---------------------------------------------------------------------------
# Rule 5: EXAMPLE
# ---------------------------------------------------------------------------

_EXAMPLE_HEADING_PATTERN = re.compile(r"\bexample|usage|how.to\b", re.IGNORECASE)


def _is_example(content: str, heading: str | None, has_code_fence: bool) -> bool:
    """Return True if content matches EXAMPLE triggers (priority 5).

    Triggers:
    - Code fence preceded by "Example:" in the same chunk
    - Section heading contains "example", "usage", or "how to"
    """
    if has_code_fence and re.search(r"Example:", content):
        return True
    if heading and _EXAMPLE_HEADING_PATTERN.search(heading):
        return True
    return False


# ---------------------------------------------------------------------------
# Rule 6: REPO_MAP
# ---------------------------------------------------------------------------

_REPO_MAP_TREE_CHARS = ["├──", "└──", "│   ", "│\t"]
_REPO_MAP_HEADING_PATTERN = re.compile(
    r"repository.map|project.layout|directory.structure|file.structure",
    re.IGNORECASE,
)


def _is_repo_map(content: str, heading: str | None) -> bool:
    """Return True if content matches REPO_MAP triggers (priority 6)."""
    for tree_char in _REPO_MAP_TREE_CHARS:
        if tree_char in content:
            return True
    if heading and _REPO_MAP_HEADING_PATTERN.search(heading):
        return True
    return False


# ---------------------------------------------------------------------------
# Rule set dispatcher (v1, frozen)
# ---------------------------------------------------------------------------

_CLASSIFY_V1_RULES: tuple[tuple[EnumContextItemType, ...], ...] = (
    # The tuple structure is (type,) with the check inline in _classify_chunk_v1
    # This tuple is ordered and frozen — do not reorder.
    (EnumContextItemType.API_CONSTRAINT,),
    (EnumContextItemType.CONFIG_NOTE,),
    (EnumContextItemType.RULE,),
    (EnumContextItemType.FAILURE_PATTERN,),
    (EnumContextItemType.EXAMPLE,),
    (EnumContextItemType.REPO_MAP,),
    (EnumContextItemType.DOC_EXCERPT,),
)


def _classify_chunk_v1(
    content: str,
    heading: str | None,
    has_code_fence: bool,
) -> EnumContextItemType:
    """Apply v1 classification rules in priority order. First match wins.

    Rule order is frozen — do not reorder. Changes require version bump.
    """
    if _is_api_constraint(content):
        return EnumContextItemType.API_CONSTRAINT
    if _is_config_note(content):
        return EnumContextItemType.CONFIG_NOTE
    if _is_rule(content):
        return EnumContextItemType.RULE
    if _is_failure_pattern(content, heading):
        return EnumContextItemType.FAILURE_PATTERN
    if _is_example(content, heading, has_code_fence):
        return EnumContextItemType.EXAMPLE
    if _is_repo_map(content, heading):
        return EnumContextItemType.REPO_MAP
    return EnumContextItemType.DOC_EXCERPT


# ---------------------------------------------------------------------------
# Tag extraction
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Convert heading text to a lowercase hyphenated slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-")


def _extract_repo_name(source_ref: str, crawl_scope: str) -> str | None:
    """Extract repo name from source_ref or crawl_scope."""
    # crawl_scope format: "org/repo"
    if "/" in crawl_scope:
        return crawl_scope.split("/")[-1]
    # source_ref might be an absolute path like /path/to/repo/file.md
    parts = source_ref.replace("\\", "/").split("/")
    for part in reversed(parts):
        if part and "." not in part:
            return part
    return None


def _extract_service_tags(content: str) -> list[str]:
    """Find OmniNode service names mentioned in content."""
    tags = []
    content_lower = content.lower()
    for svc in _OMNINODE_SERVICES:
        if svc.lower() in content_lower:
            tags.append(f"svc:{svc}")
    return sorted(tags)


def extract_tags(
    chunk: ModelRawChunkRef,
    source_ref: str,
    crawl_scope: str,
    doc_type: str,
) -> tuple[str, ...]:
    """Extract 6 tag types from a chunk.

    Tags:
    - source_ref: always included
    - section:{slugified_heading}: if heading present
    - repo:{name}: from crawl_scope or source_ref
    - lang:{language}: if code fence language present
    - svc:{service}: OmniNode service names found in content
    - doctype:{doc_type}: document class
    """
    tags: list[str] = []

    # 1. source_ref (always)
    tags.append(f"source:{source_ref}")

    # 2. section heading (slugified)
    if chunk.section_heading:
        tags.append(f"section:{_slugify(chunk.section_heading)}")

    # 3. repo name
    repo_name = _extract_repo_name(source_ref, crawl_scope)
    if repo_name:
        tags.append(f"repo:{repo_name}")

    # 4. code fence language
    if chunk.code_fence_language:
        tags.append(f"lang:{chunk.code_fence_language}")

    # 5. OmniNode service names
    tags.extend(_extract_service_tags(chunk.content))

    # 6. doctype
    tags.append(f"doctype:{doc_type}")

    return tuple(sorted(set(tags)))


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------


def _compute_content_fingerprint(content: str) -> str:
    """SHA-256 of normalized content (stable identity)."""
    normalized = " ".join(content.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _compute_version_hash(
    content_fingerprint: str,
    source_ref: str,
    source_version: str | None,
) -> str:
    """SHA-256 of {content_fingerprint, source_ref, source_version}."""
    payload = json.dumps(
        {
            "content_fingerprint": content_fingerprint,
            "source_ref": source_ref,
            "source_version": source_version or "",
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------


def handle_chunk_classify(
    input_data: ModelChunkClassifyInput,
) -> ModelChunkClassifyOutput:
    """Classify raw chunks using v1 deterministic rules.

    Pure function — no I/O, no LLM calls. Same input always produces
    the same output (replay-safe).

    Args:
        input_data: Classification request with source metadata and raw chunks.

    Returns:
        ModelChunkClassifyOutput with classified chunks, fingerprints, and tags.
    """
    classified: list[ModelClassifiedChunk] = []

    for raw in input_data.raw_chunks:
        # Classify by v1 rules
        item_type = _classify_chunk_v1(
            raw.content,
            raw.section_heading,
            raw.has_code_fence,
        )

        # Extract tags
        tags = extract_tags(
            raw,
            input_data.source_ref,
            input_data.crawl_scope,
            input_data.doc_type,
        )

        # Fingerprints
        content_fp = _compute_content_fingerprint(raw.content)
        version_hash = _compute_version_hash(
            content_fp,
            input_data.source_ref,
            input_data.source_version,
        )

        classified.append(
            ModelClassifiedChunk(
                content=raw.content,
                section_heading=raw.section_heading,
                item_type=item_type,
                rule_version=RULE_VERSION,
                tags=tags,
                content_fingerprint=content_fp,
                version_hash=version_hash,
                character_offset_start=raw.character_offset_start,
                character_offset_end=raw.character_offset_end,
                token_estimate=raw.token_estimate,
                has_code_fence=raw.has_code_fence,
                code_fence_language=raw.code_fence_language,
                source_ref=input_data.source_ref,
                crawl_scope=input_data.crawl_scope,
                source_version=input_data.source_version,
                correlation_id=input_data.correlation_id,
            )
        )

    return ModelChunkClassifyOutput(
        classified_chunks=tuple(classified),
        source_ref=input_data.source_ref,
        total_chunks=len(classified),
        correlation_id=input_data.correlation_id,
    )


__all__ = [
    "RULE_VERSION",
    "_classify_chunk_v1",
    "extract_tags",
    "handle_chunk_classify",
]
