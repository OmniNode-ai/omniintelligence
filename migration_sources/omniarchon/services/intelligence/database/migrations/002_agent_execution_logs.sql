-- ============================================================================
-- Migration: 002 - Agent Execution Logs
-- ============================================================================
-- Description: Creates agent_execution_logs table for comprehensive execution tracking
-- Author: System
-- Date: 2025-10-03
-- Track: Track 4 - Execution Log Aggregation
-- Dependencies: pattern_lineage_nodes table must exist
-- ============================================================================

-- Migration ID for tracking
INSERT INTO schema_versions (version, description, applied_at)
VALUES ('1.1.0_agent_execution_logs', 'Agent execution logs with full context tracking', NOW())
ON CONFLICT (version) DO NOTHING;

-- ============================================================================
-- Table: agent_execution_logs
-- ============================================================================
-- Comprehensive agent execution tracking with user prompts and configurations

CREATE TABLE IF NOT EXISTS agent_execution_logs (
    -- Primary identification
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Correlation with pattern lineage
    correlation_id UUID NOT NULL,
    session_id UUID,  -- Optional session grouping

    -- User context
    user_prompt TEXT,  -- Original user request/prompt
    user_id VARCHAR(255),  -- Who triggered the execution

    -- Agent information
    agent_name VARCHAR(255),  -- Which agent was used
    agent_config JSONB DEFAULT '{}',  -- Agent configuration and parameters

    -- Execution tracking
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) NOT NULL DEFAULT 'in_progress',  -- 'in_progress', 'success', 'error', 'cancelled'

    -- Error tracking
    error_message TEXT,
    error_type VARCHAR(100),

    -- Performance metrics
    duration_ms INTEGER,  -- Total execution time

    -- Additional context
    metadata JSONB DEFAULT '{}',  -- Additional execution metadata

    -- Quality metrics
    quality_score DECIMAL(3,2),  -- Overall execution quality (0-1)

    -- Constraints
    CONSTRAINT valid_status CHECK (status IN ('in_progress', 'success', 'error', 'cancelled')),
    CONSTRAINT valid_quality_score CHECK (quality_score IS NULL OR (quality_score BETWEEN 0 AND 1))
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Primary lookup indexes
CREATE INDEX IF NOT EXISTS idx_agent_execution_correlation_id
    ON agent_execution_logs(correlation_id);

CREATE INDEX IF NOT EXISTS idx_agent_execution_session_id
    ON agent_execution_logs(session_id)
    WHERE session_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_execution_agent_name
    ON agent_execution_logs(agent_name)
    WHERE agent_name IS NOT NULL;

