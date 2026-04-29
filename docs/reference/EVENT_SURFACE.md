> **Navigation**: [Home](../INDEX.md) > [Reference](.) > Event Surface

# Event Surface

**Owner:** omniintelligence
**Last verified:** 2026-04-29
**Verification source:** CLAUDE.md topic tables and contract YAML files under `src/omniintelligence/nodes/*/contract.yaml`

This page lists all Kafka topics produced, consumed, or otherwise associated with omniintelligence. It follows the shared event-surface reference pattern from [omni_home docs/standards/REPO_DOCUMENTATION_STANDARD.md](https://github.com/OmniNode-ai/omni_home/blob/main/docs/standards/REPO_DOCUMENTATION_STANDARD.md).

**Topic naming convention:** `onex.{kind}.{producer-service}.{event-name}.v{N}`

For which of these topics reach omnidash, see [DASH_INTEGRATION_TRUTH_BOUNDARY.md](DASH_INTEGRATION_TRUTH_BOUNDARY.md).

---

## Produced Topics

Topics published by omniintelligence nodes.

| Topic | Publisher node | Purpose | Consumer(s) |
|-------|---------------|---------|-------------|
| `onex.evt.omniintelligence.intent-classified.v1` | `NodeClaudeHookEventEffect` | Classified user intent from hook events | omnimemory (graph storage) |
| `onex.evt.omniintelligence.pattern-learned.v1` | `NodePatternLearningEffect` | Pattern extracted and learned from trace | `NodePatternStorageEffect` |
| `onex.evt.omniintelligence.pattern-stored.v1` | `NodePatternStorageEffect` | Pattern persisted to PostgreSQL | downstream subscribers |
| `onex.evt.omniintelligence.pattern-promoted.v1` | `NodePatternStorageEffect`, `NodePatternPromotionEffect` | Pattern promoted (provisional to validated) | downstream subscribers |
| `onex.evt.omniintelligence.pattern-deprecated.v1` | `NodePatternDemotionEffect` | Pattern demoted (validated to deprecated) | downstream subscribers |
| `onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1` | `NodePatternLifecycleEffect` | Atomic lifecycle transition applied with audit trail | downstream subscribers |
| `onex.evt.omniintelligence.code-analysis-completed.v1` | `NodeIntelligenceOrchestrator` | Code analysis workflow completed | downstream subscribers |
| `onex.evt.omniintelligence.code-analysis-failed.v1` | `NodeIntelligenceOrchestrator` | Code analysis workflow failed | downstream subscribers |
| `onex.evt.omniintelligence.document-ingestion-completed.v1` | `NodeIntelligenceOrchestrator` | Document ingestion completed | downstream subscribers |
| `onex.evt.omniintelligence.document-ingestion-failed.v1` | `NodeIntelligenceOrchestrator` | Document ingestion failed | downstream subscribers |
| `onex.evt.omniintelligence.pattern-learning-completed.v1` | `NodeIntelligenceOrchestrator` | Pattern learning workflow completed | downstream subscribers |
| `onex.evt.omniintelligence.pattern-learning-failed.v1` | `NodeIntelligenceOrchestrator` | Pattern learning workflow failed | downstream subscribers |
| `onex.evt.omniintelligence.quality-assessment-completed.v1` | `NodeIntelligenceOrchestrator` | Quality assessment scoring completed | omnidash (via projection handler) |
| `onex.evt.omniintelligence.quality-assessment-failed.v1` | `NodeIntelligenceOrchestrator` | Quality assessment scoring failed | downstream subscribers |
| `onex.evt.omniintelligence.bloom-eval-completed.v1` | `NodeBloomEvalOrchestrator` | Bloom evaluation suite completed | omnidash (gap — see DASH_INTEGRATION_TRUTH_BOUNDARY.md) |
| `onex.evt.omniintelligence.routing-feedback-processed.v1` | `NodeRoutingFeedbackEffect` | Routing feedback event processed | omnidash (verify READ_MODEL_TOPICS entry) |
| `onex.cmd.omniintelligence.pattern-lifecycle-transition.v1` | `NodePatternPromotionEffect`, `NodePatternDemotionEffect` | Command forwarded to trigger `NodePatternLifecycleEffect` | `NodePatternLifecycleEffect` |

---

## Consumed Topics

Topics subscribed to by omniintelligence nodes. Collected by `collect_subscribe_topics_from_contracts()` from contract YAML files — no hardcoded lists in Python.

| Topic | Subscriber node | Source producer | Purpose |
|-------|----------------|-----------------|---------|
| `onex.cmd.omniintelligence.claude-hook-event.v1` | `NodeClaudeHookEventEffect` | omniclaude | Claude Code hook events (UserPromptSubmit, Stop, etc.) |
| `onex.cmd.omniintelligence.tool-content.v1` | `NodeClaudeHookEventEffect` | omniclaude | Tool content events from Claude Code |
| `onex.cmd.omniintelligence.pattern-lifecycle-transition.v1` | `NodePatternLifecycleEffect` | `NodePatternPromotionEffect`, `NodePatternDemotionEffect` | Apply pattern lifecycle transitions atomically |
| `onex.cmd.omniintelligence.pattern-learning.v1` | `NodePatternLearningEffect`, `NodeIntelligenceOrchestrator` | `NodeClaudeHookEventEffect` (Stop) | Trigger pattern learning pipeline |
| `onex.evt.omniintelligence.pattern-learned.v1` | `NodePatternStorageEffect` | `NodePatternLearningEffect` | Persist learned patterns to PostgreSQL |
| `onex.evt.pattern.discovered.v1` | `NodePatternStorageEffect` | External systems (omniclaude, multi-producer domain event) | Pattern discovered externally; producer segment intentionally omitted |
| `onex.cmd.omniintelligence.session-outcome.v1` | `NodePatternFeedbackEffect` | External (session lifecycle triggers) | Record session outcome and update rolling-window metrics |
| `onex.cmd.omniintelligence.code-analysis.v1` | `NodeIntelligenceOrchestrator` | External callers | Trigger code analysis workflow |
| `onex.cmd.omniintelligence.document-ingestion.v1` | `NodeIntelligenceOrchestrator` | External callers | Trigger document ingestion workflow |
| `onex.cmd.omniintelligence.quality-assessment.v1` | `NodeIntelligenceOrchestrator` | `NodePatternFeedbackEffect` (planned — Gap 4 in wiring-gaps plan) | Trigger quality scoring pass |

---

## Projected / Read-Model Events

Events consumed by omnidash read-model projections. The projection handlers write into `omnidash_analytics` PostgreSQL. For live/dead/gap status see [DASH_INTEGRATION_TRUTH_BOUNDARY.md](DASH_INTEGRATION_TRUTH_BOUNDARY.md).

| Topic | Dash projection handler | Target table | Status |
|-------|------------------------|--------------|--------|
| `onex.evt.omniintelligence.quality-assessment-completed.v1` | `omniintelligence-projections.ts` | `pattern_learning_artifacts.quality_score` | Verify active in READ_MODEL_TOPICS |
| `onex.evt.omniintelligence.routing-feedback-processed.v1` | `omniintelligence-projections.ts:1312` | `routing_feedback_events` | Verify READ_MODEL_TOPICS entry and migration |
| `onex.evt.omniintelligence.bloom-eval-completed.v1` | None currently | `bloom_eval_results` (planned) | GAP — no consumer or table exists yet |

---

## Dashboard-Visible Events

Events that appear in omnidash dashboard surfaces (after projection).

| Topic | Dashboard surface | Status |
|-------|-------------------|--------|
| `onex.evt.omniintelligence.quality-assessment-completed.v1` | `/patterns` quality score column | Active (verify READ_MODEL_TOPICS) |
| `onex.evt.omniintelligence.routing-feedback-processed.v1` | `routing_feedback_events` read-model | Active (verify READ_MODEL_TOPICS) |

---

## Internal-Only Events

Events produced or consumed within this repo's pipeline that are not intended for external consumers.

| Topic | Notes |
|-------|-------|
| `onex.cmd.omniintelligence.pattern-lifecycle-transition.v1` | Produced by promotion/demotion nodes, consumed by lifecycle node — internal pipeline command |

---

## Deprecated or Drained Events

Events that had constants defined in omnidash but have no live producer in this repo. These are dead constants per the April 2026 wiring-gaps audit.

| Topic | Status | Notes |
|-------|--------|-------|
| `onex.evt.omniintelligence.pattern-scored.v1` | Dead — no producer | Omnidash `SUFFIX_INTELLIGENCE_PATTERN_SCORED` constant is dead. No omniintelligence node publishes this topic. |
| `onex.evt.omniintelligence.pattern-discovered.v1` | Dead — no producer | Omnidash `SUFFIX_INTELLIGENCE_PATTERN_DISCOVERED` constant is dead. No omniintelligence node publishes this topic. |
| `onex.evt.omniintelligence.session-outcome.v1` | Dead — no producer | Omnidash `SUFFIX_INTELLIGENCE_SESSION_OUTCOME_EVT` constant is dead. No producer exists here. |
| `onex.evt.omniintelligence.eval-completed.v1` | Misnamed — actual topic is `bloom-eval-completed.v1` | Omnidash `SUFFIX_INTELLIGENCE_EVAL_COMPLETED` points to wrong topic string. Naming reconciliation pending. |
| `routing.feedback` (bare legacy topic) | Drain pending (OMN-2366) | Legacy bare topic without `onex.*` prefix. `NodeRoutingFeedbackEffect` was updated to subscribe to `onex.evt.omniclaude.routing-feedback.v1`. Verify no producer remains on the bare topic. |

---

## DLQ Pattern

All effect nodes route failed messages to `{topic}.dlq` with:

- Original envelope preserved
- Error message and timestamp
- Retry count and service metadata
- Secret sanitization via `LogSanitizer`

---

## Correlation ID Tracing

All operations thread `correlation_id: UUID` through:

1. Input model
2. Handler logging (`extra={"correlation_id": ...}`)
3. Kafka payloads (`"correlation_id": str(correlation_id)`)
4. Output models (preserved for downstream)
