-- ============================================================================
-- Migration: 004 - Pattern Quality Metrics
-- ============================================================================
-- Description: Creates pattern_quality_metrics table for Pattern Dashboard
-- Date: 2025-10-28
-- Track: Pattern Dashboard Backend
-- Dependencies: PostgreSQL 15+, uuid-ossp extension, pattern_lineage_nodes table
-- Correlation ID: a06eb29a-8922-4fdf-bb27-96fc40fae415
-- Note: Adapted for Omniarchon schema (uses pattern_lineage_nodes instead of patterns)
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- 1. Pattern Quality Metrics Table
-- ============================================================================
-- Stores quality scores and confidence metrics for patterns over time
-- Used by Pattern Dashboard for trend analysis and quality monitoring

CREATE TABLE IF NOT EXISTS pattern_quality_metrics (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Pattern reference (references pattern_lineage_nodes.id)
    -- UNIQUE constraint on pattern_id to support UPSERT operations
    pattern_id UUID NOT NULL UNIQUE REFERENCES pattern_lineage_nodes(id) ON DELETE CASCADE,

    -- Quality metrics
    quality_score FLOAT NOT NULL CHECK (quality_score >= 0.0 AND quality_score <= 1.0),
    confidence FLOAT NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),

    -- Temporal tracking
    measurement_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Version tracking (optional)
    version VARCHAR(50),

    -- Audit tracking
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Additional metadata (future extensibility)
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Constraints
    CONSTRAINT valid_quality_score CHECK (quality_score >= 0.0 AND quality_score <= 1.0),
    CONSTRAINT valid_confidence CHECK (confidence >= 0.0 AND confidence <= 1.0),
    CONSTRAINT pattern_quality_metrics_pattern_id_unique UNIQUE (pattern_id)
);

-- ============================================================================
-- 2. Performance Indexes
-- ============================================================================
-- Optimized for Pattern Dashboard query patterns

-- Index on pattern_id for filtering by pattern
CREATE INDEX IF NOT EXISTS idx_pqm_pattern_id
    ON pattern_quality_metrics(pattern_id);

-- Index on measurement_timestamp for time-series queries (DESC for recent-first)
CREATE INDEX IF NOT EXISTS idx_pqm_measurement_timestamp
    ON pattern_quality_metrics(measurement_timestamp DESC);

-- Composite index for pattern-specific time-series queries
-- Used for queries like "get quality metrics for pattern X over time"
CREATE INDEX IF NOT EXISTS idx_pqm_pattern_measurement
    ON pattern_quality_metrics(pattern_id, measurement_timestamp DESC);

-- Index on quality_score for filtering by quality threshold
CREATE INDEX IF NOT EXISTS idx_pqm_quality_score
    ON pattern_quality_metrics(quality_score);

-- GIN index for metadata JSONB queries (future extensibility)
CREATE INDEX IF NOT EXISTS idx_pqm_metadata
    ON pattern_quality_metrics USING GIN (metadata);

-- ============================================================================
-- 3. Additional Indexes for Existing Tables (Dashboard Support)
-- ============================================================================
-- Add indexes to existing tables to support dashboard queries

-- Index on pattern_feedback.created_at for usage trend queries
-- Note: Only create if pattern_feedback table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_name = 'pattern_feedback') THEN
        CREATE INDEX IF NOT EXISTS idx_pattern_feedback_created_at
            ON pattern_feedback(created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_pattern_feedback_pattern_id_created
            ON pattern_feedback(pattern_id, created_at DESC);
    END IF;
END $$;

-- Index on patterns.pattern_type for type-based filtering
-- Note: Only create if patterns table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_name = 'patterns') THEN
        CREATE INDEX IF NOT EXISTS idx_patterns_pattern_type
            ON patterns(pattern_type);
    END IF;
END $$;

-- ============================================================================
-- 4. Helper Functions for Dashboard
-- ============================================================================