-- Time-based queries
CREATE INDEX IF NOT EXISTS idx_agent_execution_started_at
    ON agent_execution_logs(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_execution_completed_at
    ON agent_execution_logs(completed_at DESC)
    WHERE completed_at IS NOT NULL;

-- Status filtering
CREATE INDEX IF NOT EXISTS idx_agent_execution_status
    ON agent_execution_logs(status);

-- Combined index for common queries
CREATE INDEX IF NOT EXISTS idx_agent_execution_correlation_session
    ON agent_execution_logs(correlation_id, session_id, started_at DESC);

-- JSONB indexes for metadata queries
CREATE INDEX IF NOT EXISTS idx_agent_execution_metadata
    ON agent_execution_logs USING gin(metadata);

CREATE INDEX IF NOT EXISTS idx_agent_execution_agent_config
    ON agent_execution_logs USING gin(agent_config);

-- ============================================================================
-- Views for Common Queries
-- ============================================================================

-- View: Recent execution logs with pattern counts
CREATE OR REPLACE VIEW v_recent_agent_executions AS
SELECT
    e.execution_id,
    e.correlation_id,
    e.session_id,
    e.user_prompt,
    e.agent_name,
    e.status,
    e.started_at,
    e.completed_at,
    e.duration_ms,
    e.quality_score,
    COUNT(DISTINCT pln.id) as pattern_count,
    COUNT(DISTINCT ple.id) as event_count
FROM agent_execution_logs e
LEFT JOIN pattern_lineage_nodes pln ON pln.correlation_id = e.correlation_id
LEFT JOIN pattern_lineage_events ple ON ple.correlation_id = e.correlation_id
GROUP BY e.execution_id, e.correlation_id, e.session_id, e.user_prompt,
         e.agent_name, e.status, e.started_at, e.completed_at,
         e.duration_ms, e.quality_score
ORDER BY e.started_at DESC;

-- View: Execution summary by agent
CREATE OR REPLACE VIEW v_agent_execution_summary AS
SELECT
    agent_name,
    COUNT(*) as total_executions,
    COUNT(*) FILTER (WHERE status = 'success') as successful_executions,
    COUNT(*) FILTER (WHERE status = 'error') as failed_executions,
    ROUND(AVG(duration_ms), 2) as avg_duration_ms,
    ROUND(AVG(quality_score), 2) as avg_quality_score,
    MAX(started_at) as last_execution
FROM agent_execution_logs
WHERE agent_name IS NOT NULL
GROUP BY agent_name
ORDER BY total_executions DESC;

-- ============================================================================
-- Functions for Execution Log Management
-- ============================================================================

-- Function: Get complete execution context
CREATE OR REPLACE FUNCTION get_execution_context(
    p_correlation_id UUID DEFAULT NULL,
    p_session_id UUID DEFAULT NULL,
    p_limit INTEGER DEFAULT 50
)
RETURNS TABLE (
    execution_id UUID,
    correlation_id UUID,
    session_id UUID,
    user_prompt TEXT,
    agent_name VARCHAR,
    agent_config JSONB,
    status VARCHAR,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    quality_score DECIMAL,
    pattern_count BIGINT,
    event_count BIGINT,
    patterns JSONB,
    events JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.execution_id,
        e.correlation_id,
        e.session_id,
        e.user_prompt,
        e.agent_name,
        e.agent_config,
        e.status,
        e.started_at,
        e.completed_at,
        e.duration_ms,
        e.quality_score,
        COUNT(DISTINCT pln.id) as pattern_count,
        COUNT(DISTINCT ple.id) as event_count,
        jsonb_agg(DISTINCT jsonb_build_object(
            'pattern_id', pln.pattern_id,
            'pattern_name', pln.pattern_name,
            'pattern_type', pln.pattern_type,
            'created_at', pln.created_at
        )) FILTER (WHERE pln.id IS NOT NULL) as patterns,
        jsonb_agg(DISTINCT jsonb_build_object(
            'event_type', ple.event_type,
            'pattern_id', ple.pattern_id,
            'success', ple.success,
            'timestamp', ple.timestamp
        )) FILTER (WHERE ple.id IS NOT NULL) as events
    FROM agent_execution_logs e
    LEFT JOIN pattern_lineage_nodes pln ON pln.correlation_id = e.correlation_id
    LEFT JOIN pattern_lineage_events ple ON ple.correlation_id = e.correlation_id
    WHERE
        (p_correlation_id IS NULL OR e.correlation_id = p_correlation_id)
        AND (p_session_id IS NULL OR e.session_id = p_session_id)
    GROUP BY e.execution_id, e.correlation_id, e.session_id, e.user_prompt,
             e.agent_name, e.agent_config, e.status, e.started_at,
             e.completed_at, e.duration_ms, e.quality_score
    ORDER BY e.started_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function: Update execution status and metrics
CREATE OR REPLACE FUNCTION update_execution_status(
    p_execution_id UUID,
    p_status VARCHAR,
    p_completed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    p_error_message TEXT DEFAULT NULL,
    p_quality_score DECIMAL DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    UPDATE agent_execution_logs
    SET
        status = p_status,
        completed_at = p_completed_at,
        duration_ms = EXTRACT(EPOCH FROM (p_completed_at - started_at))::INTEGER * 1000,
        error_message = p_error_message,
        quality_score = COALESCE(p_quality_score, quality_score)
    WHERE execution_id = p_execution_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Triggers
-- ============================================================================

-- Trigger: Auto-calculate duration on completion
CREATE OR REPLACE FUNCTION trigger_calculate_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.completed_at IS NOT NULL AND NEW.duration_ms IS NULL THEN
        NEW.duration_ms := EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at))::INTEGER * 1000;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_agent_execution_duration
BEFORE UPDATE OF completed_at ON agent_execution_logs
FOR EACH ROW
EXECUTE FUNCTION trigger_calculate_duration();

-- ============================================================================
-- Comments and Documentation
-- ============================================================================

COMMENT ON TABLE agent_execution_logs IS 'Comprehensive agent execution tracking with user prompts, configurations, and performance metrics';
COMMENT ON COLUMN agent_execution_logs.correlation_id IS 'Links to pattern_lineage_nodes and pattern_lineage_events';
COMMENT ON COLUMN agent_execution_logs.session_id IS 'Optional grouping for multi-execution sessions';
COMMENT ON COLUMN agent_execution_logs.user_prompt IS 'Original user request that triggered the agent';
COMMENT ON COLUMN agent_execution_logs.agent_config IS 'JSON configuration and parameters for the agent execution';
COMMENT ON COLUMN agent_execution_logs.quality_score IS 'Overall execution quality score (0-1)';

COMMENT ON FUNCTION get_execution_context IS 'Returns complete execution context with all related patterns and events';
COMMENT ON FUNCTION update_execution_status IS 'Updates execution status and calculates metrics';

-- ============================================================================
-- Post-Migration Verification
-- ============================================================================

DO $$
BEGIN
    ASSERT (SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_execution_logs')),
        'Table agent_execution_logs not created';

    ASSERT (SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_agent_execution_correlation_id')),
        'Index idx_agent_execution_correlation_id not created';

    RAISE NOTICE 'Agent Execution Logs migration completed successfully';
END $$;

-- ============================================================================
-- End of Migration
-- ============================================================================
