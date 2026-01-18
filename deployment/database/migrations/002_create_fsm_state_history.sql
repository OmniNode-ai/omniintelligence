-- Migration: 002_create_fsm_state_history
-- Description: Create table for FSM state transition history
-- Author: omniintelligence
-- Date: 2025-11-14
--
-- Dependencies: 000_extensions.sql, 001_create_fsm_state_table.sql

-- ============================================================================
-- FSM State History Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fsm_state_history (
    -- Primary key
    id BIGSERIAL PRIMARY KEY,

    -- FSM identification
    fsm_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,

    -- State transition
    from_state VARCHAR(50),
    to_state VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,

    -- Timing
    transitioned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    duration_ms FLOAT,

    -- Context
    correlation_id VARCHAR(255),
    metadata JSONB,

    -- Result
    success BOOLEAN NOT NULL DEFAULT TRUE,
    error_message TEXT,

    -- Partitioning key (for future partitioning by time)
    partition_key DATE NOT NULL DEFAULT CURRENT_DATE
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Index for querying history by entity
CREATE INDEX IF NOT EXISTS idx_fsm_history_entity
    ON fsm_state_history(fsm_type, entity_id, transitioned_at DESC);

-- Index for correlation ID tracking
CREATE INDEX IF NOT EXISTS idx_fsm_history_correlation
    ON fsm_state_history(correlation_id);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_fsm_history_time
    ON fsm_state_history(transitioned_at DESC);

-- Index for failed transitions
CREATE INDEX IF NOT EXISTS idx_fsm_history_failures
    ON fsm_state_history(fsm_type, success)
    WHERE success = FALSE;

-- Index for partition key (for future partitioning)
CREATE INDEX IF NOT EXISTS idx_fsm_history_partition
    ON fsm_state_history(partition_key);

-- GIN index for JSONB metadata
CREATE INDEX IF NOT EXISTS idx_fsm_history_metadata
    ON fsm_state_history USING GIN (metadata);

-- ============================================================================
-- Trigger to record history on state changes
-- ============================================================================

CREATE OR REPLACE FUNCTION record_fsm_state_history()
RETURNS TRIGGER AS $$
BEGIN
    -- Only record if state actually changed
    IF (TG_OP = 'UPDATE' AND OLD.current_state != NEW.current_state) OR TG_OP = 'INSERT' THEN
        INSERT INTO fsm_state_history (
            fsm_type,
            entity_id,
            from_state,
            to_state,
            action,
            transitioned_at,
            duration_ms,
            correlation_id,
            metadata,
            success
        ) VALUES (
            NEW.fsm_type,
            NEW.entity_id,
            OLD.current_state,  -- NULL for INSERT
            NEW.current_state,
            COALESCE(NEW.metadata->>'last_action', 'UNKNOWN'),
            NEW.transition_timestamp,
            CASE
                WHEN OLD.transition_timestamp IS NOT NULL THEN
                    EXTRACT(EPOCH FROM (NEW.transition_timestamp - OLD.transition_timestamp)) * 1000
                ELSE NULL
            END,
            NEW.metadata->>'correlation_id',
            NEW.metadata,
            TRUE
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_record_fsm_history
    AFTER INSERT OR UPDATE ON fsm_state
    FOR EACH ROW
    EXECUTE FUNCTION record_fsm_state_history();

-- ============================================================================
-- Cleanup function for old history
-- ============================================================================

CREATE OR REPLACE FUNCTION cleanup_old_fsm_history(retention_days INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM fsm_state_history
    WHERE transitioned_at < NOW() - (retention_days || ' days')::INTERVAL;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_fsm_history IS 'Clean up FSM history older than specified days (default 90)';

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE fsm_state_history IS 'Historical record of all FSM state transitions';
COMMENT ON COLUMN fsm_state_history.duration_ms IS 'Time spent in previous state (milliseconds)';
COMMENT ON COLUMN fsm_state_history.action IS 'Action that caused the transition';
COMMENT ON COLUMN fsm_state_history.partition_key IS 'Date for future table partitioning';
