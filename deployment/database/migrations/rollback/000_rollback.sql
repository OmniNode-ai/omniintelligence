-- Rollback: 000_extensions
-- Description: Drop PostgreSQL extensions
-- Author: omniintelligence
-- Date: 2025-01-18
--
-- WARNING: Dropping extensions will break any tables/functions that depend on them.
-- This rollback should only be run AFTER all dependent tables have been dropped.
-- Execute in reverse order: 003_rollback.sql, 002_rollback.sql, 001_rollback.sql, then 000_rollback.sql

-- Drop extensions in reverse order of typical dependencies
DROP EXTENSION IF EXISTS pg_trgm CASCADE;
DROP EXTENSION IF EXISTS "uuid-ossp" CASCADE;
DROP EXTENSION IF EXISTS pgcrypto CASCADE;
