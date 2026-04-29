> **Navigation**: [Home](../INDEX.md) > [Reference](.) > Dash Integration Truth Boundary

# Dash Integration Truth Boundary

**Owner:** omniintelligence (producer) / omnidash (consumer)
**Last verified:** 2026-04-29
**Source:** `omni_home/docs/plans/2026-04-09-omniintelligence-wiring-gaps.md`
**Verification commands:**
- Producer truth: `grep -rn 'publish_topics' src/omniintelligence/nodes/*/contract.yaml`
- Consumer truth (omnidash): `grep -rn 'SUFFIX_INTELLIGENCE' omnidash/shared/topics.ts`

---

## Boundary Rule

**omnidash never queries omniintelligence's database directly.** All data flows via Kafka:

```
omniintelligence (producer)
    Kafka topic
        omnidash read-model consumer (projection handler)
            omnidash_analytics PostgreSQL read-model
                omnidash API / dashboard
```

omnidash owns the `omnidash_analytics` read-model. omniintelligence owns the source events. The boundary is the Kafka topic — omniintelligence never writes to `omnidash_analytics`, and omnidash never reads from omniintelligence's PostgreSQL.

---

## Architecture Diagram

```
omniintelligence (producer / owning service)
  NodePatternFeedbackEffect  ──────────────► onex.cmd.omniintelligence.quality-assessment.v1
                                                     (Gap 4: no publisher yet)
                                                             |
  NodeIntelligenceOrchestrator  ◄── triggers ─────────────-+
        NodeQualityScoringCompute (pure compute, called internally)
              publishes: onex.evt.omniintelligence.quality-assessment-completed.v1

  NodeBloomEvalOrchestrator  ─────────────► onex.evt.omniintelligence.bloom-eval-completed.v1
  NodeRoutingFeedbackEffect  ─────────────► onex.evt.omniintelligence.routing-feedback-processed.v1
  (no producer for: pattern-scored / pattern-discovered / session-outcome evt)

omnidash (consumer / read-model)
  read-model-consumer.ts  projects Kafka events into omnidash_analytics
  shared/topics.ts        export constants must match real producers
```

---

## Topic Truth Matrix

### Live and Wired

| Topic | omniintelligence producer | omnidash consumer | Status |
|-------|--------------------------|-------------------|--------|
| `onex.evt.omniintelligence.quality-assessment-completed.v1` | `NodeIntelligenceOrchestrator` | `omniintelligence-projections.ts` (`SUFFIX_INTELLIGENCE_QUALITY_ASSESSMENT_COMPLETED`) | Active — verify topic is in omnidash `topics.yaml` |
| `onex.evt.omniintelligence.routing-feedback-processed.v1` | `NodeRoutingFeedbackEffect` | `omniintelligence-projections.ts:1312` (`SUFFIX_INTELLIGENCE_ROUTING_FEEDBACK_PROCESSED`) | Active — verify `routing_feedback_events` migration and READ_MODEL_TOPICS |
| `onex.evt.omniintelligence.intent-classified.v1` | `NodeClaudeHookEventEffect` | omnimemory (not omnidash) | Internal to intelligence-to-memory pipeline; no omnidash projection needed |

### Gap: No omnidash Consumer

| Topic | omniintelligence producer | omnidash constant | Gap |
|-------|--------------------------|-------------------|-----|
| `onex.evt.omniintelligence.bloom-eval-completed.v1` | `NodeBloomEvalOrchestrator` | `SUFFIX_INTELLIGENCE_EVAL_COMPLETED` points to `eval-completed.v1` (wrong suffix) | Gap 2: no consumer in `omniintelligence-projections.ts`; `bloom_eval_results` table does not exist |

### Gap: No omniintelligence Producer

| Topic | omnidash constant | Status | Action |
|-------|-------------------|--------|--------|
| `onex.evt.omniintelligence.pattern-scored.v1` | `SUFFIX_INTELLIGENCE_PATTERN_SCORED` (topics.ts:332) | Dead constant | Prune from omnidash unless a producer ticket exists |
| `onex.evt.omniintelligence.pattern-discovered.v1` | `SUFFIX_INTELLIGENCE_PATTERN_DISCOVERED` (topics.ts:333) | Dead constant | Prune from omnidash unless a producer ticket exists |
| `onex.evt.omniintelligence.session-outcome.v1` | `SUFFIX_INTELLIGENCE_SESSION_OUTCOME_EVT` (topics.ts:330) | Dead constant | Prune from omnidash; no producer exists |

