# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for handler_chunk_classifier — v1 deterministic classification.

Test coverage:
    - One test per classification type (7 rules)
    - Priority ordering: higher-priority rule wins on ambiguous content
    - Replay safety: same input always produces same output
    - Fingerprint determinism: content_fingerprint stable across calls
    - Version hash correctness: changes with source_ref or source_version
    - Tag extraction: all 6 tag types verified
    - Empty input: empty raw_chunks returns empty classified_chunks

Ticket: OMN-2391
"""

from __future__ import annotations

import hashlib
import json

from omniintelligence.nodes.node_chunk_classifier_compute.handlers.handler_chunk_classifier import (
    RULE_VERSION,
    _classify_chunk_v1,
    extract_tags,
    handle_chunk_classify,
)
from omniintelligence.nodes.node_chunk_classifier_compute.models.enum_context_item_type import (
    EnumContextItemType,
)
from omniintelligence.nodes.node_chunk_classifier_compute.models.model_chunk_classify_input import (
    ModelChunkClassifyInput,
    ModelRawChunkRef,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_input(
    chunks: list[ModelRawChunkRef],
    source_ref: str = "docs/CLAUDE.md",
    crawl_scope: str = "omninode/omniintelligence",
    source_version: str | None = "abc123",
    doc_type: str = "general_markdown",
    correlation_id: str | None = "test-corr-01",
) -> ModelChunkClassifyInput:
    return ModelChunkClassifyInput(
        source_ref=source_ref,
        crawl_scope=crawl_scope,
        source_version=source_version,
        doc_type=doc_type,
        raw_chunks=tuple(chunks),
        correlation_id=correlation_id,
    )


def _make_chunk(
    content: str,
    section_heading: str | None = None,
    has_code_fence: bool = False,
    code_fence_language: str | None = None,
) -> ModelRawChunkRef:
    return ModelRawChunkRef(
        content=content,
        section_heading=section_heading,
        has_code_fence=has_code_fence,
        code_fence_language=code_fence_language,
    )


# ---------------------------------------------------------------------------
# Classification rule tests (7 rules)
# ---------------------------------------------------------------------------


class TestClassifyApiConstraint:
    """Priority 1: API_CONSTRAINT."""

    def test_https_url(self) -> None:
        chunk = _make_chunk("Connect to https://kafka.example.com:9092")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.API_CONSTRAINT
        )

    def test_wss_url(self) -> None:
        chunk = _make_chunk("Stream via wss://events.example.com/ws")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.API_CONSTRAINT
        )

    def test_port_pattern(self) -> None:
        chunk = _make_chunk("The broker listens on :9092 by default.")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.API_CONSTRAINT
        )

    def test_host_equals(self) -> None:
        chunk = _make_chunk("Set HOST=kafka.local in your environment.")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.API_CONSTRAINT
        )

    def test_kafka_bootstrap_servers(self) -> None:
        chunk = _make_chunk("KAFKA_BOOTSTRAP_SERVERS=192.168.86.200:29092")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.API_CONSTRAINT
        )


class TestClassifyConfigNote:
    """Priority 2: CONFIG_NOTE."""

    def test_source_env(self) -> None:
        chunk = _make_chunk("Run source .env before starting the service.")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.CONFIG_NOTE
        )

    def test_postgres_prefix(self) -> None:
        chunk = _make_chunk(
            "POSTGRES_HOST and POSTGRES_PORT must match docker-compose."
        )
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.CONFIG_NOTE
        )

    def test_database_url(self) -> None:
        chunk = _make_chunk("Set DATABASE_URL in your .env file for local development.")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.CONFIG_NOTE
        )

    def test_environment_variable(self) -> None:
        chunk = _make_chunk("This environment variable controls feature flags.")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.CONFIG_NOTE
        )

    def test_aws_prefix(self) -> None:
        chunk = _make_chunk("Configure AWS_REGION and AWS_ACCESS_KEY_ID in secrets.")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.CONFIG_NOTE
        )

    def test_word_host_pattern(self) -> None:
        chunk = _make_chunk("REDIS_HOST must point to the cluster endpoint.")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.CONFIG_NOTE
        )


class TestClassifyRule:
    """Priority 3: RULE."""

    def test_must(self) -> None:
        chunk = _make_chunk("You must use frozen=True for all event models.")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.RULE
        )

    def test_never(self) -> None:
        chunk = _make_chunk("Never block the hook thread on Kafka acks.")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.RULE
        )

    def test_critical_colon(self) -> None:
        chunk = _make_chunk("CRITICAL: Do not commit secrets to git.")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.RULE
        )

    def test_non_negotiable(self) -> None:
        chunk = _make_chunk("This is NON-NEGOTIABLE — schemas may not be loosened.")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.RULE
        )

    def test_invariant(self) -> None:
        chunk = _make_chunk(
            "DETERMINISM INVARIANT: Same input always produces same output."
        )
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.RULE
        )


class TestClassifyFailurePattern:
    """Priority 4: FAILURE_PATTERN."""

    def test_pitfall(self) -> None:
        chunk = _make_chunk("Common pitfall: using datetime.now() in event models.")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.FAILURE_PATTERN
        )

    def test_avoid(self) -> None:
        chunk = _make_chunk("Avoid calling sync code from async handlers.")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.FAILURE_PATTERN
        )

    def test_common_mistake(self) -> None:
        chunk = _make_chunk("A common mistake is to skip the token estimation step.")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.FAILURE_PATTERN
        )

    def test_gotcha_heading(self) -> None:
        chunk = _make_chunk(
            "Heading-driven classification applies here.",
            section_heading="Known Gotchas",
        )
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.FAILURE_PATTERN
        )

    def test_anti_pattern(self) -> None:
        chunk = _make_chunk("This is an anti-pattern that causes production outages.")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.FAILURE_PATTERN
        )


class TestClassifyExample:
    """Priority 5: EXAMPLE."""

    def test_example_colon_with_code_fence(self) -> None:
        content = "Example:\n```python\nresult = handle_chunk_classify(input_data)\n```"
        chunk = _make_chunk(content, has_code_fence=True)
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.EXAMPLE
        )

    def test_example_heading(self) -> None:
        chunk = _make_chunk(
            "Here is a code snippet showing usage.",
            section_heading="Usage Examples",
        )
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.EXAMPLE
        )

    def test_how_to_heading(self) -> None:
        chunk = _make_chunk(
            "Follow these steps to configure the node.",
            section_heading="How to Configure",
        )
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.EXAMPLE
        )

    def test_usage_heading(self) -> None:
        chunk = _make_chunk(
            "Call the handler with the input model.",
            section_heading="Basic Usage",
        )
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.EXAMPLE
        )


class TestClassifyRepoMap:
    """Priority 6: REPO_MAP."""

    def test_tree_branch_char(self) -> None:
        chunk = _make_chunk("omniintelligence/\n├── src/\n└── tests/")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.REPO_MAP
        )

    def test_tree_end_char(self) -> None:
        chunk = _make_chunk("└── handler_chunk_classifier.py")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.REPO_MAP
        )

    def test_repo_map_heading(self) -> None:
        chunk = _make_chunk(
            "The project is organized as follows.",
            section_heading="Repository Map",
        )
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.REPO_MAP
        )

    def test_directory_structure_heading(self) -> None:
        chunk = _make_chunk(
            "Directory listing for reference.",
            section_heading="Directory Structure",
        )
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.REPO_MAP
        )


class TestClassifyDocExcerpt:
    """Priority 7: DOC_EXCERPT (fallback)."""

    def test_plain_prose(self) -> None:
        chunk = _make_chunk(
            "This section describes the overall architecture of the ingestion pipeline."
        )
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.DOC_EXCERPT
        )

    def test_plain_prose_with_heading(self) -> None:
        chunk = _make_chunk(
            "The chunker splits documents into semantic units for downstream embedding.",
            section_heading="Overview",
        )
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.DOC_EXCERPT
        )

    def test_empty_content(self) -> None:
        chunk = _make_chunk("")
        assert (
            _classify_chunk_v1(
                chunk.content, chunk.section_heading, chunk.has_code_fence
            )
            == EnumContextItemType.DOC_EXCERPT
        )


# ---------------------------------------------------------------------------
# Priority ordering tests
# ---------------------------------------------------------------------------


class TestPriorityOrdering:
    """Verify higher-priority rules win on ambiguous content."""

    def test_api_constraint_beats_config_note(self) -> None:
        """Content matching both API_CONSTRAINT and CONFIG_NOTE → API_CONSTRAINT."""
        # Has a port pattern (API_CONSTRAINT priority 1) AND POSTGRES_ (CONFIG_NOTE priority 2)
        content = "POSTGRES_HOST=db.local listens on :5432"
        result = _classify_chunk_v1(content, None, False)
        assert result == EnumContextItemType.API_CONSTRAINT

    def test_api_constraint_beats_rule(self) -> None:
        """API_CONSTRAINT beats RULE."""
        content = "You must use https://api.example.com as the base URL."
        result = _classify_chunk_v1(content, None, False)
        assert result == EnumContextItemType.API_CONSTRAINT

    def test_config_note_beats_rule(self) -> None:
        """CONFIG_NOTE beats RULE when no API_CONSTRAINT present."""
        content = "DATABASE_URL must be set in the .env file."
        result = _classify_chunk_v1(content, None, False)
        # DATABASE_URL matches CONFIG_NOTE (priority 2) first
        assert result == EnumContextItemType.CONFIG_NOTE

    def test_rule_beats_failure_pattern(self) -> None:
        """RULE beats FAILURE_PATTERN on content with both triggers."""
        # "Do not" matches RULE (priority 3), "avoid" matches FAILURE_PATTERN (priority 4)
        content = "Do not use async without await. Avoid fire-and-forget patterns."
        # "Do not" → RULE wins
        result = _classify_chunk_v1(content, None, False)
        assert result == EnumContextItemType.RULE

    def test_failure_pattern_beats_example(self) -> None:
        """FAILURE_PATTERN beats EXAMPLE."""
        # "pitfall" (priority 4) beats "example" heading (priority 5)
        content = "Example: This is a pitfall to watch out for."
        heading = "Usage Example"
        result = _classify_chunk_v1(content, heading, True)
        assert result == EnumContextItemType.FAILURE_PATTERN

    def test_example_beats_repo_map(self) -> None:
        """EXAMPLE beats REPO_MAP when both match."""
        # "Example:" + code fence (priority 5) beats tree chars (priority 6)
        content = "Example:\n```\n├── src/\n```"
        result = _classify_chunk_v1(content, None, True)
        assert result == EnumContextItemType.EXAMPLE


# ---------------------------------------------------------------------------
# Replay safety tests
# ---------------------------------------------------------------------------


class TestReplaySafety:
    """Same input always produces same output."""

    def test_classify_deterministic(self) -> None:
        """Calling handle_chunk_classify twice with same input yields identical output."""
        chunks = [
            _make_chunk("You must use frozen=True for all event models."),
            _make_chunk("Connect to https://kafka.example.com:9092"),
            _make_chunk("This section describes the pipeline overview."),
        ]
        input_data = _make_input(chunks)
        result1 = handle_chunk_classify(input_data)
        result2 = handle_chunk_classify(input_data)

        assert result1.total_chunks == result2.total_chunks
        for c1, c2 in zip(
            result1.classified_chunks, result2.classified_chunks, strict=True
        ):
            assert c1.item_type == c2.item_type
            assert c1.content_fingerprint == c2.content_fingerprint
            assert c1.version_hash == c2.version_hash
            assert c1.tags == c2.tags

    def test_rule_version_propagated(self) -> None:
        """rule_version must equal RULE_VERSION constant on every chunk."""
        chunks = [
            _make_chunk("The pipeline processes documents in batch."),
            _make_chunk("You must configure Kafka before starting."),
        ]
        result = handle_chunk_classify(_make_input(chunks))
        for chunk in result.classified_chunks:
            assert chunk.rule_version == RULE_VERSION


# ---------------------------------------------------------------------------
# Fingerprint determinism tests
# ---------------------------------------------------------------------------


class TestFingerprintDeterminism:
    """SHA-256 fingerprints are stable and correct."""

    def test_content_fingerprint_stable(self) -> None:
        """Same content always produces same fingerprint."""
        content = "The ingestion pipeline processes documents in stages."
        chunk = _make_chunk(content)
        result = handle_chunk_classify(_make_input([chunk]))
        classified = result.classified_chunks[0]

        # Recompute manually
        normalized = " ".join(content.split())
        expected = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        assert classified.content_fingerprint == expected

    def test_content_fingerprint_whitespace_insensitive(self) -> None:
        """Whitespace normalization: extra spaces don't change fingerprint."""
        content_a = "The pipeline  processes    documents."
        content_b = "The pipeline processes documents."
        result_a = handle_chunk_classify(_make_input([_make_chunk(content_a)]))
        result_b = handle_chunk_classify(_make_input([_make_chunk(content_b)]))
        assert (
            result_a.classified_chunks[0].content_fingerprint
            == result_b.classified_chunks[0].content_fingerprint
        )

    def test_version_hash_changes_with_source_version(self) -> None:
        """version_hash differs when source_version changes."""
        chunk = _make_chunk("The pipeline processes documents.")
        result_v1 = handle_chunk_classify(
            _make_input([chunk], source_version="sha1abc")
        )
        result_v2 = handle_chunk_classify(
            _make_input([chunk], source_version="sha2def")
        )
        assert (
            result_v1.classified_chunks[0].version_hash
            != result_v2.classified_chunks[0].version_hash
        )

    def test_version_hash_changes_with_source_ref(self) -> None:
        """version_hash differs when source_ref changes."""
        chunk = _make_chunk("The pipeline processes documents.")
        result_a = handle_chunk_classify(_make_input([chunk], source_ref="docs/a.md"))
        result_b = handle_chunk_classify(_make_input([chunk], source_ref="docs/b.md"))
        assert (
            result_a.classified_chunks[0].version_hash
            != result_b.classified_chunks[0].version_hash
        )

    def test_version_hash_structure(self) -> None:
        """version_hash equals sha256(json({content_fp, source_ref, source_version}))."""
        content = "The pipeline processes documents in batch."
        chunk = _make_chunk(content)
        source_ref = "docs/CLAUDE.md"
        source_version = "abc123"

        result = handle_chunk_classify(
            _make_input([chunk], source_ref=source_ref, source_version=source_version)
        )
        classified = result.classified_chunks[0]

        # Recompute manually
        normalized = " ".join(content.split())
        content_fp = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        payload = json.dumps(
            {
                "content_fingerprint": content_fp,
                "source_ref": source_ref,
                "source_version": source_version,
            },
            sort_keys=True,
        )
        expected_version_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        assert classified.content_fingerprint == content_fp
        assert classified.version_hash == expected_version_hash


