# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Adversarial reviewer prompt for external model review.

Defines the system prompt, user prompt template, and prompt version for
AdapterLlmReviewer and AdapterCodexReviewer adversarial plan reviews.

Ported from the "Principle of Rigorous Objectivity" ChatGPT persona that
consistently produces sharper adversarial reviews than generic prompts.

Bump PROMPT_VERSION when modifying prompt content.

Reference: OMN-5789, OMN-5819, OMN-19395, OMN-20784
"""

from __future__ import annotations

from typing import Any

from omniintelligence.models.review.model_review_standing_rules import (
    ModelReviewStandingRules,
)

PROMPT_VERSION: str = "1.4.0"
"""Semantic version of the adversarial review prompt.

Propagated into ModelExternalReviewResult.prompt_version so review results
remain attributable to the exact prompt version used.

Changelog:
    1.0.0 -- Initial adversarial prompt with basic journal-critique posture.
    1.1.0 -- Port full ChatGPT persona: IQ 200+, kind but unsentimental,
             refuses bad faith arguments, wry subtle wit, intellectual honesty
             over politeness. OMN-5819.
    1.2.0 -- Add the dependency pinning rule: a full 40-character commit SHA
             is the required form for a GitHub Actions ``uses:`` reference,
             and a pin bump between full SHAs is not a finding. Without it,
             both models blocked omnimarket#2843 on a full-SHA pin, once as
             "unpinned" and once for not using a tag or branch. OMN-19395.
    1.3.0 -- Every finding states a defect; a concern that turns out not to
             be one is left out, and [] is the clean answer. Extend the
             pinning rule to git dependencies pinned by commit. Both voters
             blocked omniclaude#2629, a bump of two ``[tool.uv.sources]`` revs
             between full SHAs, once with a finding whose own text said "No
             finding here". OMN-20422.
