-- Migration: 000_extensions
-- Description: Create required PostgreSQL extensions
-- Author: omniintelligence
-- Date: 2025-01-18
--
-- IMPORTANT: This file MUST run first (alphabetically ordered) to ensure
-- extensions are available before any table uses them.
--
-- PostgreSQL docker-entrypoint-initdb.d executes *.sql files in alphabetical
-- order, so 000_ prefix guarantees this runs before 001_, 002_, etc.

-- ============================================================================
-- Required Extensions
-- ============================================================================

-- pgcrypto: Cryptographic functions including secure random generation
-- Used for: gen_random_uuid() fallback (native in PG13+), password hashing,
--           secure random bytes, encryption/decryption functions
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- uuid-ossp: UUID generation functions
-- Used for: uuid_generate_v4(), uuid_generate_v1(), uuid_generate_v1mc()
-- Note: gen_random_uuid() is native to PostgreSQL 13+ and preferred for
--       random UUIDs, but uuid-ossp provides additional generation methods
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- pg_trgm: Trigram text similarity and indexing
-- Used for: Pattern matching, fuzzy text search, similarity scoring
-- Enables: similarity(), word_similarity(), GIN/GiST trigram indexes
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- Verification Query (for debugging/validation)
-- ============================================================================
-- Uncomment to verify extensions are installed:
-- SELECT extname, extversion FROM pg_extension
-- WHERE extname IN ('pgcrypto', 'uuid-ossp', 'pg_trgm')
-- ORDER BY extname;

-- ============================================================================
-- Extension Notes
-- ============================================================================
--
-- Future extensions that may be needed:
-- - vector (pgvector): For embedding storage and similarity search
--   CREATE EXTENSION IF NOT EXISTS vector;
--
-- - hstore: Key-value pair storage
--   CREATE EXTENSION IF NOT EXISTS hstore;
--
-- - btree_gin: GIN index support for scalar types
--   CREATE EXTENSION IF NOT EXISTS btree_gin;
--
-- - pg_stat_statements: Query performance statistics
--   CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
