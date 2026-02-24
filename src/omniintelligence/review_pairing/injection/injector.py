# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Preemptive Pattern Injection: inject stable patterns before code generation.

Queries PROMOTED and STABLE patterns for a given repo+language context,
formats them as natural-language constraints, and injects them into the
agent system prompt before code generation begins.

Core design principles:
    - **Non-blocking**: if pattern query fails, log and continue without injection.
    - **Token budget**: injection capped at MAX_INJECTION_TOKENS (default 500).
    - **Lowest-ranked truncation**: patterns ranked by score DESC; lowest dropped first.
    - **Human-readable output**: constraints are plain English, not raw JSON.
    - **Reward signals**: emitted after generation for avoidance (+1.0) and
      repeated violation (-2.0).

Format injected into agent system prompt::

    [PATTERN CONSTRAINTS]
    The following constraints are derived from previously observed violations
    in this repository. Avoid introducing these issues in generated code:

    1. Avoid rule ruff:E501. Lines must not exceed 88 characters.
    2. Avoid rule mypy:return-value. All functions must include return type annotations.
    ...
    [END PATTERN CONSTRAINTS]

Architecture:
    Pure computation — no Qdrant, no Postgres, no Kafka in this module.
    Callers (Effect nodes) provide pattern candidates; this module formats
    and applies token budget enforcement.

Reference: OMN-2577
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, unique
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_INJECTION_TOKENS: int = int(os.getenv("PATTERN_INJECTION_MAX_TOKENS", "500"))
"""Maximum tokens to add to the prompt from pattern injection."""

DEFAULT_TOP_K: int = int(os.getenv("PATTERN_INJECTION_TOP_K", "10"))
"""Maximum number of patterns to consider for injection (ranked by score)."""

INJECTION_SOURCE: str = "pattern_reinforcement"
"""Value logged to agent_manifest_injections.injection_source."""

REWARD_AVOIDANCE: float = 1.0
"""Reward for successfully avoiding a pattern that historically appeared."""

REWARD_REPEATED_VIOLATION: float = -2.0
"""Penalty for introducing a violation matching an injected pattern."""

# Approx chars-per-token for GPT-4-class models
_CHARS_PER_TOKEN: int = 4


def _estimate_tokens(text: str) -> int:
    """Estimate token count from character length (conservative heuristic)."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@unique
class RewardSignalType(str, Enum):
    """Type of reward signal emitted after code generation.

    Values:
        PREEMPTIVE_AVOIDANCE: Agent avoided a violation that historically appeared.
        REPEATED_VIOLATION: Agent introduced a violation matching an injected pattern.
    """

    PREEMPTIVE_AVOIDANCE = "preemptive_avoidance"
    REPEATED_VIOLATION = "repeated_violation"


@dataclass(frozen=True)
class PatternConstraintCandidate:
    """A single pattern eligible for injection into the agent prompt.

    Attributes:
        pattern_id: Unique identifier of the pattern (from pattern store).
        rule_id: Canonical rule identifier (e.g. ``ruff:E501``).
        natural_language_constraint: Human-readable constraint text.
            Must be a single sentence describing what to avoid.
        pattern_score: Score in [0.0, 1.0]; used for ranking and truncation.
        repo: Repository slug (e.g. ``OmniNode-ai/omniintelligence``).
        language: Programming language (e.g. ``python``, ``typescript``).
        file_path_prefix: Optional file path prefix for scoped injection.
            When set, only inject if the generation target matches this prefix.
        state: Lifecycle state of the pattern (``promoted`` or ``stable``).
    """

    pattern_id: UUID
    rule_id: str
    natural_language_constraint: str
    pattern_score: float
    repo: str
    language: str
    file_path_prefix: str = ""
    state: str = "stable"


@dataclass
class InjectionContext:
    """Context provided by the caller for a code generation request.

    Attributes:
        repo: Repository slug of the generation target.
        language: Programming language of the target file.
        file_path: Target file path (for prefix matching).
        generation_session_id: Unique ID for this generation session.
            Used to correlate injection events with reward signals.
    """

    repo: str
    language: str
    file_path: str = ""
    generation_session_id: UUID = field(default_factory=uuid4)


@dataclass
class InjectionResult:
    """Result of a pattern injection attempt.

    Attributes:
        injected: Whether any patterns were injected.
        constraint_block: The ``[PATTERN CONSTRAINTS]`` block to prepend to the prompt.
            Empty string if no patterns were injected.
        patterns_injected: List of pattern IDs that were injected.
        patterns_truncated: List of pattern IDs dropped due to token budget.
        token_count: Estimated token count of the constraint_block.
        injection_id: Unique ID for this injection event (logged to DB by caller).
        injected_at: UTC datetime of injection.
    """

    injected: bool
    constraint_block: str
    patterns_injected: list[UUID] = field(default_factory=list)
    patterns_truncated: list[UUID] = field(default_factory=list)
    token_count: int = 0
    injection_id: UUID = field(default_factory=uuid4)
    injected_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


@dataclass(frozen=True)
class RewardSignal:
    """Reward signal emitted after code generation.

    Published to ``onex.evt.review-pairing.reward-signal.v1``.

    Attributes:
        signal_id: Unique identifier for this reward signal.
        generation_session_id: Reference to the generation session.
        injection_id: Reference to the injection event.
        pattern_id: Pattern that was avoided or violated.
        rule_id: Rule that was avoided or violated.
        signal_type: Whether this is avoidance (+1.0) or violation (-2.0).
        reward_value: Numeric reward value.
        emitted_at: UTC datetime of emission.
    """

    signal_id: UUID
    generation_session_id: UUID
    injection_id: UUID
    pattern_id: UUID
    rule_id: str
    signal_type: RewardSignalType
    reward_value: float
    emitted_at: datetime


# ---------------------------------------------------------------------------
# Header/footer templates
# ---------------------------------------------------------------------------

_HEADER = """\
[PATTERN CONSTRAINTS]
The following constraints are derived from previously observed violations
in this repository. Avoid introducing these issues in generated code:

