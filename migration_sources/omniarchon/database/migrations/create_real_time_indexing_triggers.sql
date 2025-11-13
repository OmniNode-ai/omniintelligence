-- Real-time Indexing Triggers for Archon
-- This migration creates PostgreSQL triggers that automatically trigger
-- document indexing when documents are created or updated in the archon_projects table

-- Enable the http extension for making HTTP requests from within PostgreSQL
CREATE EXTENSION IF NOT EXISTS http;

-- Create a function to trigger document indexing via HTTP webhook
CREATE OR REPLACE FUNCTION trigger_document_indexing()
RETURNS trigger AS $$
DECLARE
    doc_data jsonb;
    doc_record jsonb;
    payload jsonb;
    response http_response;
    intelligence_service_url text;
    auto_indexing_enabled text;
BEGIN
    -- Check if auto-indexing is enabled (default: true)
    auto_indexing_enabled := coalesce(current_setting('app.auto_indexing_enabled', true), 'true');

    IF auto_indexing_enabled != 'true' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    -- Get intelligence service URL from environment variable
    intelligence_service_url := coalesce(current_setting('app.intelligence_service_url', true), 'http://archon-intelligence:8053');

    -- Handle different trigger operations
    IF TG_OP = 'INSERT' THEN
        doc_data := NEW.docs;
    ELSIF TG_OP = 'UPDATE' THEN
        doc_data := NEW.docs;
    ELSE
        RETURN OLD;
    END IF;

    -- Process each document in the docs JSONB array
    IF doc_data IS NOT NULL AND jsonb_array_length(doc_data) > 0 THEN
        FOR doc_record IN SELECT * FROM jsonb_array_elements(doc_data)
        LOOP
            -- Only process documents that were recently created or modified
            -- Check for new documents (no updated_at) or recently updated documents
            IF (doc_record->>'updated_at' IS NULL AND TG_OP = 'INSERT') OR
               (doc_record->>'updated_at' IS NOT NULL AND
                (doc_record->>'updated_at')::timestamp > (NOW() - INTERVAL '1 minute')) THEN

                -- Prepare payload for intelligence service
                payload := jsonb_build_object(
                    'document_id', doc_record->>'id',
                    'project_id', NEW.id,
                    'title', doc_record->>'title',
                    'content', doc_record->'content',
                    'document_type', doc_record->>'document_type',
                    'metadata', jsonb_build_object(
                        'tags', doc_record->'tags',
                        'author', doc_record->>'author',
                        'status', doc_record->>'status',
                        'version', doc_record->>'version',
                        'created_at', coalesce(doc_record->>'created_at', NEW.created_at::text),
                        'updated_at', coalesce(doc_record->>'updated_at', NEW.updated_at::text),
                        'trigger_source', 'database_trigger'
                    )
                );

                -- Make HTTP request to intelligence service (async, fire-and-forget)
                BEGIN
                    SELECT * INTO response FROM http_post(
                        intelligence_service_url || '/process/document',
                        payload::text,
                        'application/json'
                    );

                    -- Log successful trigger
                    RAISE NOTICE 'Document indexing triggered for document_id: %, status: %',
                        doc_record->>'id', response.status;

                EXCEPTION WHEN others THEN
                    -- Log error but don't fail the transaction
                    RAISE WARNING 'Failed to trigger document indexing for document_id: %, error: %',
                        doc_record->>'id', SQLERRM;
                END;

            END IF;
        END LOOP;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Create triggers for INSERT and UPDATE operations on archon_projects
DROP TRIGGER IF EXISTS trigger_document_indexing_insert ON archon_projects;
DROP TRIGGER IF EXISTS trigger_document_indexing_update ON archon_projects;

CREATE TRIGGER trigger_document_indexing_insert
    AFTER INSERT ON archon_projects
    FOR EACH ROW
    WHEN (NEW.docs IS NOT NULL AND jsonb_array_length(NEW.docs) > 0)
    EXECUTE FUNCTION trigger_document_indexing();

CREATE TRIGGER trigger_document_indexing_update
    AFTER UPDATE OF docs ON archon_projects
    FOR EACH ROW
    WHEN (NEW.docs IS DISTINCT FROM OLD.docs AND NEW.docs IS NOT NULL)
    EXECUTE FUNCTION trigger_document_indexing();

