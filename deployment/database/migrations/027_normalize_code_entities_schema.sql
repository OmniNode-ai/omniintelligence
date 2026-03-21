-- Migration: 027_normalize_code_entities_schema.sql
-- Idempotent normalization for legacy code_entities/code_relationships schemas.
--
-- Three known legacy variants exist:
--   1. 025_create_code_entities.sql (simple): name, file_path, line_start, line_end, source_code
--   2. 025_code_entities.sql (rich): entity_name, qualified_name, source_path, line_number, signature, file_hash
--   3. Mixed state from partial manual migrations
--
-- This migration brings ALL variants to the canonical rich schema
-- defined in 025_code_entities.sql. It is fully idempotent and safe
-- to run multiple times.

DO $$ BEGIN

-- =====================================================================
-- code_entities: rename legacy columns to rich schema names
-- =====================================================================

-- name -> entity_name
IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'name'
) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'entity_name'
) THEN
    ALTER TABLE code_entities RENAME COLUMN name TO entity_name;
END IF;

-- file_path -> source_path
IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'file_path'
) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'source_path'
) THEN
    ALTER TABLE code_entities RENAME COLUMN file_path TO source_path;
END IF;

-- line_start -> line_number
IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'line_start'
) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'line_number'
) THEN
    ALTER TABLE code_entities RENAME COLUMN line_start TO line_number;
END IF;

-- =====================================================================
-- code_entities: add missing rich columns
-- =====================================================================

IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'qualified_name'
) THEN
    ALTER TABLE code_entities ADD COLUMN qualified_name TEXT;
    -- Backfill from source_path + entity_name if both exist
    UPDATE code_entities
    SET qualified_name = COALESCE(source_path, '') || ':' || COALESCE(entity_name, '')
    WHERE qualified_name IS NULL;
    ALTER TABLE code_entities ALTER COLUMN qualified_name SET NOT NULL;
END IF;

IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'signature'
) THEN
    ALTER TABLE code_entities ADD COLUMN signature TEXT;
END IF;

IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'fields'
) THEN
    ALTER TABLE code_entities ADD COLUMN fields JSONB;
END IF;

-- Enrichment fields (populated by LLM enrichment handler)
IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'classification'
) THEN
    ALTER TABLE code_entities ADD COLUMN classification TEXT;
END IF;

IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'llm_description'
) THEN
    ALTER TABLE code_entities ADD COLUMN llm_description TEXT;
END IF;

IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'architectural_pattern'
) THEN
    ALTER TABLE code_entities ADD COLUMN architectural_pattern TEXT;
END IF;

IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'classification_confidence'
) THEN
    ALTER TABLE code_entities ADD COLUMN classification_confidence FLOAT;
END IF;

IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'enrichment_version'
) THEN
    ALTER TABLE code_entities ADD COLUMN enrichment_version TEXT;
END IF;

-- Freshness timestamps
IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'last_extracted_at'
) THEN
    ALTER TABLE code_entities ADD COLUMN last_extracted_at TIMESTAMPTZ DEFAULT NOW();
END IF;

IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'last_enriched_at'
) THEN
    ALTER TABLE code_entities ADD COLUMN last_enriched_at TIMESTAMPTZ;
END IF;

IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'last_embedded_at'
) THEN
    ALTER TABLE code_entities ADD COLUMN last_embedded_at TIMESTAMPTZ;
END IF;

IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'last_graph_synced_at'
) THEN
    ALTER TABLE code_entities ADD COLUMN last_graph_synced_at TIMESTAMPTZ;
END IF;

-- =====================================================================
-- code_entities: drop orphan columns from simple schema
-- =====================================================================

IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'line_end'
) THEN
    ALTER TABLE code_entities DROP COLUMN line_end;
END IF;

IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'source_code'
) THEN
    ALTER TABLE code_entities DROP COLUMN source_code;
END IF;

IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_entities' AND column_name = 'embedding_id'
) THEN
    ALTER TABLE code_entities DROP COLUMN embedding_id;
END IF;

-- =====================================================================
-- code_entities: ensure canonical unique constraint
-- =====================================================================

-- Drop old unique constraint if it exists
IF EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'code_entities'
      AND constraint_type = 'UNIQUE'
      AND constraint_name = 'code_entities_source_repo_file_path_name_entity_type_key'
) THEN
    ALTER TABLE code_entities
    DROP CONSTRAINT code_entities_source_repo_file_path_name_entity_type_key;
END IF;

-- Add canonical unique constraint if missing
IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'code_entities'
      AND constraint_type = 'UNIQUE'
      AND constraint_name = 'code_entities_qualified_name_source_repo_key'
) THEN
    ALTER TABLE code_entities
    ADD CONSTRAINT code_entities_qualified_name_source_repo_key
    UNIQUE (qualified_name, source_repo);
END IF;

-- =====================================================================
-- code_relationships: add missing columns from rich schema
-- =====================================================================

IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_relationships' AND column_name = 'evidence'
) THEN
    ALTER TABLE code_relationships ADD COLUMN evidence TEXT[];
END IF;

IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_relationships' AND column_name = 'inject_into_context'
) THEN
    ALTER TABLE code_relationships ADD COLUMN inject_into_context BOOLEAN DEFAULT true;
END IF;

IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_relationships' AND column_name = 'source_repo'
) THEN
    ALTER TABLE code_relationships ADD COLUMN source_repo TEXT;
END IF;

IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_relationships' AND column_name = 'updated_at'
) THEN
    ALTER TABLE code_relationships ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
END IF;

-- Drop orphan metadata column from simple schema
IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'code_relationships' AND column_name = 'metadata'
) THEN
    ALTER TABLE code_relationships DROP COLUMN metadata;
END IF;

-- =====================================================================
-- Indexes: ensure canonical indexes exist
-- =====================================================================

CREATE INDEX IF NOT EXISTS idx_code_entities_qualified ON code_entities(qualified_name);
CREATE INDEX IF NOT EXISTS idx_code_entities_classification ON code_entities(classification);
CREATE INDEX IF NOT EXISTS idx_code_entities_file_path ON code_entities(source_path);
CREATE INDEX IF NOT EXISTS idx_code_relationships_injectable
    ON code_relationships(inject_into_context) WHERE inject_into_context = true;

END $$;