### Naming Mismatch

| Intended topic | omnidash constant | Actual produced topic | Action |
|----------------|-------------------|-----------------------|--------|
| bloom eval results | `SUFFIX_INTELLIGENCE_EVAL_COMPLETED` → `onex.evt.omniintelligence.eval-completed.v1` | `onex.evt.omniintelligence.bloom-eval-completed.v1` | Update omnidash constant to `bloom-eval-completed.v1` and add projection handler |

### Omnidash Dead Constants (no omniintelligence involvement)

| Topic | omnidash constant | Status | Notes |
|-------|-------------------|--------|-------|
| `onex.cmd.omniintelligence.session-outcome.v1` | `SUFFIX_INTELLIGENCE_SESSION_OUTCOME_CMD` (topics.ts:328) | Dead constant on omnidash side | This command IS consumed by `NodePatternFeedbackEffect` here, but omnidash subscribing makes no sense — prune from omnidash |

### Legacy / Deprecated

| Topic | Status | Notes |
|-------|--------|-------|
| `routing.feedback` (bare topic, no `onex.*` prefix) | Drain pending (OMN-2366) | Legacy bare topic from before `onex.*` naming standard. `NodeRoutingFeedbackEffect` now subscribes to `onex.evt.omniclaude.routing-feedback.v1`. Verify no producer remains on the bare topic. |

---

## Quality Score Pipeline — Gap 4

The primary data gap blocking non-null quality scores on the omnidash `/patterns` dashboard:

```
NodePatternFeedbackEffect  ──X──►  onex.cmd.omniintelligence.quality-assessment.v1
                                          (NO PUBLISHER — Gap 4)
                                                   |
                                                   v (if published)
                                   NodeIntelligenceOrchestrator
                                          |
                                          v
                                   NodeQualityScoringCompute
                                          |
                                          v
                         onex.evt.omniintelligence.quality-assessment-completed.v1
                                          |
                                          v
                                   omnidash projection handler
                                          |
                                          v
                                   omnidash_analytics.pattern_learning_artifacts.quality_score
```

**Root cause:** `NodePatternFeedbackEffect.handler_session_outcome.py` writes rolling-window metrics to `learned_patterns` DB but does not publish the quality-assessment command. Without that publish, `NodeIntelligenceOrchestrator` never triggers scoring, and quality scores remain NULL.

**Fix location:** `src/omniintelligence/nodes/node_pattern_feedback_effect/handlers/handler_session_outcome.py` — add publish of `onex.cmd.omniintelligence.quality-assessment.v1` after successful DB write. Contract `publish_topics` must be updated to declare this.

**Tracking:** See wiring-gaps plan Task 3 for implementation steps.

---

## PatternSummarySchema Field Alias Issue

omnidash `shared/event-schemas.ts` `PatternSummarySchema` accepts three aliases per field:

- `id | pattern_id | patternId`
- `quality_score | composite_score | compositeScore`

This triple-alias pattern masks serialization drift. Resolution path:

1. Confirm what field names `NodePatternProjectionEffect` actually serializes (expected: snake_case)
2. If snake_case only: remove camelCase aliases from omnidash
3. If camelCase: update omniintelligence first, then remove aliases in a follow-on omnidash PR

Breaking-change risk: tracked in wiring-gaps plan Task 8.

---

## Stable Reference vs. Historical Context

| Document | Status | Notes |
|----------|--------|-------|
| This page (`DASH_INTEGRATION_TRUTH_BOUNDARY.md`) | **Stable reference** — update when topic wiring changes | Extracted from wiring-gaps plan 2026-04-09 |
| `omni_home/docs/plans/2026-04-09-omniintelligence-wiring-gaps.md` | Historical context — implementation plan | Not active architecture; task list for gap-closing work |

---

## Verification

To verify producer truth for any topic:

```bash
# Check if omniintelligence produces a topic
grep -rn 'bloom-eval-completed' src/omniintelligence/nodes/
grep -rn 'publish_topics' src/omniintelligence/nodes/node_bloom_eval_orchestrator/contract.yaml

# Check if omnidash has a consumer constant
grep -rn 'SUFFIX_INTELLIGENCE' omnidash/shared/topics.ts

# Check if omnidash has a projection handler
grep -rn 'bloom-eval-completed\|SUFFIX_INTELLIGENCE_BLOOM' \
  omnidash/server/consumers/read-model/omniintelligence-projections.ts
```