# ---------------------------------------------------------------------------
# Tag extraction tests
# ---------------------------------------------------------------------------


class TestTagExtraction:
    """Verify all 6 tag types are extracted correctly."""

    def test_source_tag_always_present(self) -> None:
        chunk = _make_chunk("Some content.")
        result = handle_chunk_classify(_make_input([chunk], source_ref="docs/api.md"))
        tags = result.classified_chunks[0].tags
        assert "source:docs/api.md" in tags

    def test_section_tag_from_heading(self) -> None:
        chunk = _make_chunk("Some content.", section_heading="API Reference")
        result = handle_chunk_classify(_make_input([chunk]))
        tags = result.classified_chunks[0].tags
        assert "section:api-reference" in tags

    def test_section_tag_absent_without_heading(self) -> None:
        chunk = _make_chunk("Some content.", section_heading=None)
        result = handle_chunk_classify(_make_input([chunk]))
        tags = result.classified_chunks[0].tags
        assert not any(t.startswith("section:") for t in tags)

    def test_repo_tag_from_crawl_scope(self) -> None:
        chunk = _make_chunk("Some content.")
        result = handle_chunk_classify(
            _make_input([chunk], crawl_scope="omninode/omniintelligence")
        )
        tags = result.classified_chunks[0].tags
        assert "repo:omniintelligence" in tags

    def test_lang_tag_from_code_fence(self) -> None:
        chunk = _make_chunk(
            "```python\nresult = 1 + 1\n```",
            has_code_fence=True,
            code_fence_language="python",
        )
        result = handle_chunk_classify(_make_input([chunk]))
        tags = result.classified_chunks[0].tags
        assert "lang:python" in tags

    def test_lang_tag_absent_without_fence(self) -> None:
        chunk = _make_chunk("Plain text.", has_code_fence=False)
        result = handle_chunk_classify(_make_input([chunk]))
        tags = result.classified_chunks[0].tags
        assert not any(t.startswith("lang:") for t in tags)

    def test_svc_tag_for_known_service(self) -> None:
        chunk = _make_chunk(
            "The omniintelligence service handles embedding generation."
        )
        result = handle_chunk_classify(_make_input([chunk]))
        tags = result.classified_chunks[0].tags
        assert "svc:omniintelligence" in tags

    def test_svc_tag_absent_for_unknown_service(self) -> None:
        chunk = _make_chunk("Some third-party service handles this.")
        result = handle_chunk_classify(_make_input([chunk]))
        tags = result.classified_chunks[0].tags
        assert not any(t.startswith("svc:") for t in tags)

    def test_doctype_tag(self) -> None:
        chunk = _make_chunk("Some content.")
        result = handle_chunk_classify(_make_input([chunk], doc_type="claude_md"))
        tags = result.classified_chunks[0].tags
        assert "doctype:claude_md" in tags

    def test_tags_are_sorted_and_unique(self) -> None:
        chunk = _make_chunk(
            "omniintelligence docs.",
            section_heading="Overview",
            has_code_fence=True,
            code_fence_language="python",
        )
        result = handle_chunk_classify(_make_input([chunk]))
        tags = result.classified_chunks[0].tags
        assert tags == tuple(sorted(set(tags)))


