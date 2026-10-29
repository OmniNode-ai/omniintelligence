# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""OMN-21005: the caller owns the unchanged allowlist and uses core's guard.

The recorded paths come from the guard's omniintelligence allowlist at
c0c49e1240ffaa6db1fe36f74b50c0acd345d7b2. The project locks core 0.47.24,
which predates the ratchet handler, so behavioural probes use an isolated
0.47.41 validator environment without changing the application's lock.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
CALLER = WORKFLOWS / "imperative-contract-guard.yml"
ALLOWLIST = ROOT / ".github/imperative-contract-allowlist.yaml"
ALLOWLIST_PATH = ALLOWLIST.relative_to(ROOT).as_posix()
RECORDED_ALLOWLIST_DIGEST = bytes(
    (
        142,
        100,
        139,
        216,
        32,
        116,
        252,
        23,
        164,
        16,
        15,
        189,
        86,
        145,
        93,
        224,
        146,
        125,
        233,
        241,
        165,
        100,
        219,
        220,
        190,
        142,
        100,
        10,
        193,
        66,
        136,
        34,
    )
)
CORE_SHA_PREFIX = "031148215"
CORE_USES = "OmniNode-ai/omnibase_core/.github/workflows/imperative-contract-guard.yml"
RECORDED_PATHS = [
    "omniintelligence/nodes/node_agent_behavior_eval_compute/handlers/handler_agent_behavior_evaluation.py",
    "omniintelligence/nodes/node_anti_gaming_guardrails_compute/handlers/handler_guardrails.py",
    "omniintelligence/nodes/node_anti_gaming_alerter_effect/handlers/protocols.py",
    "omniintelligence/nodes/node_ast_extraction_compute/handlers/handler_ast_extract.py",
    "omniintelligence/nodes/node_ast_extraction_compute/handlers/handler_deterministic_classify.py",
    "omniintelligence/nodes/node_ast_extraction_compute/handlers/handler_extract_ast.py",
    "omniintelligence/nodes/node_ast_extraction_compute/handlers/handler_multilang_extract.py",
    "omniintelligence/nodes/node_ast_extraction_compute/handlers/handler_quality_score.py",
    "omniintelligence/nodes/node_ast_extraction_compute/handlers/handler_relationship_detect.py",
    "omniintelligence/nodes/node_bloom_eval_orchestrator/handlers/handler_bloom_eval_effect.py",
    "omniintelligence/nodes/node_ci_error_classifier_compute/handlers/handler_classifier.py",
    "omniintelligence/nodes/node_ci_failure_tracker_effect/handlers/handler_streak.py",
    "omniintelligence/nodes/node_ci_failure_tracker_effect/handlers/handler_trigger_record.py",
    "omniintelligence/nodes/node_ci_fingerprint_compute/handlers/handler_fingerprint.py",
    "omniintelligence/nodes/node_code_crawler_effect/handlers/handler_onextree_generator.py",
    "omniintelligence/nodes/node_code_crawler_effect/handlers/handler_onextree_query.py",
    "omniintelligence/nodes/node_code_entity_bridge_compute/handlers/handler_bridge.py",
    "omniintelligence/nodes/node_compliance_evaluate_effect/handlers/handler_compliance_evaluate.py",
    "omniintelligence/nodes/node_contract_eval_compute/handlers/handler_contract_eval.py",
    "omniintelligence/nodes/node_contract_eval_compute/handlers/validators.py",
    "omniintelligence/nodes/node_crawl_scheduler_effect/handlers/debounce_state.py",
    "omniintelligence/nodes/node_debug_fix_record_effect/handlers/handler_fix_record.py",
    "omniintelligence/nodes/node_debug_retrieval_compute/handlers/handler_retrieval.py",
    "omniintelligence/nodes/node_document_fetch_effect/handlers/protocol_blob_store.py",
    "omniintelligence/nodes/node_execution_trace_parser_compute/handlers/exceptions.py",
    "omniintelligence/nodes/node_execution_trace_parser_compute/handlers/handler_compute.py",
    "omniintelligence/nodes/node_execution_trace_parser_compute/handlers/handler_event_extraction.py",
    "omniintelligence/nodes/node_execution_trace_parser_compute/handlers/handler_trace_parsing.py",
    "omniintelligence/nodes/node_execution_trace_parser_compute/handlers/protocols.py",
    "omniintelligence/nodes/node_git_repo_crawler_effect/handlers/protocol_crawl_state.py",
    "omniintelligence/nodes/node_gmail_intent_evaluator_effect/handlers/handler_gmail_intent_evaluate.py",
    "omniintelligence/nodes/node_intelligence_reducer/handlers/handler_pattern_lifecycle.py",
    "omniintelligence/nodes/node_intelligence_reducer/handlers/handler_process.py",
    "omniintelligence/nodes/node_intent_classifier_compute/handlers/exceptions.py",
    "omniintelligence/nodes/node_intent_classifier_compute/handlers/handler_adaptive_classification.py",
    "omniintelligence/nodes/node_intent_classifier_compute/handlers/handler_intent_classification.py",
    "omniintelligence/nodes/node_intent_classifier_compute/handlers/handler_langextract.py",
    "omniintelligence/nodes/node_intent_classifier_compute/handlers/handler_typed_classification.py",
    "omniintelligence/nodes/node_intent_cost_forecast_compute/handlers/handler_cost_forecast.py",
    "omniintelligence/nodes/node_intent_drift_detect_compute/handlers/handler_drift_detect.py",
    "omniintelligence/nodes/node_linear_crawler_effect/handlers/protocol_linear_state.py",
    "omniintelligence/nodes/node_memory_eval_compute/handlers/handler_memory_evaluation.py",
    "omniintelligence/nodes/node_pattern_assembler_orchestrator/handlers/exceptions.py",
    "omniintelligence/nodes/node_pattern_assembler_orchestrator/handlers/handler_orchestrate.py",
    "omniintelligence/nodes/node_pattern_assembler_orchestrator/handlers/handler_pattern_assembly.py",
    "omniintelligence/nodes/node_pattern_assembler_orchestrator/handlers/handler_workflow_coordination.py",
    "omniintelligence/nodes/node_pattern_assembler_orchestrator/handlers/protocols.py",
    "omniintelligence/nodes/node_pattern_compliance_effect/handlers/exceptions.py",
    "omniintelligence/nodes/node_pattern_compliance_effect/handlers/handler_compliance.py",
    "omniintelligence/nodes/node_pattern_compliance_effect/handlers/handler_compute.py",
    "omniintelligence/nodes/node_pattern_compliance_effect/handlers/protocols.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/exceptions.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/handler_architecture_patterns.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/handler_converters.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/handler_core_models.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/handler_error_patterns.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/handler_extract_all_patterns.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/handler_file_patterns.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/handler_group_node_families.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/handler_identity.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/handler_match_pattern.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/handler_merge.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/handler_novelty.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/handler_scan_role_occurrences.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/handler_store_node_families.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/handler_tool_failure_patterns.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/handler_tool_patterns.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/protocols.py",
    "omniintelligence/nodes/node_pattern_extraction_compute/handlers/utils.py",
    "omniintelligence/nodes/node_pattern_feedback_effect/handlers/handler_attribution_binder.py",
    "omniintelligence/nodes/node_pattern_feedback_effect/handlers/heuristics.py",
    "omniintelligence/nodes/node_pattern_learning_compute/handlers/exceptions.py",
    "omniintelligence/nodes/node_pattern_learning_compute/handlers/handler_confidence_scoring.py",
    "omniintelligence/nodes/node_pattern_learning_compute/handlers/handler_deduplication.py",
    "omniintelligence/nodes/node_pattern_learning_compute/handlers/handler_feature_extraction.py",
    "omniintelligence/nodes/node_pattern_learning_compute/handlers/handler_pattern_clustering.py",
    "omniintelligence/nodes/node_pattern_learning_compute/handlers/handler_pattern_learning.py",
    "omniintelligence/nodes/node_pattern_learning_compute/handlers/presets.py",
    "omniintelligence/nodes/node_pattern_learning_compute/handlers/protocols.py",
    "omniintelligence/nodes/node_pattern_learning_compute/handlers/replay.py",
    "omniintelligence/nodes/node_pattern_learning_compute/handlers/union_find.py",
    "omniintelligence/nodes/node_pattern_learning_compute/handlers/utils.py",
    "omniintelligence/nodes/node_pattern_matching_compute/handlers/exceptions.py",
    "omniintelligence/nodes/node_pattern_matching_compute/handlers/handler_compute.py",
    "omniintelligence/nodes/node_pattern_matching_compute/handlers/handler_pattern_matching.py",
    "omniintelligence/nodes/node_pattern_matching_compute/handlers/protocols.py",
    "omniintelligence/nodes/node_pattern_promotion_effect/handlers/handler_auto_promote.py",
    "omniintelligence/nodes/node_pattern_promotion_effect/handlers/handler_metrics.py",
    "omniintelligence/nodes/node_pattern_storage_effect/handlers/handler_pattern_storage.py",
    "omniintelligence/nodes/node_pattern_storage_effect/handlers/model_state_transition.py",
    "omniintelligence/nodes/node_pattern_storage_effect/handlers/protocol_pattern_state_manager.py",
    "omniintelligence/nodes/node_plan_reviewer_multi_compute/handlers/handler_confidence_scorer.py",
    "omniintelligence/nodes/node_plan_reviewer_multi_compute/handlers/handler_plan_reviewer_multi_compute.py",
    "omniintelligence/nodes/node_plan_reviewer_multi_compute/handlers/strategies/handler_independent_merge.py",
    "omniintelligence/nodes/node_plan_reviewer_multi_compute/handlers/strategies/handler_panel_vote.py",
    "omniintelligence/nodes/node_plan_reviewer_multi_compute/handlers/strategies/handler_sequential_critique.py",
    "omniintelligence/nodes/node_plan_reviewer_multi_compute/handlers/strategies/handler_specialist_split.py",
    "omniintelligence/nodes/node_policy_state_reducer/handlers/handler_lifecycle.py",
    "omniintelligence/nodes/node_policy_state_reducer/handlers/protocols.py",
    "omniintelligence/nodes/node_quality_scoring_compute/handlers/enum_onex_strictness_level.py",
    "omniintelligence/nodes/node_quality_scoring_compute/handlers/exceptions.py",
    "omniintelligence/nodes/node_quality_scoring_compute/handlers/handler_compute.py",
    "omniintelligence/nodes/node_quality_scoring_compute/handlers/handler_quality_scoring.py",
    "omniintelligence/nodes/node_quality_scoring_compute/handlers/presets.py",
    "omniintelligence/nodes/node_quality_scoring_compute/handlers/protocols.py",
    "omniintelligence/nodes/node_scoring_reducer_compute/handlers/handler_scoring.py",
    "omniintelligence/nodes/node_semantic_analysis_compute/handlers/exceptions.py",
    "omniintelligence/nodes/node_semantic_analysis_compute/handlers/handler_compute_semantic_analysis.py",
    "omniintelligence/nodes/node_semantic_analysis_compute/handlers/handler_semantic_analysis.py",
    "omniintelligence/nodes/node_semantic_analysis_compute/handlers/protocols.py",
    "omniintelligence/nodes/node_success_criteria_matcher_compute/handlers/exceptions.py",
    "omniintelligence/nodes/node_success_criteria_matcher_compute/handlers/handler_compute.py",
    "omniintelligence/nodes/node_success_criteria_matcher_compute/handlers/handler_criteria_matching.py",
    "omniintelligence/nodes/node_success_criteria_matcher_compute/handlers/protocols.py",
    "omniintelligence/nodes/node_watchdog_effect/handlers/observer_factory.py",
    "omniintelligence/nodes/node_intent_graph_reducer/handlers/handler_intent_graph_update.py",
    "omniintelligence/nodes/node_objective_ab_framework_compute/handlers/handler_ab_framework.py",
    "src/omniintelligence/adapters/embedding_client.py",
    "src/omniintelligence/adapters/embedding_client_local_openai.py",
    "src/omniintelligence/adapters/eval_llm_client.py",
    "src/omniintelligence/adapters/gmail_intent_http_client.py",
    "src/omniintelligence/adapters/utilization_llm_client.py",
    "src/omniintelligence/constants.py",
    "src/omniintelligence/models/events/model_llm_call_completed_event.py",
    "src/omniintelligence/nodes/node_anti_gaming_alerter_effect/models/model_alerter_input.py",
    "src/omniintelligence/nodes/node_intent_classifier_compute/models/model_typed_intent_config.py",
    "src/omniintelligence/nodes/node_pattern_demotion_effect/models/model_demotion_request.py",
    "src/omniintelligence/runtime/dispatch_handler_code_embed_graph.py",
    "src/omniintelligence/runtime/dispatch_handler_routing_feedback.py",
    "src/omniintelligence/runtime/dispatch_handler_utilization_scoring.py",
    "src/omniintelligence/runtime/dispatch_handlers.py",
    "src/omniintelligence/topics.py",
]
LIVE_HANDLER = "src/omniintelligence/nodes/node_pattern_demotion_effect/handlers/handler_demotion.py"


