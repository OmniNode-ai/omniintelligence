# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""IntentTopic and IntelligenceCommandTopic read their values from node contracts (OMN-21677)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from omniintelligence import topics
from omniintelligence.models.topics import ModelContractTopicReader
from omniintelligence.topics import IntelligenceCommandTopic, IntentTopic

EXPECTED_INTENT_TOPICS: dict[str, str] = {
    "CLAUDE_CODE_REVIEW_COMPLETED": "onex.evt.omniintelligence.claude-code-review-completed.v1",
    "INTENT_DRIFT_DETECTED": "onex.evt.omniintelligence.intent-drift-detected.v1",
    "INTENT_OUTCOME_LABELED": "onex.evt.omniintelligence.intent-outcome-labeled.v1",
    "INTENT_PATTERN_PROMOTED": "onex.evt.omniintelligence.intent-pattern-promoted.v1",
    "LLM_CALL_COMPLETED": "onex.evt.omniintelligence.llm-call-completed.v1",
    "ROUTING_FEEDBACK_PROCESSED": "onex.evt.omniintelligence.routing-feedback-processed.v1",
    "COMPLIANCE_EVALUATED": "onex.evt.omniintelligence.compliance-evaluated.v1",
    "RUN_EVALUATED": "onex.evt.omniintelligence.run-evaluated.v1",
    "PLAN_REVIEW_STRATEGY_RUN_COMPLETED": "onex.evt.omniintelligence.plan-review-strategy-run-completed.v1",
    "PATTERN_LIFECYCLE_TRANSITIONED": "onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1",
    "PATTERN_STORED": "onex.evt.omniintelligence.pattern-stored.v1",
    "PATTERN_DISCOVERED": "onex.evt.pattern.discovered.v1",
    "FINDING_OBSERVED": "onex.evt.review-pairing.finding-observed.v1",
    "FIX_APPLIED": "onex.evt.review-pairing.fix-applied.v1",
    "FINDING_RESOLVED": "onex.evt.review-pairing.finding-resolved.v1",
    "PAIR_CREATED": "onex.evt.review-pairing.pair-created.v1",
    "CODE_ANALYSIS_COMPLETED": "onex.evt.omniintelligence.code-analysis-completed.v1",
    "CODE_ANALYSIS_FAILED": "onex.evt.omniintelligence.code-analysis-failed.v1",
    "CODE_ENTITIES_EXTRACTED_EMBED": "onex.evt.omniintelligence.code-entities-extracted-embed.v1",
}

EXPECTED_COMMAND_TOPICS: dict[str, str] = {
    "CLAUDE_CODE_REVIEW": "onex.cmd.omniintelligence.claude-code-review.v1",
    "CLAUDE_HOOK_EVENT": "onex.cmd.omniintelligence.claude-hook-event.v1",
    "TOOL_CONTENT": "onex.cmd.omniintelligence.tool-content.v1",
    "PATTERN_LEARNING": "onex.cmd.omniintelligence.pattern-learning.v1",
    "COMPLIANCE_EVALUATE": "onex.cmd.omniintelligence.compliance-evaluate.v1",
    "DECISION_RECORDED": "onex.cmd.omniintelligence.decision-recorded.v1",
    "BLOOM_EVAL_RUN": "onex.cmd.omniintelligence.bloom-eval-run.v1",
    "DOCUMENT_INGESTION": "onex.cmd.omniintelligence.document-ingestion.v1",
    "QUALITY_ASSESSMENT": "onex.cmd.omniintelligence.quality-assessment.v1",
    "CRAWL_TICK": "onex.cmd.omnimemory.crawl-tick.v1",
    "CODE_ANALYSIS": "onex.cmd.omniintelligence.code-analysis.v1",
    "CRAWL_REQUESTED": "onex.cmd.omnimemory.crawl-requested.v1",
    "DOCUMENT_INDEXED": "onex.evt.omnimemory.document-indexed.v1",
}

# Members no node contract declares yet; they keep their literal.
STILL_LITERAL: frozenset[str] = frozenset(
    {
        "onex.evt.omniintelligence.episode-boundary.v1",
        "onex.evt.omniintelligence.code-entities-extracted-bridge.v1",
        "onex.cmd.omniintelligence.intent-received.v1",
    }
)


@pytest.mark.unit
@pytest.mark.parametrize(("member", "topic"), sorted(EXPECTED_INTENT_TOPICS.items()))
def test_intent_topic_value_comes_from_its_contract(member: str, topic: str) -> None:
    assert IntentTopic[member].value == topic


@pytest.mark.unit
@pytest.mark.parametrize(("member", "topic"), sorted(EXPECTED_COMMAND_TOPICS.items()))
def test_command_topic_value_comes_from_its_contract(member: str, topic: str) -> None:
    assert IntelligenceCommandTopic[member].value == topic


@pytest.mark.unit
def test_every_member_is_covered_by_a_contract_or_listed_as_literal() -> None:
    members = {m.value for m in IntentTopic} | {
        m.value for m in IntelligenceCommandTopic
    }
    covered = set(EXPECTED_INTENT_TOPICS.values()) | set(
        EXPECTED_COMMAND_TOPICS.values()
    )
    assert members == covered | STILL_LITERAL


@pytest.mark.unit
def test_only_the_listed_topics_remain_literal_in_topics_module() -> None:
    tree = ast.parse(Path(topics.__file__).read_text())
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith("onex.")
    }
    assert literals == STILL_LITERAL


@pytest.mark.unit
def test_reader_resolves_topics_from_event_lists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "pkg_event_list_nodes"
    (root / "node_orchestrator").mkdir(parents=True)
    (root / "__init__.py").write_text("")
    (root / "node_orchestrator" / "contract.yaml").write_text(
        "consumed_events:\n"
        "  - topic: onex.cmd.alpha.work-requested.v1\n"
        "    event_type: WorkRequested\n"
        "published_events:\n"
        "  - topic: onex.evt.alpha.work-finished.v1\n"
        "    event_type: WorkFinished\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    reader = ModelContractTopicReader(nodes_package="pkg_event_list_nodes")

    assert (
        reader.command("node_orchestrator", "work-requested")
        == "onex.cmd.alpha.work-requested.v1"
    )
    assert (
        reader.event("node_orchestrator", "work-finished")
        == "onex.evt.alpha.work-finished.v1"
    )
    with pytest.raises(LookupError, match="declares 0 topics"):
        reader.event("node_orchestrator", "work-requested")


@pytest.mark.unit
def test_reader_event_and_command_fix_the_kind() -> None:
    reader = ModelContractTopicReader()

    assert (
        reader.command("node_claude_hook_event_effect", "claude-hook-event")
        == IntelligenceCommandTopic.CLAUDE_HOOK_EVENT.value
    )
    with pytest.raises(LookupError):
        reader.event("node_claude_hook_event_effect", "claude-hook-event")
