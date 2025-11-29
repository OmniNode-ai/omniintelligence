-- Rollback: 001_create_fsm_state_table
-- Description: Drop fsm_state table and related objects
-- Author: omniintelligence
-- Date: 2025-11-14

-- Drop trigger
DROP TRIGGER IF EXISTS trigger_fsm_state_updated_at ON fsm_state;

-- Drop function
DROP FUNCTION IF EXISTS update_fsm_state_updated_at();

-- Drop indexes
DROP INDEX IF EXISTS idx_fsm_state_metadata;
DROP INDEX IF EXISTS idx_fsm_state_transition_time;
DROP INDEX IF EXISTS idx_fsm_state_lease_expiry;
DROP INDEX IF EXISTS idx_fsm_state_lease;
DROP INDEX IF EXISTS idx_fsm_state_type_state;
DROP INDEX IF EXISTS idx_fsm_state_current_state;
DROP INDEX IF EXISTS idx_fsm_state_fsm_entity;

-- Drop table
DROP TABLE IF EXISTS fsm_state CASCADE;