# ---------------------------------------------------------------------------
# Output model integrity tests
# ---------------------------------------------------------------------------


class TestOutputModelIntegrity:
    """Verify output model fields are correctly populated."""

    def test_empty_chunks_returns_empty_output(self) -> None:
        result = handle_chunk_classify(_make_input([]))
        assert result.total_chunks == 0
        assert result.classified_chunks == ()

    def test_total_chunks_matches_input(self) -> None:
        chunks = [_make_chunk(f"Chunk number {i}.") for i in range(5)]
        result = handle_chunk_classify(_make_input(chunks))
        assert result.total_chunks == 5
        assert len(result.classified_chunks) == 5

    def test_source_ref_propagated(self) -> None:
        result = handle_chunk_classify(
            _make_input([_make_chunk("content")], source_ref="path/to/doc.md")
        )
        assert result.source_ref == "path/to/doc.md"
        assert result.classified_chunks[0].source_ref == "path/to/doc.md"

    def test_correlation_id_propagated(self) -> None:
        result = handle_chunk_classify(
            _make_input([_make_chunk("content")], correlation_id="corr-xyz")
        )
        assert result.correlation_id == "corr-xyz"
        assert result.classified_chunks[0].correlation_id == "corr-xyz"

    def test_crawl_scope_propagated(self) -> None:
        result = handle_chunk_classify(
            _make_input([_make_chunk("content")], crawl_scope="omninode/docs")
        )
        assert result.classified_chunks[0].crawl_scope == "omninode/docs"

    def test_source_version_propagated(self) -> None:
        result = handle_chunk_classify(
            _make_input([_make_chunk("content")], source_version="sha-deadbeef")
        )
        assert result.classified_chunks[0].source_version == "sha-deadbeef"

    def test_has_code_fence_propagated(self) -> None:
        chunk = _make_chunk("content", has_code_fence=True, code_fence_language="yaml")
        result = handle_chunk_classify(_make_input([chunk]))
        classified = result.classified_chunks[0]
        assert classified.has_code_fence is True
        assert classified.code_fence_language == "yaml"

    def test_character_offsets_propagated(self) -> None:
        chunk = ModelRawChunkRef(
            content="content",
            character_offset_start=100,
            character_offset_end=200,
            token_estimate=42,
        )
        result = handle_chunk_classify(_make_input([chunk]))
        classified = result.classified_chunks[0]
        assert classified.character_offset_start == 100
        assert classified.character_offset_end == 200
        assert classified.token_estimate == 42

    def test_ordering_preserved(self) -> None:
        """Chunk order in output matches input order."""
        chunks = [_make_chunk(f"Content for chunk {i}.") for i in range(10)]
        result = handle_chunk_classify(_make_input(chunks))
        for i, classified in enumerate(result.classified_chunks):
            assert classified.content == f"Content for chunk {i}."

    def test_none_correlation_id(self) -> None:
        result = handle_chunk_classify(
            _make_input([_make_chunk("content")], correlation_id=None)
        )
        assert result.correlation_id is None
        assert result.classified_chunks[0].correlation_id is None


# ---------------------------------------------------------------------------
# extract_tags unit tests
# ---------------------------------------------------------------------------


class TestExtractTagsUnit:
    """Direct unit tests for extract_tags helper."""

    def test_section_heading_slugified(self) -> None:
        # "&" is stripped (non-word char), adjacent spaces collapse to single "-"
        chunk = ModelRawChunkRef(content="x", section_heading="API & REST Endpoints")
        tags = extract_tags(chunk, "docs/api.md", "omninode/api", "design_doc")
        assert "section:api-rest-endpoints" in tags

    def test_repo_from_source_ref_path(self) -> None:
        chunk = ModelRawChunkRef(content="x")
        tags = extract_tags(
            chunk, "/path/to/omniclaude/README.md", "", "general_markdown"
        )
        assert "repo:omniclaude" in tags

    def test_multiple_services_in_content(self) -> None:
        chunk = ModelRawChunkRef(
            content="omniintelligence sends events to omniclaude via Kafka."
        )
        tags = extract_tags(chunk, "docs/arch.md", "omninode/docs", "general_markdown")
        assert "svc:omniintelligence" in tags
        assert "svc:omniclaude" in tags
