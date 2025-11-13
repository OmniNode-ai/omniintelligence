# Homelab-First Testing Approach

## Philosophy

The Archon RAG system is designed with a "homelab-first" testing philosophy. This means:

1. **Complete Self-Sufficiency**: Tests should run entirely within your local environment without requiring external API dependencies
2. **Provider Agnostic**: Code uses generic database terminology rather than provider-specific naming
3. **Local Development Stack**: Full database stack runs locally using Docker containers
4. **Mock External Services**: External APIs (like OpenAI embeddings) are mocked for testing

## Database Architecture

### Local Stack
- **Database**: PostgreSQL (compatible with Supabase)
- **API Gateway**: Kong
- **REST API**: PostgREST
- **Authentication**: GoTrue (optional for testing)

### Configuration Files
- `docker-compose.test.yml`: Local database stack
- `config/test-db/schema.sql`: Database schema initialization
- `config/test-supabase/permissions.sql`: Role permissions setup

## Testing Strategy

### Integration Tests
- Use `pytest` with async support
- Run against local database stack
- Include comprehensive cleanup mechanisms
- Production data protection guards

### Mock Services
- **Embedding Service**: Returns deterministic dummy vectors (1536-dimensional)
- **External APIs**: All external dependencies mocked for offline testing
- **Contextual Embeddings**: Mock implementation for testing

### Data Isolation
- Unique session IDs for test isolation
- Foreign key constraint handling
- Automatic cleanup of test data
- Multiple safety layers to prevent production data deletion

## Key Benefits

1. **Faster Development**: No network latency or rate limits
2. **Reliable Testing**: No external service outages affecting tests
3. **Cost Effective**: No API charges for development/testing
4. **Privacy**: No data sent to external services during testing
5. **Offline Capability**: Work without internet connection

## Provider Abstraction

The codebase has been refactored to use generic terms:
- `get_database_client()` instead of `get_supabase_client()`
- `add_documents_to_database()` instead of `add_documents_to_supabase()`
- `database_client` variables instead of `supabase_client`
- Generic comments and documentation

This abstraction allows for:
- Easy migration between database providers
- Clearer separation of concerns
- Better testability
- Reduced vendor lock-in

## Running Tests

```bash
# Start local database stack
docker-compose -f docker-compose.test.yml up -d

# Run integration tests
poetry run python run_rag_tests.py --safety-only

# Run with real integration tests (includes test data cleanup)
TESTING=true REAL_INTEGRATION_TESTS=true poetry run python run_rag_tests.py --safety-only
```

## Safety Mechanisms

1. **Environment Validation**: Ensures test environment is properly configured
2. **Production Guards**: Multiple checks to prevent accidental production data modification
3. **Session Isolation**: Unique test session IDs for data isolation
4. **Comprehensive Cleanup**: Automatic removal of test data and projects
5. **Foreign Key Handling**: Proper creation and cleanup of related records

This approach ensures robust, fast, and safe testing while maintaining compatibility with production database systems.
