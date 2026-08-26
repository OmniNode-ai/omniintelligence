> **Navigation**: [Home](../INDEX.md) > [Reference](.) > Dash Integration Truth Boundary

# Dash Integration Truth Boundary

**Owner:** omniintelligence (producer) / omnidash (consumer)
**Last verified:** 2026-08-26
**Status:** Producer side (this repo) re-verified live and accurate. Consumer side (omnidash) is
**STALE — do not treat as current truth.** See "Consumer-Side Status" below.
**Source:** `omni_home/docs/plans/2026-04-09-omniintelligence-wiring-gaps.md`

---

## Consumer-Side Status (read this first)

This document's original "Topic Truth Matrix" cited specific omnidash files and exported
constants as the live consumer-side truth: `omnidash/shared/topics.ts`, `SUFFIX_INTELLIGENCE_*`
constants, `omnidash/server/consumers/read-model/omniintelligence-projections.ts`, and a
`read-model-consumer.ts`. Re-verified against the live `omnidash` tree (`origin/dev`,
2026-08-26):

- `omnidash/shared/topics.ts` does not exist. The nearest file is `omnidash/shared/types/topics.ts`.
- No `SUFFIX_INTELLIGENCE_*` constant exists anywhere in the `omnidash` tree
  (`grep -rn SUFFIX_INTELLIGENCE omnidash` returns nothing).
- `omniintelligence-projections.ts` does not exist anywhere in the tree.
- `read-model-consumer.ts` does not exist anywhere in the tree.
- `omnidash` has no `server/consumers` directory at all — the read-model-consumer
  architecture this doc describes is not present in the current `omnidash` codebase.
- `PatternSummarySchema` (cited below under "Field Alias Issue") does not exist anywhere
  in `omnidash` either.

This is not a rename — a full-tree grep found no trace of the described integration surface.
`omnidash` has moved to a different architecture since this doc was last verified
(2026-04-29; see `omni_home/CLAUDE.md` repository registry, which now describes `omnidash` as a
"Composable widget dashboard (Vite + React, services-led architecture)"). Whether omniintelligence
events reach omnidash today, and by what mechanism, is **unknown from this repo alone** and cannot
be established without an omnidash-side audit.

**Follow-up filed:** OMN-16577 — determine, from the omnidash side, whether/how omniintelligence
Kafka events are currently consumed by omnidash's current architecture, and either restore a
truth-boundary doc on the omnidash side or update this document's consumer-side claims to match.

---

## Boundary Rule

**omnidash never queries omniintelligence's database directly.** All data is intended to flow via
Kafka:

```
omniintelligence (producer)
    Kafka topic
        omnidash read-model consumer (projection handler)
            omnidash_analytics PostgreSQL read-model
                omnidash API / dashboard
```

This is the architectural intent as of the 2026-04-09 wiring-gaps audit: omnidash owns the
`omnidash_analytics` read-model, omniintelligence owns the source events, and the boundary is the
Kafka topic. Whether this remains the live implementation on the omnidash side is exactly the
question the consumer-side audit above needs to answer.

---

## Producer-Side Truth (omniintelligence) — re-verified live 2026-08-26

The following topics are confirmed live by grepping this repo's node contracts
(`grep -rn 'publish_topics' -A5 src/omniintelligence/nodes/*/contract.yaml`):

| Topic | Producer | Verified |
|-------|----------|----------|
| `onex.evt.omniintelligence.bloom-eval-completed.v1` | `node_bloom_eval_orchestrator` | `contract.yaml` `publish_topics` |
| `onex.evt.omniintelligence.intent-classified.v1` | `node_claude_hook_event_effect`, `node_cursor_hook_event_effect` | `contract.yaml` `publish_topics` |
| `onex.evt.omniintelligence.routing-feedback-processed.v1` | `node_routing_feedback_effect` | `contract.yaml` `publish_topics` |
| `onex.cmd.omniintelligence.quality-assessment.v1` | `node_pattern_feedback_effect` | `contract.yaml` `publish_topics` — **now shipped, see Gap 4 below** |
| `onex.evt.omniintelligence.pattern-scored.v1` | `node_pattern_feedback_effect` | `contract.yaml` `publish_topics` |
| `onex.evt.omniclaude.routing-feedback.v1` | consumed (not produced) by `node_routing_feedback_effect`, cross-repo from omniclaude | `contract.yaml` `subscribe_topics` |

No producer exists in this repo for `pattern-discovered` or `session-outcome` (evt); those remain
consumer-side-only claims that the omnidash audit above needs to confirm as dead or resolve.

---

## Quality Score Pipeline — Gap 4 (RESOLVED, was open as of 2026-04-29)

The original text of this section described a missing publisher:

> `NodePatternFeedbackEffect` writes rolling-window metrics to `learned_patterns` DB but does not
> publish the quality-assessment command, so `NodeIntelligenceOrchestrator` never triggers scoring.

**Live re-verification (2026-08-26): this is fixed.** `OMN-8144` shipped the publish —
`src/omniintelligence/nodes/node_pattern_feedback_effect/handlers/handler_session_outcome.py`
step 6b ("Emit quality-assessment commands for each updated pattern (OMN-8144)") now calls
`producer.publish(...)` for `onex.cmd.omniintelligence.quality-assessment.v1` after the DB write,
and the contract's `publish_topics` declares it. (This mirrors the same fix already recorded for
`EVENT_SURFACE.md`'s Gap-4 label — see OMN-16309 closeout — but that fix did not touch this file,
which still had its own stale copy of the same claim until now.)

Whether the omnidash-side projection handler that was supposed to consume
`onex.evt.omniintelligence.quality-assessment-completed.v1` and populate
`omnidash_analytics.pattern_learning_artifacts.quality_score` exists today is covered by the
Consumer-Side Status section above — not re-asserted here.

---

## Legacy / Deprecated

| Topic | Status | Notes |
|-------|--------|-------|
| `routing.feedback` (bare topic, no `onex.*` prefix) | Drain pending, unverified on the consumer side | `node_routing_feedback_effect` now subscribes to `onex.evt.omniclaude.routing-feedback.v1` (confirmed live, contract.yaml `subscribe_topics`). Whether any producer remains on the bare legacy topic was not re-verified this pass. |

---

## Stable Reference vs. Historical Context

| Document | Status | Notes |
|----------|--------|-------|
| This page (`DASH_INTEGRATION_TRUTH_BOUNDARY.md`) | **Producer side: stable / re-verified 2026-08-26. Consumer side: STALE, unverifiable from this repo — see Consumer-Side Status.** | Extracted from wiring-gaps plan 2026-04-09; consumer-side content not re-verifiable after omnidash's architecture changed |
| `omni_home/docs/plans/2026-04-09-omniintelligence-wiring-gaps.md` | Historical context — implementation plan | Not active architecture; task list for gap-closing work |

---

## Verification

To verify producer truth for any topic (still accurate):

```bash
# Check if omniintelligence produces a topic
grep -rn 'bloom-eval-completed' src/omniintelligence/nodes/
grep -rn 'publish_topics' src/omniintelligence/nodes/node_bloom_eval_orchestrator/contract.yaml
```

To check consumer-side truth, the commands this doc previously listed
(`grep -rn 'SUFFIX_INTELLIGENCE' omnidash/shared/topics.ts`, and equivalents for
`omniintelligence-projections.ts`) all return nothing against the live `omnidash` tree — that is
the finding documented above, not a command to re-run expecting a different result until the
omnidash-side follow-up lands.