-- Function to get latest quality metric for a pattern
CREATE OR REPLACE FUNCTION get_latest_quality_metric(p_pattern_id UUID)
RETURNS TABLE (
    quality_score FLOAT,
    confidence FLOAT,
    measurement_timestamp TIMESTAMP WITH TIME ZONE,
    version VARCHAR
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        pqm.quality_score,
        pqm.confidence,
        pqm.measurement_timestamp,
        pqm.version
    FROM pattern_quality_metrics pqm
    WHERE pqm.pattern_id = p_pattern_id
    ORDER BY pqm.measurement_timestamp DESC
    LIMIT 1;
END;
$$;

-- Function to get quality trend for a pattern (last N measurements)
CREATE OR REPLACE FUNCTION get_quality_trend(
    p_pattern_id UUID,
    p_limit INTEGER DEFAULT 30
)
RETURNS TABLE (
    quality_score FLOAT,
    confidence FLOAT,
    measurement_timestamp TIMESTAMP WITH TIME ZONE,
    trend_direction VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_measurements INTEGER;
    v_avg_early FLOAT;
    v_avg_recent FLOAT;
BEGIN
    -- Get recent measurements
    RETURN QUERY
    WITH recent_metrics AS (
        SELECT
            pqm.quality_score,
            pqm.confidence,
            pqm.measurement_timestamp,
            ROW_NUMBER() OVER (ORDER BY pqm.measurement_timestamp DESC) as rn
        FROM pattern_quality_metrics pqm
        WHERE pqm.pattern_id = p_pattern_id
        ORDER BY pqm.measurement_timestamp DESC
        LIMIT p_limit
    ),
    trend_calc AS (
        SELECT
            AVG(CASE WHEN rn <= p_limit / 2 THEN quality_score END) as avg_recent,
            AVG(CASE WHEN rn > p_limit / 2 THEN quality_score END) as avg_early
        FROM recent_metrics
    )
    SELECT
        rm.quality_score,
        rm.confidence,
        rm.measurement_timestamp,
        CASE
            WHEN tc.avg_recent > tc.avg_early + 0.05 THEN 'improving'::VARCHAR
            WHEN tc.avg_recent < tc.avg_early - 0.05 THEN 'declining'::VARCHAR
            ELSE 'stable'::VARCHAR
        END as trend_direction
    FROM recent_metrics rm
    CROSS JOIN trend_calc tc
    ORDER BY rm.measurement_timestamp DESC;
END;
$$;

-- Function to calculate average quality for all patterns
CREATE OR REPLACE FUNCTION get_average_quality_score()
RETURNS FLOAT
LANGUAGE plpgsql
AS $$
DECLARE
    v_avg_score FLOAT;
BEGIN
    -- Get average of most recent quality score for each pattern
    SELECT AVG(latest_quality)
    INTO v_avg_score
    FROM (
        SELECT DISTINCT ON (pattern_id)
            quality_score as latest_quality
        FROM pattern_quality_metrics
        ORDER BY pattern_id, measurement_timestamp DESC
    ) latest_scores;

    RETURN COALESCE(v_avg_score, 0.0);
END;
$$;

-- ============================================================================
-- 5. Comments and Documentation
-- ============================================================================

COMMENT ON TABLE pattern_quality_metrics IS 'Quality scores and confidence metrics for patterns over time (Pattern Dashboard)';
COMMENT ON COLUMN pattern_quality_metrics.quality_score IS 'Pattern quality score (0.0-1.0)';
COMMENT ON COLUMN pattern_quality_metrics.confidence IS 'Confidence in quality measurement (0.0-1.0)';
COMMENT ON COLUMN pattern_quality_metrics.measurement_timestamp IS 'When quality was measured (for time-series analysis)';
COMMENT ON COLUMN pattern_quality_metrics.version IS 'Pattern version when quality was measured (optional)';
COMMENT ON COLUMN pattern_quality_metrics.metadata IS 'Additional metadata (extensible via JSONB)';

COMMENT ON FUNCTION get_latest_quality_metric IS 'Get most recent quality metric for a pattern';
COMMENT ON FUNCTION get_quality_trend IS 'Get quality trend for a pattern (improving/declining/stable)';
COMMENT ON FUNCTION get_average_quality_score IS 'Calculate average quality score across all patterns';

-- ============================================================================
-- 6. Sample Data (Optional - for testing)
-- ============================================================================
-- Uncomment to insert sample data for testing

/*
-- Insert sample quality metrics for testing
INSERT INTO pattern_quality_metrics (pattern_id, quality_score, confidence, measurement_timestamp, version)
SELECT
    pln.id,
    0.75 + (RANDOM() * 0.25)::FLOAT, -- Quality between 0.75-1.0
    0.80 + (RANDOM() * 0.20)::FLOAT, -- Confidence between 0.80-1.0
    NOW() - (n || ' days')::INTERVAL,
    pln.pattern_version
FROM
    pattern_lineage_nodes pln
    CROSS JOIN generate_series(0, 30) n
WHERE EXISTS (SELECT 1 FROM pattern_lineage_nodes LIMIT 1)
LIMIT 100; -- Limit to avoid excessive sample data
*/

-- ============================================================================
-- Migration Complete
-- ============================================================================
-- Tables created: pattern_quality_metrics
-- Indexes created: 5 (pattern_id, measurement_timestamp, composite, quality_score, metadata)
-- Functions created: 3 (get_latest_quality_metric, get_quality_trend, get_average_quality_score)
-- Performance target: <200ms for dashboard queries
-- ============================================================================