def _mapping(path: Path) -> dict[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _core(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--no-project", "--with", "omnibase-core==0.47.41", *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
        cwd=ROOT,
    )


def _caller_sha() -> str:
    jobs = _mapping(CALLER)["jobs"]
    assert isinstance(jobs, dict)
    uses = jobs["imperative-contract-guard"]["uses"]
    assert isinstance(uses, str)
    repository, sha = uses.split("@")
    assert repository == CORE_USES
    assert re.fullmatch(r"[0-9a-f]{40}", sha)
    assert sha.startswith(CORE_SHA_PREFIX)
    return sha


def test_caller_uses_core_and_keeps_the_job_and_context() -> None:
    workflow = _mapping(CALLER)
    assert workflow["name"] == "Imperative Contract Guard"
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    assert set(jobs) == {"imperative-contract-guard"}
    job = jobs["imperative-contract-guard"]
    assert job["uses"] == f"{CORE_USES}@{_caller_sha()}"
    assert job["with"] == {"allowlist-path": ALLOWLIST_PATH}
    assert workflow["permissions"] == {"contents": "read"}
    for path in WORKFLOWS.iterdir():
        if path.suffix in {".yml", ".yaml"}:
            text = path.read_text(encoding="utf-8")
            assert not re.search(
                r"onex_change_control/\.github/workflows/imperative-contract-guard\.yml",
                text,
            ), path


def test_canonical_shape_hook_and_ci_use_the_same_dev_merge_tag() -> None:
    """OMN-21527: the hook and the CI job run the node entry at one dev-merge tag."""
    repos = _mapping(ROOT / ".pre-commit-config.yaml")["repos"]
    assert isinstance(repos, list)
    (hook_repo,) = [
        repo
        for repo in repos
        if any(hook["id"] == "canonical-file-shape" for hook in repo["hooks"])
    ]
    assert hook_repo["repo"] == "https://github.com/OmniNode-ai/omnibase_core"
    tag = hook_repo["rev"]
    assert re.fullmatch(r"dev-\d{14}-[0-9a-f]{12}", tag)
    (hook,) = hook_repo["hooks"]
    assert hook["args"] == ["--rules", "file-shape"]
    jobs = _mapping(WORKFLOWS / "ci.yml")["jobs"]
    assert isinstance(jobs, dict)
    assert jobs["canonical-file-shape"]["env"]["CANONICAL_FILE_SHAPE_CORE"].endswith(
        f"@{tag}"
    )


def test_own_allowlist_matches_the_recorded_paths() -> None:
    assert hashlib.sha256(ALLOWLIST.read_bytes()).digest() == RECORDED_ALLOWLIST_DIGEST
    entries = _mapping(ALLOWLIST)["allowlisted_handlers"]
    assert isinstance(entries, list)
    assert [entry["path"] for entry in entries] == RECORDED_PATHS


def test_core_ratchet_accepts_unchanged_and_shrinking_but_refuses_an_extra_path() -> (
    None
):
    text = ALLOWLIST.read_text(encoding="utf-8")
    entries = _mapping(ALLOWLIST)["allowlisted_handlers"]
    assert isinstance(entries, list)
    extra = "src/omniintelligence/nodes/node_planted_effect/handlers/handler_planted.py"
    request = {
        "base": text,
        "head": yaml.safe_dump({"allowlisted_handlers": [*entries, {"path": extra}]}),
        "shrunk": yaml.safe_dump({"allowlisted_handlers": entries[:-1]}),
    }
    result = _core(
        "python",
        "-c",
        "import json, sys; "
        "from omnibase_core.handlers.handler_imperative_allowlist_ratchet import "
        "HandlerImperativeAllowlistRatchet; "
        "from omnibase_core.models.nodes.imperative_contract_guard."
        "model_allowlist_ratchet_input import ModelAllowlistRatchetInput; "
        "p=json.load(sys.stdin); h=HandlerImperativeAllowlistRatchet(); "
        "reports=[h.handle(ModelAllowlistRatchetInput(base_text=p['base'], "
        "head_text=p[k])) for k in ('base', 'shrunk', 'head')]; "
        "print(json.dumps([dict(r.model_dump(), admitted=r.admitted) for r in reports]))",
        stdin=json.dumps(request),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    unchanged, shrunk, planted = json.loads(result.stdout)
    assert unchanged == {
        "added": [],
        "removed": [],
        "bootstrap": False,
        "admitted": True,
    }
    assert shrunk["admitted"] is True
    assert shrunk["removed"] == [RECORDED_PATHS[-1]]
    assert planted["admitted"] is False
    assert planted["bootstrap"] is False
    assert planted["added"] == [extra]


def test_core_guard_accepts_clean_tree_and_refuses_a_planted_live_handler(
    tmp_path: Path,
) -> None:
    # Use the caller's input; the merge-base caller cannot provide it.
    jobs = _mapping(CALLER)["jobs"]
    assert isinstance(jobs, dict)
    assert jobs["imperative-contract-guard"]["with"]["allowlist-path"] == ALLOWLIST_PATH
    root = tmp_path / "omniintelligence"
    shutil.copytree(
        ROOT / "src", root / "src", ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copyfile(ROOT / "pyproject.toml", root / "pyproject.toml")
    (root / ".github").mkdir()
    shutil.copyfile(ALLOWLIST, root / ALLOWLIST_PATH)
    args = (
        "python",
        "-m",
        "omnibase_core.handlers.handler_imperative_contract_guard_cli",
        "--repo-root",
        str(root),
        "--allowlist-path",
        ALLOWLIST_PATH,
        "--scan-freestanding",
        "--json",
    )
    clean = _core(*args)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    handler = root / LIVE_HANDLER
    original = handler.read_text(encoding="utf-8")
    # The scanner reads this source; it does not execute a network request.
    handler.write_text(
        original + '\nimport httpx\nhttpx.get("http://example.invalid/planted")\n',
        encoding="utf-8",
    )
    planted = _core(*args)
    assert planted.returncode == 1, planted.stdout + planted.stderr
    report = json.loads(planted.stdout)[0]
    assert report["new_violation_count"] > 0
    (violation,) = [
        violation
        for violation in report["new_violations"]
        if violation["handler_path"].endswith("handlers/handler_demotion.py")
    ]
    assert violation["reachability"] == "live"
    assert "HTTP" in violation["undeclared_transports"]
    assert "undeclared_transport" in violation["violations"]
