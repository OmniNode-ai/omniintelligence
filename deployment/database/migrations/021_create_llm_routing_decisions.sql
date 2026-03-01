-- Migration: 021_create_llm_routing_decisions
-- Description: Create llm_routing_decisions table for Bifrost LLM routing feedback loop
-- Author: omniintelligence
-- Date: 2026-03-01
-- Ticket: OMN-3298
--
-- Context:
--   node_llm_routing_decision_effect (OMN-2939) persists routing decision records
--   from omniclaude's Bifrost LLM gateway. The table is declared in
--   OMNIINTELLIGENCE_SCHEMA_MANIFEST but was never migrated, causing
--   SchemaFingerprintMismatchError at boot time.
--
--   The handler upserts on (session_id, correlation_id) as the idempotency key:
--     ON CONFLICT (session_id, correlation_id) DO UPDATE SET processed_at = EXCLUDED.processed_at
--
-- Idempotency:
--   All statements use IF NOT EXISTS so re-applying this migration is safe.
--
-- Rollback: rollback/021_rollback.sql

-- ============================================================================
-- Table: llm_routing_decisions
-- Idempotent routing decision records from omniclaude's Bifrost LLM gateway.
-- Unique on (session_id, correlation_id).
-- ============================================================================

CREATE TABLE IF NOT EXISTS llm_routing_decisions (
    -- Surrogate primary key
    id                      UUID        NOT NULL DEFAULT gen_random_uuid(),

    -- Idempotency key: composite unique constraint (matches ON CONFLICT clause in handler)
    -- session_id: opaque string from omniclaude (may be UUID or short string)
    session_id              TEXT        NOT NULL,
    -- correlation_id: distributed tracing ID (string; omniclaude emits as string)
    correlation_id          TEXT        NOT NULL,

    -- Routing decision payload
    -- selected_agent: agent name chosen by the LLM router
    selected_agent          TEXT        NOT NULL,
    -- llm_confidence: confidence score returned by the LLM (0.0-1.0)
    llm_confidence          FLOAT8      NOT NULL DEFAULT 0.0,
    -- llm_latency_ms: routing latency in milliseconds
    llm_latency_ms          INT4        NOT NULL DEFAULT 0,
    -- fallback_used: true if the LLM fell back to fuzzy matching
    fallback_used           BOOLEAN     NOT NULL DEFAULT FALSE,
    -- model_used: model identifier used for routing (e.g. endpoint URL)
    model_used              TEXT        NOT NULL DEFAULT '',
    -- fuzzy_top_candidate: top agent from fuzzy matching (determinism audit)
    fuzzy_top_candidate     TEXT,
    -- llm_selected_candidate: raw agent name the LLM returned before mapping
    llm_selected_candidate  TEXT,
    -- agreement: true when LLM and fuzzy top candidates agree
    agreement               BOOLEAN     NOT NULL DEFAULT FALSE,
    -- routing_prompt_version: prompt template version string
    routing_prompt_version  TEXT        NOT NULL DEFAULT '',

    -- Audit fields
    -- processed_at: when this node processed the event (updated on idempotent re-delivery)
    processed_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- created_at: when the row was first inserted (immutable after creation)
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_llm_routing_decisions PRIMARY KEY (id),
    CONSTRAINT uq_llm_routing_decisions_key
        UNIQUE (session_id, correlation_id)
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Index for querying all decisions for a session (analytics, debugging)
CREATE INDEX IF NOT EXISTS idx_llm_routing_decisions_session_id
    ON llm_routing_decisions (session_id);

-- Index for time-range queries (e.g., metrics dashboards, latency analysis)
CREATE INDEX IF NOT EXISTS idx_llm_routing_decisions_processed_at
    ON llm_routing_decisions (processed_at DESC);

-- Index for agreement analysis (LLM vs fuzzy matching comparison)
CREATE INDEX IF NOT EXISTS idx_llm_routing_decisions_agreement
    ON llm_routing_decisions (agreement);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE llm_routing_decisions IS
    'Idempotent LLM routing decision records from omniclaude Bifrost gateway. '
    'Unique on (session_id, correlation_id). OMN-3298 / OMN-2939.';

COMMENT ON COLUMN llm_routing_decisions.session_id IS
    'Session identifier from omniclaude (opaque string, not enforced as UUID).';

COMMENT ON COLUMN llm_routing_decisions.correlation_id IS
    'Distributed tracing correlation ID (string from omniclaude event envelope).';

COMMENT ON COLUMN llm_routing_decisions.selected_agent IS
    'Agent name selected by the LLM router after mapping.';

COMMENT ON COLUMN llm_routing_decisions.llm_confidence IS
    'Confidence score returned by the LLM (0.0-1.0).';

COMMENT ON COLUMN llm_routing_decisions.llm_latency_ms IS
    'Routing latency in milliseconds from the LLM call.';

COMMENT ON COLUMN llm_routing_decisions.fallback_used IS
    'True if the LLM routing fell back to fuzzy matching.';

COMMENT ON COLUMN llm_routing_decisions.model_used IS
    'Model identifier used for routing (typically an endpoint URL).';

COMMENT ON COLUMN llm_routing_decisions.fuzzy_top_candidate IS
    'Top agent from deterministic fuzzy matching (used for agreement audit). '
    'NULL if fuzzy matching did not produce a candidate.';

COMMENT ON COLUMN llm_routing_decisions.llm_selected_candidate IS
    'Raw agent name the LLM returned before normalization mapping. '
    'NULL if LLM did not return a candidate (fallback path).';

COMMENT ON COLUMN llm_routing_decisions.agreement IS
    'True when LLM-selected candidate and fuzzy top candidate agree.';

COMMENT ON COLUMN llm_routing_decisions.routing_prompt_version IS
    'Version string of the routing prompt template used for this decision.';

COMMENT ON COLUMN llm_routing_decisions.processed_at IS
    'When node_llm_routing_decision_effect processed this event. '
    'Updated on idempotent re-delivery (ON CONFLICT DO UPDATE).';

COMMENT ON COLUMN llm_routing_decisions.created_at IS
    'When the row was first inserted. Immutable after creation. '
    'Immutability is enforced at the application layer (ON CONFLICT DO UPDATE '
    'does not include created_at in the SET clause), not by a database constraint.';
