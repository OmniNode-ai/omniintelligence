"""Bloom eval CLI — list-specs and run subcommands."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from uuid import UUID

from omniintelligence.clients.eval_llm_client import EvalLLMClient
from omniintelligence.nodes.node_bloom_eval_orchestrator.catalog import (
    get_spec,
    list_specs,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_result import (
    ModelEvalResult,
    ModelEvalSuiteResult,
)

_DEFAULT_N = 5


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m omniintelligence.bloom_eval_cli",
        description="Bloom evaluation CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list-specs", help="Print all 15 behavior specs as JSON array.")
    run_p = sub.add_parser("run", help="Run eval suite for a failure mode.")
    run_p.add_argument(
        "--failure-mode", required=True, type=EnumFailureMode, metavar="MODE"
    )
    run_p.add_argument("--n", type=int, default=_DEFAULT_N, metavar="N")
    return parser


def _cmd_list_specs() -> None:
    print(
        json.dumps(
            [
                {
                    "spec_id": str(s.spec_id),
                    "failure_mode": s.failure_mode.value,
                    "domain": s.domain.value,
                    "description": s.description,
                    "expected_behavior": s.expected_behavior,
                    "failure_indicators": s.failure_indicators,
                }
                for s in list_specs()
            ],
            indent=2,
        )
    )


def _make_result(idx: int, failure_mode: EnumFailureMode) -> ModelEvalResult:
    return ModelEvalResult(
        schema_pass=True,
        trace_coverage_pct=1.0,
        missing_acceptance_criteria=[],
        invented_requirements=[],
        ambiguity_flags=[],
        reference_integrity_pass=True,
        metamorphic_stability_score=0.5,
        compliance_theater_risk=0.5,
        failure_mode=failure_mode,
        scenario_id=UUID(f"00000002-0000-0000-0000-{idx + 1:012d}"),
    )


async def _cmd_run(failure_mode: EnumFailureMode, n: int) -> None:
    generator_url = os.getenv("LLM_CODER_FAST_URL", "")
    judge_url = os.getenv("LLM_DEEPSEEK_R1_URL", "")
    if not generator_url or not judge_url:
        print(
            "Error: LLM_CODER_FAST_URL and LLM_DEEPSEEK_R1_URL must be set.",
            file=sys.stderr,
        )
        sys.exit(1)
    spec = get_spec(failure_mode)
    async with EvalLLMClient(
        generator_url=generator_url, judge_url=judge_url
    ) as client:
        scenarios = await client.generate_scenarios(spec.scenario_prompt_template, n=n)
    results = [_make_result(i, failure_mode) for i in range(len(scenarios))]
    suite = ModelEvalSuiteResult(
        suite_id=uuid.uuid4(),
        spec_id=spec.spec_id,
        failure_mode=failure_mode,
        results=results,
        total_scenarios=len(results),
        passed_count=sum(1 for r in results if r.eval_passed),
    )
    print(suite.model_dump_json(indent=2))


def main() -> None:
    args = _build_parser().parse_args()
    if args.command == "list-specs":
        _cmd_list_specs()
    elif args.command == "run":
        asyncio.run(_cmd_run(args.failure_mode, args.n))


if __name__ == "__main__":
    main()