-- Create a function to manually trigger indexing for existing documents
CREATE OR REPLACE FUNCTION manual_trigger_document_indexing(project_id_param uuid)
RETURNS text AS $$
DECLARE
    project_record record;
    doc_record jsonb;
    payload jsonb;
    response http_response;
    intelligence_service_url text;
    processed_count integer := 0;
BEGIN
    -- Get intelligence service URL
    intelligence_service_url := coalesce(current_setting('app.intelligence_service_url', true), 'http://archon-intelligence:8053');

    -- Get the project
    SELECT * INTO project_record FROM archon_projects WHERE id = project_id_param;

    IF NOT FOUND THEN
        RETURN 'Project not found: ' || project_id_param::text;
    END IF;

    -- Process each document in the project
    IF project_record.docs IS NOT NULL AND jsonb_array_length(project_record.docs) > 0 THEN
        FOR doc_record IN SELECT * FROM jsonb_array_elements(project_record.docs)
        LOOP
            -- Prepare payload for intelligence service
            payload := jsonb_build_object(
                'document_id', doc_record->>'id',
                'project_id', project_record.id,
                'title', doc_record->>'title',
                'content', doc_record->'content',
                'document_type', doc_record->>'document_type',
                'metadata', jsonb_build_object(
                    'tags', doc_record->'tags',
                    'author', doc_record->>'author',
                    'status', doc_record->>'status',
                    'version', doc_record->>'version',
                    'created_at', coalesce(doc_record->>'created_at', project_record.created_at::text),
                    'updated_at', coalesce(doc_record->>'updated_at', project_record.updated_at::text),
                    'trigger_source', 'manual_reindex'
                )
            );

            -- Make HTTP request to intelligence service
            BEGIN
                SELECT * INTO response FROM http_post(
                    intelligence_service_url || '/process/document',
                    payload::text,
                    'application/json'
                );

                processed_count := processed_count + 1;

            EXCEPTION WHEN others THEN
                RAISE WARNING 'Failed to trigger indexing for document_id: %, error: %',
                    doc_record->>'id', SQLERRM;
            END;
        END LOOP;
    END IF;

    RETURN 'Triggered indexing for ' || processed_count || ' documents in project ' || project_id_param::text;
END;
$$ LANGUAGE plpgsql;

-- Create a function to reindex all documents in all projects (use with caution)
CREATE OR REPLACE FUNCTION reindex_all_documents()
RETURNS text AS $$
DECLARE
    project_record record;
    total_processed integer := 0;
    result_text text;
BEGIN
    FOR project_record IN SELECT id FROM archon_projects WHERE docs IS NOT NULL
    LOOP
        SELECT manual_trigger_document_indexing(project_record.id) INTO result_text;

        -- Extract the count from the result
        total_processed := total_processed +
            CAST(split_part(split_part(result_text, 'Triggered indexing for ', 2), ' documents', 1) AS integer);
    END LOOP;

    RETURN 'Reindexed ' || total_processed || ' documents across all projects';
END;
$$ LANGUAGE plpgsql;

-- Set up configuration parameters for the triggers
-- These can be overridden in the database environment
SELECT set_config('app.auto_indexing_enabled', 'true', false);
SELECT set_config('app.intelligence_service_url', 'http://archon-intelligence:8053', false);

-- Create indexes to improve trigger performance
CREATE INDEX IF NOT EXISTS idx_archon_projects_docs_gin ON archon_projects USING gin (docs);
CREATE INDEX IF NOT EXISTS idx_archon_projects_updated_at ON archon_projects (updated_at);

-- Grant necessary permissions for the http extension
-- Note: This may require superuser permissions in some PostgreSQL configurations
-- GRANT USAGE ON SCHEMA public TO postgres;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO postgres;

-- Informational comments for maintenance
COMMENT ON FUNCTION trigger_document_indexing() IS 'Automatically triggers document indexing when documents are created or updated';
COMMENT ON FUNCTION manual_trigger_document_indexing(uuid) IS 'Manually trigger indexing for all documents in a specific project';
COMMENT ON FUNCTION reindex_all_documents() IS 'Reindex all documents in all projects - use with caution in production';

-- Log successful migration
DO $$
BEGIN
    RAISE NOTICE 'Real-time indexing triggers created successfully';
    RAISE NOTICE 'Auto-indexing enabled: %', current_setting('app.auto_indexing_enabled');
    RAISE NOTICE 'Intelligence service URL: %', current_setting('app.intelligence_service_url');
END $$;
