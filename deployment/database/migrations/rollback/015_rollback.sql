-- Rollback: 015_create_db_metadata
-- Description: Drop db_metadata singleton table (boot-time handshake B1+B2)
-- Author: omniintelligence
-- Date: 2026-02-21
-- Ticket: OMN-2435

-- Drop trigger and function
DROP TRIGGER IF EXISTS trigger_db_metadata_updated_at ON db_metadata;
DROP FUNCTION IF EXISTS update_db_metadata_updated_at();

-- Drop table (CASCADE removes all dependent objects)
DROP TABLE IF EXISTS db_metadata CASCADE;
