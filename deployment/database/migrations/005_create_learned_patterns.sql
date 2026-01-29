-- Migration: 005_create_learned_patterns
-- Description: Create learned_patterns table with rolling metrics for promotion/demotion
-- Author: omniintelligence
-- Date: 2026-01-29
-- Ticket: OMN-1667
--
-- Dependencies: 004_create_domain_taxonomy.sql (foreign key to domain_taxonomy)
-- Note: Rolling window metrics prevent early failures from permanently poisoning scores.
--       Patterns need temporal stability (first_seen_at, distinct_days_seen) for promotion.

-- ============================================================================
-- Learned Patterns Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS learned_patterns (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Pattern identification
    pattern_signature TEXT NOT NULL,

    -- Domain with taxonomy (foreign key to domain_taxonomy)
    -- FK Cascade: RESTRICT prevents accidental domain deletion while patterns reference it;
    --             CASCADE propagates domain_id renames to maintain referential integrity.
    domain_id VARCHAR(50) NOT NULL REFERENCES domain_taxonomy(domain_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    domain_version VARCHAR(20) NOT NULL,
    domain_candidates JSONB NOT NULL DEFAULT '[]',  -- [{domain, confidence}, ...]

    -- Pattern metadata
    keywords TEXT[],
    confidence FLOAT NOT NULL CHECK (confidence >= 0.5),

    -- Lifecycle status
    status VARCHAR(20) NOT NULL DEFAULT 'candidate'
        CHECK (status IN ('candidate', 'provisional', 'validated', 'deprecated')),
    promoted_at TIMESTAMPTZ,
    deprecated_at TIMESTAMPTZ,
    deprecation_reason TEXT,

    -- Provenance tracking
    source_session_ids UUID[] NOT NULL,
    recurrence_count INT NOT NULL DEFAULT 1,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    distinct_days_seen INT NOT NULL DEFAULT 1,

    -- Rolling quality metrics (window of 20)
    quality_score FLOAT DEFAULT 0.5
        CONSTRAINT check_quality_score_bounds CHECK (quality_score >= 0.0 AND quality_score <= 1.0),
    injection_count_rolling_20 INT DEFAULT 0,
    success_count_rolling_20 INT DEFAULT 0,
    failure_count_rolling_20 INT DEFAULT 0,
    failure_streak INT DEFAULT 0,

    -- Data integrity constraint: success + failure can never exceed total injections
    CONSTRAINT check_rolling_metrics_sum
        CHECK (success_count_rolling_20 + failure_count_rolling_20 <= injection_count_rolling_20),

    -- Versioning
    -- Note: supersedes/superseded_by form a version chain (linked list of pattern versions).
    -- CIRCULAR REFERENCE CONSTRAINT: Application logic MUST ensure no cycles in the version chain.
    -- A pattern cannot supersede itself directly (A -> A) or transitively (A -> B -> C -> A).
    -- Database-level cycle prevention is not implemented due to complexity; enforce in application layer.
    version INT NOT NULL DEFAULT 1,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    supersedes UUID REFERENCES learned_patterns(id),
    superseded_by UUID REFERENCES learned_patterns(id),

    -- Compiled artifact
    compiled_snippet TEXT,
    compiled_token_count INT,
    compiled_at TIMESTAMPTZ,

    -- Auditing
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Uniqueness constraint for signature + domain + version
    CONSTRAINT unique_signature_domain_version UNIQUE (pattern_signature, domain_id, version)
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Partial unique index for current version lookup
CREATE UNIQUE INDEX IF NOT EXISTS idx_current_pattern
    ON learned_patterns (pattern_signature, domain_id)
    WHERE is_current = TRUE;

-- Index for querying by domain
CREATE INDEX IF NOT EXISTS idx_learned_patterns_domain
    ON learned_patterns(domain_id);

-- Index for querying by status
CREATE INDEX IF NOT EXISTS idx_learned_patterns_status
    ON learned_patterns(status);

-- Index for finding patterns by domain and status
CREATE INDEX IF NOT EXISTS idx_learned_patterns_domain_status
    ON learned_patterns(domain_id, status);

-- Index for temporal queries
CREATE INDEX IF NOT EXISTS idx_learned_patterns_first_seen
    ON learned_patterns(first_seen_at);

CREATE INDEX IF NOT EXISTS idx_learned_patterns_last_seen
    ON learned_patterns(last_seen_at);

-- Index for promotion candidates (temporal stability)
CREATE INDEX IF NOT EXISTS idx_learned_patterns_promotion_candidates
    ON learned_patterns(status, distinct_days_seen, quality_score)
    WHERE status = 'candidate' OR status = 'provisional';

-- Index for current versions only
CREATE INDEX IF NOT EXISTS idx_learned_patterns_current
    ON learned_patterns(is_current)
    WHERE is_current = TRUE;

-- Index for quality-based queries
CREATE INDEX IF NOT EXISTS idx_learned_patterns_quality
    ON learned_patterns(quality_score DESC);

-- Index for failure streak monitoring
CREATE INDEX IF NOT EXISTS idx_learned_patterns_failure_streak
    ON learned_patterns(failure_streak)
    WHERE failure_streak > 0;

-- GIN index for keywords array search
CREATE INDEX IF NOT EXISTS idx_learned_patterns_keywords
    ON learned_patterns USING GIN (keywords);

-- GIN index for domain_candidates JSONB
CREATE INDEX IF NOT EXISTS idx_learned_patterns_domain_candidates
    ON learned_patterns USING GIN (domain_candidates);

-- GIN index for source_session_ids array
CREATE INDEX IF NOT EXISTS idx_learned_patterns_source_sessions
    ON learned_patterns USING GIN (source_session_ids);

-- ============================================================================
-- Trigger for updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_learned_patterns_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_learned_patterns_updated_at
    BEFORE UPDATE ON learned_patterns
    FOR EACH ROW
    EXECUTE FUNCTION update_learned_patterns_updated_at();

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE learned_patterns IS 'Learned patterns with rolling metrics for promotion/demotion decisions';

-- Pattern identification
COMMENT ON COLUMN learned_patterns.id IS 'Unique pattern identifier';
COMMENT ON COLUMN learned_patterns.pattern_signature IS 'Canonical signature identifying the pattern';

-- Domain
COMMENT ON COLUMN learned_patterns.domain_id IS 'Primary domain from versioned taxonomy';
COMMENT ON COLUMN learned_patterns.domain_version IS 'Taxonomy version when pattern was classified';
COMMENT ON COLUMN learned_patterns.domain_candidates IS 'JSON array of {domain, confidence} for coherence checks';

-- Metadata
COMMENT ON COLUMN learned_patterns.keywords IS 'Keywords associated with this pattern';
COMMENT ON COLUMN learned_patterns.confidence IS 'Pattern confidence score (minimum 0.5)';

-- Lifecycle
COMMENT ON COLUMN learned_patterns.status IS 'Lifecycle: candidate -> provisional -> validated -> deprecated';
COMMENT ON COLUMN learned_patterns.promoted_at IS 'Timestamp when pattern was promoted to current status';
COMMENT ON COLUMN learned_patterns.deprecated_at IS 'Timestamp when pattern was deprecated';
COMMENT ON COLUMN learned_patterns.deprecation_reason IS 'Reason for deprecation';

-- Provenance
COMMENT ON COLUMN learned_patterns.source_session_ids IS 'Session IDs where this pattern was observed';
COMMENT ON COLUMN learned_patterns.recurrence_count IS 'Number of times pattern has been observed';
COMMENT ON COLUMN learned_patterns.first_seen_at IS 'First observation timestamp';
COMMENT ON COLUMN learned_patterns.last_seen_at IS 'Most recent observation timestamp';
COMMENT ON COLUMN learned_patterns.distinct_days_seen IS 'Number of distinct days pattern was observed (promotion gate)';

-- Rolling metrics
COMMENT ON COLUMN learned_patterns.quality_score IS 'Current quality score (0.0-1.0)';
COMMENT ON COLUMN learned_patterns.injection_count_rolling_20 IS 'Injection count in rolling window of 20';
COMMENT ON COLUMN learned_patterns.success_count_rolling_20 IS 'Success count in rolling window of 20';
COMMENT ON COLUMN learned_patterns.failure_count_rolling_20 IS 'Failure count in rolling window of 20';
COMMENT ON COLUMN learned_patterns.failure_streak IS 'Consecutive failures (triggers demotion)';

-- Constraint comments
COMMENT ON CONSTRAINT check_quality_score_bounds ON learned_patterns IS 'Ensures quality_score remains within valid range [0.0, 1.0]';
COMMENT ON CONSTRAINT check_rolling_metrics_sum ON learned_patterns IS 'Ensures success + failure counts never exceed total injection count in rolling window';

-- Versioning
COMMENT ON COLUMN learned_patterns.version IS 'Pattern version number';
COMMENT ON COLUMN learned_patterns.is_current IS 'Whether this is the current version';
COMMENT ON COLUMN learned_patterns.supersedes IS 'Previous version this pattern supersedes. Forms a version chain with superseded_by. APPLICATION CONSTRAINT: Must not form circular chains (A->B->C->A). A pattern cannot supersede itself directly or transitively. Cycle prevention enforced in application layer, not database.';
COMMENT ON COLUMN learned_patterns.superseded_by IS 'Newer version that supersedes this pattern. Forms a version chain with supersedes. APPLICATION CONSTRAINT: Must not form circular chains (A->B->C->A). A pattern cannot be superseded by itself directly or transitively. Cycle prevention enforced in application layer, not database.';

-- Compiled artifact
COMMENT ON COLUMN learned_patterns.compiled_snippet IS 'Pre-compiled snippet for injection';
COMMENT ON COLUMN learned_patterns.compiled_token_count IS 'Token count of compiled snippet';
COMMENT ON COLUMN learned_patterns.compiled_at IS 'When snippet was last compiled';
