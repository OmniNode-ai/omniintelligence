-- Migration: 003_create_workflow_executions
-- Description: Create table for workflow execution tracking
-- Author: omniintelligence
-- Date: 2025-11-14
--
-- Dependencies: 000_extensions.sql, 001_create_fsm_state_table.sql
-- Note: Reuses update_fsm_state_updated_at() function from 001

-- ============================================================================
-- Workflow Executions Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow_executions (
    -- Primary key
    workflow_id VARCHAR(255) PRIMARY KEY,

    -- Workflow identification
    operation_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,

    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'RUNNING',
    current_step VARCHAR(100),

    -- Progress tracking
    completed_steps JSONB DEFAULT '[]'::JSONB,
    failed_step VARCHAR(100),

    -- Timing
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms FLOAT,

    -- Context
    correlation_id VARCHAR(255) NOT NULL,
    input_payload JSONB,
    output_results JSONB,

    -- Error handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Metadata
    metadata JSONB,

    -- Auditing
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Index for querying by entity
CREATE INDEX IF NOT EXISTS idx_workflow_exec_entity
    ON workflow_executions(entity_id, started_at DESC);

-- Index for querying by status
CREATE INDEX IF NOT EXISTS idx_workflow_exec_status
    ON workflow_executions(status, started_at DESC);

-- Index for querying by operation type
CREATE INDEX IF NOT EXISTS idx_workflow_exec_operation
    ON workflow_executions(operation_type, started_at DESC);

-- Index for correlation ID tracking
CREATE INDEX IF NOT EXISTS idx_workflow_exec_correlation
    ON workflow_executions(correlation_id);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_workflow_exec_time
    ON workflow_executions(started_at DESC);

-- Index for finding stuck workflows
CREATE INDEX IF NOT EXISTS idx_workflow_exec_stuck
    ON workflow_executions(status, updated_at)
    WHERE status = 'RUNNING';

-- GIN indexes for JSONB columns
CREATE INDEX IF NOT EXISTS idx_workflow_exec_metadata
    ON workflow_executions USING GIN (metadata);

CREATE INDEX IF NOT EXISTS idx_workflow_exec_completed_steps
    ON workflow_executions USING GIN (completed_steps);

-- ============================================================================
-- Trigger for updated_at
-- ============================================================================

CREATE TRIGGER trigger_workflow_exec_updated_at
    BEFORE UPDATE ON workflow_executions
    FOR EACH ROW
    EXECUTE FUNCTION update_fsm_state_updated_at();  -- Reuse existing function

-- ============================================================================
-- Trigger to calculate duration on completion
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_workflow_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.completed_at IS NOT NULL AND OLD.completed_at IS NULL THEN
        NEW.duration_ms = EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_calculate_duration
    BEFORE UPDATE ON workflow_executions
    FOR EACH ROW
    EXECUTE FUNCTION calculate_workflow_duration();

-- ============================================================================
-- Workflow cleanup function
-- ============================================================================

CREATE OR REPLACE FUNCTION cleanup_completed_workflows(retention_days INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM workflow_executions
    WHERE status IN ('COMPLETED', 'FAILED')
    AND completed_at < NOW() - (retention_days || ' days')::INTERVAL;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_completed_workflows IS 'Clean up completed workflows older than specified days (default 30)';

-- ============================================================================
-- Function to find stuck workflows
-- ============================================================================

CREATE OR REPLACE FUNCTION find_stuck_workflows(timeout_hours INTEGER DEFAULT 24)
RETURNS TABLE (
    workflow_id VARCHAR(255),
    operation_type VARCHAR(50),
    current_step VARCHAR(100),
    stuck_duration_hours FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        we.workflow_id,
        we.operation_type,
        we.current_step,
        EXTRACT(EPOCH FROM (NOW() - we.updated_at)) / 3600 AS stuck_duration_hours
    FROM workflow_executions we
    WHERE we.status = 'RUNNING'
    AND we.updated_at < NOW() - (timeout_hours || ' hours')::INTERVAL
    ORDER BY we.updated_at ASC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION find_stuck_workflows IS 'Find workflows stuck in RUNNING state beyond timeout';

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE workflow_executions IS 'Tracks execution of orchestrator workflows';
COMMENT ON COLUMN workflow_executions.status IS 'Workflow status: RUNNING, COMPLETED, FAILED, PAUSED';
COMMENT ON COLUMN workflow_executions.completed_steps IS 'Array of completed step names';
COMMENT ON COLUMN workflow_executions.retry_count IS 'Number of retry attempts';
