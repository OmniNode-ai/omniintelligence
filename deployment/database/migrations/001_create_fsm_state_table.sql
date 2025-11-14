-- Migration: 001_create_fsm_state_table
-- Description: Create the unified FSM state tracking table
-- Author: omniintelligence
-- Date: 2025-11-14

-- ============================================================================
-- FSM State Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fsm_state (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- FSM identification
    fsm_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,

    -- State tracking
    current_state VARCHAR(50) NOT NULL,
    previous_state VARCHAR(50),
    transition_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Metadata
    metadata JSONB,

    -- Action lease management (for distributed coordination)
    lease_id VARCHAR(255),
    lease_epoch INTEGER,
    lease_expires_at TIMESTAMPTZ,

    -- Auditing
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraint: one FSM state per entity
    CONSTRAINT uq_fsm_entity UNIQUE (fsm_type, entity_id)
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Index for querying by FSM type and entity
CREATE INDEX IF NOT EXISTS idx_fsm_state_fsm_entity
    ON fsm_state(fsm_type, entity_id);

-- Index for querying by current state
CREATE INDEX IF NOT EXISTS idx_fsm_state_current_state
    ON fsm_state(current_state);

-- Index for finding entities in a specific state
CREATE INDEX IF NOT EXISTS idx_fsm_state_type_state
    ON fsm_state(fsm_type, current_state);

-- Index for lease management
CREATE INDEX IF NOT EXISTS idx_fsm_state_lease
    ON fsm_state(lease_id, lease_epoch)
    WHERE lease_id IS NOT NULL;

-- Index for expired leases cleanup
CREATE INDEX IF NOT EXISTS idx_fsm_state_lease_expiry
    ON fsm_state(lease_expires_at)
    WHERE lease_expires_at IS NOT NULL;

-- Index for transition timestamp queries
CREATE INDEX IF NOT EXISTS idx_fsm_state_transition_time
    ON fsm_state(transition_timestamp);

-- GIN index for JSONB metadata queries
CREATE INDEX IF NOT EXISTS idx_fsm_state_metadata
    ON fsm_state USING GIN (metadata);

-- ============================================================================
-- Trigger for updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_fsm_state_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_fsm_state_updated_at
    BEFORE UPDATE ON fsm_state
    FOR EACH ROW
    EXECUTE FUNCTION update_fsm_state_updated_at();

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE fsm_state IS 'Unified FSM state tracking for all intelligence FSMs';
COMMENT ON COLUMN fsm_state.fsm_type IS 'FSM type: INGESTION, PATTERN_LEARNING, QUALITY_ASSESSMENT';
COMMENT ON COLUMN fsm_state.entity_id IS 'Unique identifier for the entity being tracked';
COMMENT ON COLUMN fsm_state.current_state IS 'Current state in the FSM';
COMMENT ON COLUMN fsm_state.previous_state IS 'Previous state before last transition';
COMMENT ON COLUMN fsm_state.transition_timestamp IS 'Timestamp of last state transition';
COMMENT ON COLUMN fsm_state.metadata IS 'Additional metadata about the entity state';
COMMENT ON COLUMN fsm_state.lease_id IS 'Action lease ID for distributed coordination';
COMMENT ON COLUMN fsm_state.lease_epoch IS 'Lease epoch for preventing conflicts';
COMMENT ON COLUMN fsm_state.lease_expires_at IS 'Lease expiration timestamp';