"""

_FOOTER = "\n[END PATTERN CONSTRAINTS]"


# ---------------------------------------------------------------------------
# PatternInjector
# ---------------------------------------------------------------------------


class PatternInjector:
    """Pure-computation pattern injector for the preemptive injection pipeline.

    The injector is stateless. All I/O (Qdrant query, Postgres fallback,
    Kafka emission, DB logging) is handled by the caller (Effect nodes).
    The injector only formats patterns and enforces token budget.

    Usage::

        injector = PatternInjector()

        # Caller fetches candidates from Qdrant/Postgres
        candidates = [...]  # List[PatternConstraintCandidate]

        context = InjectionContext(
            repo="OmniNode-ai/omniintelligence",
            language="python",
            file_path="src/foo/bar.py",
        )

        result = injector.build_injection(candidates, context)
        if result.injected:
            # Prepend result.constraint_block to agent system prompt
            # Log injection_id to agent_manifest_injections
            ...

        # After generation, compare generated code against injected patterns
        reward_signals = injector.compute_reward_signals(
            injected_patterns=result.patterns_injected,
            violated_rule_ids={"ruff:E501"},  # rules found in post-gen CI
            avoided_rule_ids={"mypy:return-value"},  # historically present but absent
            session_id=context.generation_session_id,
            injection_id=result.injection_id,
            candidates=candidates,
        )
        # Caller emits reward_signals to Kafka
    """

    def build_injection(
        self,
        candidates: list[PatternConstraintCandidate],
        context: InjectionContext,
        *,
        top_k: int = DEFAULT_TOP_K,
        max_tokens: int = MAX_INJECTION_TOKENS,
    ) -> InjectionResult:
        """Build a ``[PATTERN CONSTRAINTS]`` block from matched pattern candidates.

        Filters candidates by repo/language/file_path_prefix, ranks by score,
        applies token budget enforcement, and formats the constraint block.

        Args:
            candidates: Pattern candidates fetched by the caller from Qdrant/Postgres.
            context: Code generation context (repo, language, file_path).
            top_k: Maximum number of candidates to consider.
            max_tokens: Token budget for the injection block.

        Returns:
            ``InjectionResult`` with the constraint block and metadata.
        """
        if not candidates:
            logger.debug("PatternInjector.build_injection: no candidates provided")
            return InjectionResult(injected=False, constraint_block="")

        # Filter by context
        matched = self._filter_candidates(candidates, context)
        if not matched:
            logger.debug(
                "PatternInjector.build_injection: no candidates matched context "
                "repo=%s lang=%s path=%s",
                context.repo,
                context.language,
                context.file_path,
            )
            return InjectionResult(injected=False, constraint_block="")

        # Rank by score descending, limit to top_k
        ranked = sorted(matched, key=lambda c: c.pattern_score, reverse=True)[:top_k]

        # Apply token budget
        selected, truncated = self._apply_token_budget(ranked, max_tokens)

        if not selected:
            logger.debug(
                "PatternInjector.build_injection: all candidates exceeded token budget"
            )
            return InjectionResult(injected=False, constraint_block="")

        # Format constraint block
        block = self._format_block(selected)
        token_count = _estimate_tokens(block)

        logger.info(
            "PatternInjector.build_injection: injecting %d patterns (%d tokens), "
            "truncated %d",
            len(selected),
            token_count,
            len(truncated),
        )

        return InjectionResult(
            injected=True,
            constraint_block=block,
            patterns_injected=[c.pattern_id for c in selected],
            patterns_truncated=[c.pattern_id for c in truncated],
            token_count=token_count,
        )

    def compute_reward_signals(
        self,
        *,
        injected_patterns: list[UUID],
        violated_rule_ids: set[str],
        avoided_rule_ids: set[str],
        session_id: UUID,
        injection_id: UUID,
        candidates: list[PatternConstraintCandidate],
    ) -> list[RewardSignal]:
        """Compute reward signals after code generation.

        Emits:
            +1.0 (PREEMPTIVE_AVOIDANCE) for each injected pattern whose rule
                appeared historically but was avoided in generated code.
            -2.0 (REPEATED_VIOLATION) for each injected pattern whose rule
                was still violated in generated code.

        Args:
            injected_patterns: Pattern IDs that were injected.
            violated_rule_ids: Rule IDs found in post-generation CI output.
            avoided_rule_ids: Rule IDs historically present but absent post-gen.
            session_id: Generation session ID.
            injection_id: Injection event ID.
            candidates: Original candidate list (for rule_id lookup).

        Returns:
            List of ``RewardSignal`` instances (empty if none apply).
        """
        # Build lookup from pattern_id → candidate
        id_map: dict[UUID, PatternConstraintCandidate] = {
            c.pattern_id: c for c in candidates
        }

        signals: list[RewardSignal] = []
        now = datetime.now(tz=UTC)

        for pattern_id in injected_patterns:
            candidate = id_map.get(pattern_id)
            if candidate is None:
                continue

            rule_id = candidate.rule_id

            if rule_id in violated_rule_ids:
                signals.append(
                    RewardSignal(
                        signal_id=uuid4(),
                        generation_session_id=session_id,
                        injection_id=injection_id,
                        pattern_id=pattern_id,
                        rule_id=rule_id,
                        signal_type=RewardSignalType.REPEATED_VIOLATION,
                        reward_value=REWARD_REPEATED_VIOLATION,
                        emitted_at=now,
                    )
                )

            elif rule_id in avoided_rule_ids:
                signals.append(
                    RewardSignal(
                        signal_id=uuid4(),
                        generation_session_id=session_id,
                        injection_id=injection_id,
                        pattern_id=pattern_id,
                        rule_id=rule_id,
                        signal_type=RewardSignalType.PREEMPTIVE_AVOIDANCE,
                        reward_value=REWARD_AVOIDANCE,
                        emitted_at=now,
                    )
                )

        logger.debug(
            "PatternInjector.compute_reward_signals: %d signals "
            "(%d violations, %d avoidances)",
            len(signals),
            sum(
                1
                for s in signals
                if s.signal_type == RewardSignalType.REPEATED_VIOLATION
            ),
            sum(
                1
                for s in signals
                if s.signal_type == RewardSignalType.PREEMPTIVE_AVOIDANCE
            ),
        )

        return signals

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _filter_candidates(
        candidates: list[PatternConstraintCandidate],
        context: InjectionContext,
    ) -> list[PatternConstraintCandidate]:
        """Filter candidates by repo, language, and file path prefix."""
        result = []
        for c in candidates:
            if c.repo and c.repo != context.repo:
                continue
            if c.language and c.language != context.language:
                continue
            if c.file_path_prefix and not context.file_path.startswith(
                c.file_path_prefix
            ):
                continue
            result.append(c)
        return result

    @staticmethod
    def _apply_token_budget(
        ranked: list[PatternConstraintCandidate],
        max_tokens: int,
    ) -> tuple[list[PatternConstraintCandidate], list[PatternConstraintCandidate]]:
        """Apply token budget: select patterns that fit, drop lowest-ranked rest.

        Args:
            ranked: Candidates sorted by score descending.
            max_tokens: Maximum token budget.

        Returns:
            ``(selected, truncated)`` tuple.
        """
        header_tokens = _estimate_tokens(_HEADER + _FOOTER)
        remaining = max_tokens - header_tokens

        selected: list[PatternConstraintCandidate] = []
        truncated: list[PatternConstraintCandidate] = []

        for i, candidate in enumerate(ranked):
            line = f"{i + 1}. {candidate.natural_language_constraint}\n"
            cost = _estimate_tokens(line)
            if remaining >= cost:
                selected.append(candidate)
                remaining -= cost
            else:
                truncated.append(candidate)

        return selected, truncated

    @staticmethod
    def _format_block(
        selected: list[PatternConstraintCandidate],
    ) -> str:
        """Format selected candidates into the constraint block string."""
        lines = [_HEADER]
        for i, c in enumerate(selected, 1):
            lines.append(f"{i}. {c.natural_language_constraint}\n")
        lines.append(_FOOTER)
        return "".join(lines)
