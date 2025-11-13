# Testing Documentation

**Version**: 1.0.0 | **Date**: 2025-10-29

Comprehensive testing guide for Archon services, covering Supabase removal, Consul integration, and event-driven architecture.

## Table of Contents

1. [Overview](#overview)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Unit Tests](#unit-tests)
5. [Integration Tests](#integration-tests)
6. [End-to-End Tests](#end-to-end-tests)
7. [Test Fixtures](#test-fixtures)
8. [Coverage Requirements](#coverage-requirements)
9. [CI/CD Integration](#cicd-integration)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The Archon test suite validates:

**✅ Supabase Removal & Graceful Degradation**
- Service startup without Supabase
- Fallback to environment variables
- Graceful error handling

**✅ Consul Integration**
- Service registration/deregistration
- Service discovery
- Health check monitoring

**✅ Event-Driven Architecture**
- Kafka event publishing/consumption
- Vector indexing pipeline
- Service coordination

### Test Categories

| Category | Location | Purpose | Run Command |
|----------|----------|---------|-------------|
| **Unit Tests** | `tests/unit/services/` | Test individual components in isolation | `pytest tests/unit/` |
| **Integration Tests** | `tests/integration/` | Test service interactions | `pytest tests/integration/` |
| **End-to-End Tests** | `tests/e2e/` | Test complete workflows | `pytest tests/e2e/ --real-integration` |

---

## Test Structure

```
python/tests/
├── conftest.py                           # Shared fixtures and configuration
├── unit/
│   └── services/
│       ├── test_credential_service.py    # Credential service unit tests
│       ├── test_consul_service.py        # Consul service unit tests
│       └── test_kafka_consumer_service.py # Kafka consumer tests
├── integration/
│   ├── test_consul_integration.py        # Consul integration tests
│   └── test_supabase_fallback.py         # Supabase fallback tests
└── e2e/
    ├── test_event_pipeline.py            # Event pipeline E2E tests
    └── test_service_discovery.py         # Service discovery E2E tests
```

---

## Running Tests

### Quick Start

```bash
# Run all tests (unit + integration, mocked)
pytest

# Run with coverage
pytest --cov=src/server/services --cov-report=term-missing

# Run specific test category
pytest tests/unit/                # Unit tests only
pytest tests/integration/         # Integration tests only
pytest tests/e2e/                 # E2E tests only (mocked)
```

### Real Integration Tests

**⚠️ Requires running services:**
- Consul: `192.168.86.200:8500`
- Kafka/Redpanda: `192.168.86.200:29092`
- Qdrant: `localhost:6333`

```bash
# Run real integration tests
pytest tests/integration/test_consul_integration.py --real-integration
pytest tests/e2e/test_event_pipeline.py --real-integration
pytest tests/e2e/test_service_discovery.py --real-integration

# Run all real integration tests
pytest --real-integration
```

### Coverage Analysis

```bash
# Generate coverage report
pytest --cov=src/server/services \
       --cov=src/server/utils \
       --cov-report=html \
       --cov-report=term-missing

# Open HTML coverage report
open htmlcov/index.html

# Coverage with specific threshold
pytest --cov=src/server/services --cov-fail-under=90
```

### Parallel Execution

```bash
# Run tests in parallel (4 workers)
pytest -n 4

# Auto-detect CPU cores
pytest -n auto
```

---

## Unit Tests

### Credential Service Tests

**File**: `tests/unit/services/test_credential_service.py`

**Coverage**: 95%+ (target)

**Test Classes**:

```python
TestCredentialServiceGracefulDegradation
├── test_load_credentials_without_supabase
├── test_get_credential_with_unavailable_supabase
├── test_set_credential_fails_gracefully_without_supabase
└── test_get_credentials_by_category_without_supabase

TestCredentialServiceWithSupabase
├── test_load_all_credentials_success
├── test_get_credential_with_decryption
├── test_set_credential_encrypted
└── test_delete_credential

TestCredentialServiceEncryption
├── test_encrypt_value
├── test_decrypt_value
└── test_decrypt_invalid_value_fails

TestCredentialServiceCache
├── test_cache_initialization
├── test_rag_settings_cache
└── test_rag_cache_invalidation_on_set

TestCredentialServiceProviderManagement
├── test_get_active_provider_openai
├── test_get_active_provider_ollama
└── test_get_active_provider_fallback_to_env
```

**Key Tests**:

```bash
# Run credential service tests
pytest tests/unit/services/test_credential_service.py -v

# Run specific test class
pytest tests/unit/services/test_credential_service.py::TestCredentialServiceGracefulDegradation -v

# Run specific test
pytest tests/unit/services/test_credential_service.py::TestCredentialServiceGracefulDegradation::test_load_credentials_without_supabase -v
```

### Consul Service Tests

**File**: `tests/unit/services/test_consul_service.py`

**Coverage**: 95%+ (target)

**Test Classes**:

```python
TestConsulServiceInitialization
├── test_initialization_enabled
├── test_initialization_disabled
└── test_initialization_with_env_vars

TestConsulServiceRegistration
├── test_register_service_basic
├── test_register_service_with_health_check
└── test_register_service_with_tags

TestConsulServiceDeregistration
├── test_deregister_service_success
└── test_deregister_service_failure

TestConsulServiceDiscovery
├── test_discover_service_success
├── test_discover_service_with_tag_filter
└── test_discover_service_multiple_instances

TestConsulServiceURL
├── test_get_service_url_success
├── test_get_service_url_https
└── test_get_service_url_no_instances

TestConsulServiceCleanup
├── test_cleanup_deregisters_all_services
└── test_cleanup_when_disabled
```

**Key Tests**:

```bash
# Run consul service tests
pytest tests/unit/services/test_consul_service.py -v

# Test registration workflow
pytest tests/unit/services/test_consul_service.py::TestConsulServiceRegistration -v

# Test discovery workflow
pytest tests/unit/services/test_consul_service.py::TestConsulServiceDiscovery -v
```

---

## Integration Tests

### Consul Integration Tests

**File**: `tests/integration/test_consul_integration.py`

**Requires**: Real Consul instance at `192.168.86.200:8500`

**Test Classes**:

```python
TestConsulIntegrationRegistration
├── test_register_and_discover_service
├── test_register_with_health_check
└── test_deregister_service

TestConsulIntegrationDiscovery
├── test_discover_multiple_instances
├── test_discover_with_tag_filter
└── test_get_service_url

TestConsulIntegrationGracefulDegradation
├── test_service_continues_without_consul
└── test_operations_when_disabled

TestConsulIntegrationCleanup
└── test_cleanup_deregisters_all

TestConsulIntegrationMultiService
├── test_multiple_services_register_simultaneously
└── test_service_discovery_across_services
```

**Running**:

```bash
# Run with real Consul
pytest tests/integration/test_consul_integration.py --real-integration

# Run specific test
pytest tests/integration/test_consul_integration.py::TestConsulIntegrationRegistration::test_register_and_discover_service --real-integration
```

### Supabase Fallback Tests

**File**: `tests/integration/test_supabase_fallback.py`

**Test Classes**:

```python
TestSupabaseFallbackStartup
├── test_credential_service_starts_without_supabase
├── test_initialize_credentials_without_supabase
└── test_service_uses_environment_variables_as_fallback

TestSupabaseFallbackOperations
├── test_get_credential_returns_default_without_supabase
├── test_set_credential_fails_gracefully_without_supabase
└── test_delete_credential_fails_gracefully_without_supabase

TestSupabaseFallbackProviderManagement
├── test_get_active_provider_uses_environment_fallback
└── test_get_active_provider_ollama_with_env_fallback

TestSupabaseFallbackApplicationFlow
├── test_application_initialization_without_supabase
└── test_credential_service_continues_after_supabase_failure

TestSupabaseFallbackE2EScenarios
└── test_e2e_application_startup_without_supabase
```

**Running**:

```bash
# Run Supabase fallback tests
pytest tests/integration/test_supabase_fallback.py -v

# Test complete application flow
pytest tests/integration/test_supabase_fallback.py::TestSupabaseFallbackApplicationFlow -v
```

---

## End-to-End Tests

### Event Pipeline Tests

**File**: `tests/e2e/test_event_pipeline.py`

**Requires**:
- Kafka/Redpanda: `192.168.86.200:29092`
- archon-intelligence: `localhost:8053`
- Qdrant: `localhost:6333`

**Test Classes**:

```python
TestEventPipelinePublishing
├── test_publish_tree_discover_event
├── test_publish_stamping_generate_event
└── test_publish_tree_index_event

TestEventPipelineConsumption
└── test_publish_and_consume_event

TestEventPipelineVectorIndexing
└── test_document_indexing_creates_vector

TestEventPipelineCompleteFlow
└── test_complete_ingestion_pipeline

TestEventPipelinePerformance
└── test_bulk_event_publishing
```

**Running**:

```bash
# Run with real services
pytest tests/e2e/test_event_pipeline.py --real-integration

# Test specific workflow
pytest tests/e2e/test_event_pipeline.py::TestEventPipelineCompleteFlow --real-integration
```

### Service Discovery Tests

**File**: `tests/e2e/test_service_discovery.py`

**Requires**: Real Consul at `192.168.86.200:8500`

**Test Classes**:

```python
TestServiceDiscoveryRegistration
└── test_multiple_services_register_on_startup

TestServiceDiscoveryLookup
├── test_server_discovers_intelligence_service
├── test_discover_service_by_tag
└── test_discover_all_instances_of_service

TestServiceDiscoveryHealthChecks
└── test_service_health_check_failure

TestServiceDiscoveryFailover
├── test_discover_healthy_instance_after_unhealthy
└── test_service_deregistration_removes_from_discovery

TestServiceDiscoveryCompleteWorkflow
├── test_complete_service_lifecycle
└── test_multi_service_coordination
```

**Running**:

```bash
# Run with real Consul
pytest tests/e2e/test_service_discovery.py --real-integration

# Test complete lifecycle
pytest tests/e2e/test_service_discovery.py::TestServiceDiscoveryCompleteWorkflow --real-integration
```

---

## Test Fixtures

### Global Fixtures (conftest.py)

**Mocking Fixtures**:
```python
@pytest.fixture
def mock_database_client():
    """Mock Supabase client"""

@pytest.fixture
def mock_consul_client():
    """Mock Consul client"""

@pytest.fixture
def mock_kafka_producer():
    """Mock Kafka producer"""

@pytest.fixture
def mock_kafka_consumer():
    """Mock Kafka consumer"""
```

**Environment Fixtures**:
```python
@pytest.fixture
def test_env_credentials():
    """Test environment credentials"""

@pytest.fixture
def test_timeouts():
    """Configurable test timeouts"""
```

**Service Fixtures**:
```python
@pytest.fixture
def client():
    """FastAPI test client with mocked database"""

@pytest.fixture
def auth_client():
    """Authenticated test client"""
```

### Using Fixtures

```python
def test_my_feature(mock_database_client, test_env_credentials):
    """Test using multiple fixtures."""
    # Fixtures automatically injected by pytest
    assert mock_database_client is not None
    assert test_env_credentials["OPENAI_API_KEY"] == "test-openai-key"
```

---

## Coverage Requirements

### Target Coverage

| Component | Target | Current |
|-----------|--------|---------|
| **credential_service.py** | >90% | Testing required |
| **consul_service.py** | >90% | Testing required |
| **Overall Services** | >85% | Testing required |

### Measuring Coverage

```bash
# Run coverage for specific modules
pytest --cov=src/server/services.credential_service \
       --cov=src/server/services.consul_service \
       --cov-report=term-missing

# Generate HTML report
pytest --cov=src/server/services --cov-report=html

# Fail if coverage below threshold
pytest --cov=src/server/services --cov-fail-under=90
```

### Coverage Report Example

```
Name                                   Stmts   Miss  Cover   Missing
--------------------------------------------------------------------
credential_service.py                    245     15    94%   123-125, 301
consul_service.py                        180      8    96%   234-236
--------------------------------------------------------------------
TOTAL                                    425     23    95%
```

---

## CI/CD Integration

### GitHub Actions Workflow

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      consul:
        image: hashicorp/consul:latest
        ports:
          - 8500:8500

      kafka:
        image: vectorized/redpanda:latest
        ports:
          - 29092:29092

      qdrant:
        image: qdrant/qdrant:latest
        ports:
          - 6333:6333

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync --all-groups

      - name: Run unit tests
        run: pytest tests/unit/ --cov=src/server/services --cov-report=xml

      - name: Run integration tests
        run: pytest tests/integration/ --real-integration

      - name: Run E2E tests
        run: pytest tests/e2e/ --real-integration

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml
```

### Pre-commit Hooks

```bash
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
        args: ['tests/unit/', '--cov=src/server/services', '--cov-fail-under=90']
```

---

## Troubleshooting

### Common Issues

#### 1. "Real database calls are not allowed in tests!"

**Cause**: Test trying to connect to Supabase without proper mocking.

**Solution**:
```python
# Use --real-integration flag for integration tests
pytest tests/integration/test_consul_integration.py --real-integration

# Or mark test with @pytest.mark.real_integration
@pytest.mark.real_integration
def test_my_integration():
    pass
```

#### 2. "Consul not available"

**Cause**: Real Consul instance not running.

**Solution**:
```bash
# Check Consul status
curl http://192.168.86.200:8500/v1/status/leader

# Or skip real integration tests
pytest tests/integration/test_consul_integration.py  # Uses mocks

# Or start Consul locally
docker run -d -p 8500:8500 hashicorp/consul:latest
```

#### 3. "Event consumption timed out"

**Cause**: Kafka/Redpanda not running or archon-intelligence not consuming events.

**Solution**:
```bash
# Verify Kafka connectivity
nc -zv 192.168.86.200 29092

# Check archon-intelligence service
docker ps | grep archon-intelligence

# Verify topic exists
docker exec archon-bridge rpk topic list
```

#### 4. "Import errors"

**Cause**: Missing test dependencies.

**Solution**:
```bash
# Install all dependencies
uv sync --all-groups

# Or with pip
pip install -e ".[dev]"
```

#### 5. "Coverage below threshold"

**Cause**: Insufficient test coverage for new code.

**Solution**:
```bash
# Identify untested lines
pytest --cov=src/server/services --cov-report=term-missing

# Add tests for missing lines
# Re-run coverage check
```

### Debug Mode

```bash
# Run tests with verbose output
pytest -vv

# Show print statements
pytest -s

# Stop on first failure
pytest -x

# Start debugger on failure
pytest --pdb

# Run specific test with detailed output
pytest tests/unit/services/test_credential_service.py::TestCredentialServiceGracefulDegradation::test_load_credentials_without_supabase -vvs
```

### Performance Debugging

```bash
# Show slowest tests
pytest --durations=10

# Profile test execution
pytest --profile

# Time each test
pytest --durations=0
```

---

## Best Practices

### 1. Test Isolation

**✅ Good**:
```python
def test_with_fresh_service():
    service = CredentialService()  # New instance per test
    result = await service.load_all_credentials()
    assert result == {}
```

**❌ Bad**:
```python
service = CredentialService()  # Shared state

def test_one():
    service.cache = {"key": "value"}  # Pollutes other tests

def test_two():
    assert service.cache == {}  # Fails due to test_one
```

### 2. Mock External Dependencies

**✅ Good**:
```python
@patch("src.server.services.consul_service.consul.Consul")
def test_with_mock(mock_consul):
    mock_consul.return_value = MagicMock()
    service = ConsulService(enabled=True)
    # Test without real Consul
```

**❌ Bad**:
```python
def test_without_mock():
    service = ConsulService(enabled=True)  # Requires real Consul
    # Test fails if Consul unavailable
```

### 3. Use Fixtures for Setup

**✅ Good**:
```python
@pytest.fixture
def credential_service():
    service = CredentialService()
    yield service
    # Automatic cleanup

def test_with_fixture(credential_service):
    result = await credential_service.load_all_credentials()
```

**❌ Bad**:
```python
def test_with_manual_setup():
    service = CredentialService()  # Manual setup
    result = await service.load_all_credentials()
    # No cleanup
```

### 4. Test Edge Cases

```python
def test_edge_cases():
    # Test empty input
    assert process_data("") == {}

    # Test None input
    assert process_data(None) == {}

    # Test large input
    assert len(process_data("x" * 100000)) > 0

    # Test invalid input
    with pytest.raises(ValueError):
        process_data(invalid_data)
```

### 5. Use Meaningful Test Names

**✅ Good**:
```python
def test_credential_service_starts_successfully_when_supabase_unavailable():
    pass

def test_consul_registration_includes_health_check_with_correct_interval():
    pass
```

**❌ Bad**:
```python
def test_1():
    pass

def test_service():
    pass
```

---

## Resources

- **pytest Documentation**: https://docs.pytest.org/
- **pytest-asyncio**: https://pytest-asyncio.readthedocs.io/
- **pytest-cov**: https://pytest-cov.readthedocs.io/
- **pytest-mock**: https://pytest-mock.readthedocs.io/

---

## Summary

**Test Suite Overview**:
- ✅ **6 test files** created
- ✅ **118+ test cases** covering unit, integration, and E2E scenarios
- ✅ **95%+ coverage target** for new code
- ✅ **Mock-based tests** (no external services required)
- ✅ **Real integration tests** (with `--real-integration` flag)
- ✅ **CI/CD ready** (GitHub Actions compatible)

**Quick Start**:
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/server/services --cov-report=term-missing

# Run real integration tests
pytest --real-integration
```

**Coverage Command**:
```bash
pytest tests/unit/services/ \
  --cov=src/server/services.credential_service \
  --cov=src/server/services.consul_service \
  --cov-report=term-missing \
  --cov-fail-under=90
```

---

**Last Updated**: 2025-10-29 | **Version**: 1.0.0