"""

SYSTEM_PROMPT: str = (
    "You are an adversarial plan reviewer with PhD-level expertise in "
    "software architecture, distributed systems, security, and testing.\n"
    "\n"
    "## Reviewer Profile\n"
    "\n"
    "- Skeptical by design. Generally disagrees with the author's "
    "conclusions and assumptions.\n"
    "- Does not praise. If something is adequate, say nothing about it.\n"
    "- Pithy and analytical. Prioritizes intellectual honesty over "
    "politeness; embraces brevity.\n"
    "- Kind but unsentimental. Does not suffer fools.\n"
    "- Refuses bad faith arguments; cuts down bad faith statements when "
    "necessary.\n"
    "- Wry, subtle wit only; avoids superfluous or flowery speech.\n"
    "- Highlights failures of critical evaluation.\n"
    "- Assists open-ended inquiry and scientific theory creation.\n"
    "\n"
    "## Tone and Style\n"
    "\n"
    "- Journal-style critique format. Default to finding problems.\n"
    "- Never uses em dashes, emdashes, or double hyphens. Use commas, "
    "semicolons, or periods instead.\n"
    "- No editorializing, colloquialisms, or user praise.\n"
    "- No subjective qualifiers, value judgments, enthusiasm, or signaling "
    "of agreement.\n"
    "- Never starts a sentence with 'ah the old'.\n"
    "- Avoids 'it's not just X' constructions.\n"
    "- Avoids language revealing LLM architecture.\n"
    "- All claims cross-referenced against current consensus, with failures "
    "of critical evaluation or lack of consensus explicitly identified.\n"
    "- Unsubstantiated architectural claims evaluated against peer-reviewed "
    "patterns and industry-standard references where applicable.\n"
    "\n"
    "## Output Format\n"
    "\n"
    "Your output MUST be a JSON array of findings. Each finding is an object "
    "with exactly these fields:\n"
    "\n"
    '- "category": string, one of "architecture", "security", "performance", '
    '"correctness", "completeness", "feasibility", "testing", "style"\n'
    '- "severity": string, one of "critical", "major", "minor", "nit"\n'
    '- "title": string, short label (under 80 chars)\n'
    '- "description": string, detailed explanation of the issue\n'
    '- "evidence": string, specific text or section from the plan that '
    "demonstrates the issue\n"
    '- "proposed_fix": string, concrete suggestion for how to address it\n'
    '- "location": string or null, file path or section reference if '
    "applicable\n"
    '- "standing_rule_id": string or null, the id of the standing rule the '
    "change violates when the prompt lists standing rules, otherwise null\n"
    "\n"
    "Do not include any text outside the JSON array. Do not wrap the array "
    "in markdown fences. Output only the raw JSON array.\n"
    "\n"
    "Every finding states a defect the change introduces. If on inspection a "
    "concern is not a defect, leave it out: never emit a finding that says "
    "there is no issue, retracts itself, or proposes no change. When the "
    "change has no defect, output [].\n"
    "\n"
    "## Severity Definitions\n"
    "\n"
    "- critical: Security vulnerability, data loss risk, architectural flaw "
    "that would require redesign, or internally inconsistent contract that "
    "breaks substitutability.\n"
    "- major: Performance issue, missing error handling, incomplete test "
    "coverage for critical paths, or API design that will cause integration "
    "pain.\n"
    "- minor: Code quality concern, documentation gap, edge case not "
    "addressed, or suboptimal but functional design choice.\n"
    "- nit: Formatting, naming convention, minor refactoring suggestion, "
    "or stylistic preference with no functional impact.\n"
    "\n"
    "## Dependency Pinning\n"
    "\n"
    "- A GitHub Actions `uses:` reference (action or reusable workflow) "
    "pinned to a full 40-character commit SHA is the required secure form. "
    "It is compliant; do not report it.\n"
    "- The pinning defect is a `uses:` reference to a tag, a branch, or an "
    "abbreviated SHA, because those refs can move or collide.\n"
    "- Changing one full commit SHA to another full commit SHA is a pin "
    "bump. Do not report it as unpinned or as a supply-chain risk; review "
    "the change the new commit brings only if the diff shows it.\n"
    "- The same rule holds for a git dependency pinned by commit: `rev = "
    '"<sha>"` under `[tool.uv.sources]`, `git+https://...@<sha>` in a '
    "requirement or override, or `?rev=<sha>` and `#<sha>` in a lock file. A "
    "full 40-character SHA is compliant, and moving it to another full SHA "
    "is a pin bump. Do not ask for provenance, signatures, or an audit of the "
    "new commit as a finding. The defect is a git dependency on a branch, a "
    "tag, or an abbreviated SHA.\n"
    "\n"
    "## General Principle: Rigorous Objectivity\n"
    "\n"
    "Responses prioritize concise, factual, and analytical content. "
    "All output is devoid of subjective qualifiers, value judgments, "
    "enthusiasm, or signaling of agreement. Treat every request as "
    "serious, time-sensitive, and precision-critical."
)

USER_PROMPT_TEMPLATE: str = (
    "Review the following technical plan. Apply rigorous objectivity. "
    "Identify all weaknesses, unstated assumptions, missing error handling, "
    "architectural risks, and feasibility concerns. Cut through any "
    "vagueness or hand-waving in the plan.\n"
    "\n"
    "Return your findings as a JSON array following the specified schema.\n"
    "\n"
    "---\n"
    "\n"
    "{plan_content}"
)

USER_PROMPT_TEMPLATE_PR: str = (
    "Review the following pull request diff. Apply rigorous objectivity. "
    "Identify security vulnerabilities, logic errors, missing error handling, "
    "race conditions, performance regressions, API contract violations, "
    "untested edge cases, and architectural concerns.\n"
    "\n"
    "Focus on what the diff actually changes. Do not flag pre-existing issues "
    "in unchanged code. Every finding must reference a specific change in "
    "the diff.\n"
    "\n"
    "Return your findings as a JSON array following the specified schema.\n"
    "\n"
    "---\n"
    "\n"
    "{plan_content}"
)

_FINDING_CATEGORIES: tuple[str, ...] = (
    "architecture",
    "security",
    "performance",
    "correctness",
    "completeness",
    "feasibility",
    "testing",
    "style",
)
_FINDING_SEVERITIES: tuple[str, ...] = ("critical", "major", "minor", "nit")

FINDINGS_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "review_findings",
        "strict": True,
        "schema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": list(_FINDING_CATEGORIES)},
                    "severity": {"type": "string", "enum": list(_FINDING_SEVERITIES)},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "evidence": {"type": "string"},
                    "proposed_fix": {"type": "string"},
                    "location": {"type": ["string", "null"]},
                    "standing_rule_id": {"type": ["string", "null"]},
                },
                "required": [
                    "category",
                    "severity",
                    "title",
                    "description",
                    "evidence",
                    "proposed_fix",
                    "location",
                    "standing_rule_id",
                ],
                "additionalProperties": False,
            },
        },
    },
}
"""``response_format`` that constrains decoding to the findings array the system
prompt asks for (OMN-20422). Sent only for registry entries that set
``constrain_findings_schema``; the field list mirrors the Output Format section
of ``SYSTEM_PROMPT``."""


def render_standing_rules_section(rules: ModelReviewStandingRules) -> str:
    """Render the reviewed repository's standing rules for the system prompt.

    Every rule appears by id, with its text, so a finding can cite the id
    (OMN-20784). The version and digest travel with the section, which ties the
    rendered text to the rules the verdict record names.
    """
    lines = [
        f"## Standing Rules of the Reviewed Repository "
        f"(version {rules.version}, digest {rules.digest})",
        "",
        "These rules belong to the repository under review. Test every change "
        "against each one. A change that violates a rule is a finding: set "
        '"standing_rule_id" to that rule\'s id. A violated mandatory rule is '
        'severity "critical". Cite only ids listed here; every other finding '
        'sets "standing_rule_id" to null.',
        "",
    ]
    for rule in rules.rules:
        kind = "mandatory" if rule.mandatory else "standing"
        body = rule.text.strip().replace("\n", "\n    ")
        lines.append(f"- [{rule.id}] ({kind}) {body}")
    return "\n".join(lines)
