# Archon DevOps Makefile
# Simplified commands for development, testing, and deployment

.PHONY: help dev-start dev-stop test build deploy-staging deploy-production monitoring clean

# Default target
help: ## Show this help message
	@echo "Archon DevOps Commands"
	@echo "====================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development Commands
dev-start: ## Start development environment
	@echo "🚀 Starting development environment..."
	docker compose up -d
	@echo "⏳ Waiting for services to be ready..."
	./scripts/wait-for-services.sh
	@echo "✅ Development environment ready!"
	@echo "   Frontend: http://localhost:3737"
	@echo "   Backend:  http://localhost:8181"
	@echo "   MCP:      http://localhost:8051"

dev-start-full: ## Start development environment with all services
	@echo "🚀 Starting full development environment with agents..."
	docker compose --profile agents up -d
	./scripts/wait-for-services.sh

dev-stop: ## Stop development environment
	@echo "🛑 Stopping development environment..."
	docker compose down

dev-restart: ## Restart development environment
	@echo "🔄 Restarting development environment..."
	docker compose restart

dev-logs: ## Show development logs
	docker compose logs -f

dev-clean: ## Clean development environment (removes volumes)
	@echo "🧹 Cleaning development environment..."
	docker compose down -v
	docker system prune -f

# Testing Commands
test: ## Run all tests
	@echo "🧪 Running all tests..."
	docker compose -f deployment/docker-compose.test.yml up --build --abort-on-container-exit
	docker compose -f deployment/docker-compose.test.yml down

test-backend: ## Run backend tests only
	@echo "🧪 Running backend tests..."
	cd python && poetry run python -m pytest tests/ -v --cov=src

test-frontend: ## Run frontend tests only
	@echo "🧪 Running frontend tests..."
	cd archon-ui-main && npm test

test-e2e: ## Run end-to-end tests
	@echo "🧪 Running E2E tests..."
	docker compose -f deployment/docker-compose.test.yml up -d
	./scripts/wait-for-services.sh
	docker compose -f deployment/docker-compose.test.yml exec archon-server poetry run pytest tests/e2e/ -v
	docker compose -f deployment/docker-compose.test.yml down

# Integration Testing Commands (MCP Document Indexing Pipeline)
INTEGRATION_COMPOSE := deployment/docker-compose.integration-tests.yml
INTEGRATION_TEST_RUNNER := docker compose -f $(INTEGRATION_COMPOSE) run --rm test-runner
INTEGRATION_LOGS_DIR := test-results/logs
INTEGRATION_REPORTS_DIR := test-results/reports

test-integration-setup: ## Setup integration test environment
	@echo "🔧 Setting up integration test environment..."
	@mkdir -p $(INTEGRATION_LOGS_DIR) $(INTEGRATION_REPORTS_DIR) test-results/coverage test-results/benchmarks
	@docker compose -f $(INTEGRATION_COMPOSE) down --volumes --remove-orphans 2>/dev/null || true
	@docker compose -f $(INTEGRATION_COMPOSE) build --no-cache
	@docker compose -f $(INTEGRATION_COMPOSE) up -d
	@echo "⏳ Waiting for services to be ready..."
	@sleep 30
	@$(MAKE) test-integration-health
	@echo "✅ Integration test environment ready"

test-integration-down: ## Stop integration test environment
	@echo "🛑 Stopping integration test environment..."
	@docker compose -f $(INTEGRATION_COMPOSE) down --volumes --remove-orphans

test-integration-clean: ## Clean integration test environment and artifacts
	@echo "🧹 Cleaning integration test environment..."
	@docker compose -f $(INTEGRATION_COMPOSE) down --volumes --remove-orphans --rmi local 2>/dev/null || true
	@rm -rf test-results/

test-integration-fast: ## Run essential integration tests (5-10 minutes)
	@echo "🚀 Running essential integration tests..."
	@$(INTEGRATION_TEST_RUNNER) pytest tests/integration/test_happy_path.py::test_complete_pipeline_single_document \
		tests/integration/test_error_handling.py::TestServiceFailureScenarios::test_intelligence_service_unavailable \
		tests/integration/test_performance.py::TestLatencyBenchmarks::test_document_creation_latency \
		tests/integration/test_data_consistency.py::TestCrossServiceDataConsistency::test_document_creation_consistency \
		-v --maxfail=3

test-integration-full: ## Run complete integration test suite (15-30 minutes)
	@echo "🧪 Running complete integration test suite..."
	@$(INTEGRATION_TEST_RUNNER) pytest tests/integration/ \
		-v --cov=tests/integration \
		--cov-report=html:test-results/coverage/html \
		--cov-report=xml:test-results/coverage/coverage.xml \
		--junitxml=$(INTEGRATION_REPORTS_DIR)/junit.xml \
		--html=$(INTEGRATION_REPORTS_DIR)/report.html --self-contained-html

test-integration-happy-path: ## Run happy path integration tests
	@echo "✅ Running happy path tests..."
	@$(INTEGRATION_TEST_RUNNER) pytest tests/integration/test_happy_path.py -v

test-integration-errors: ## Run error handling tests
	@echo "❌ Running error handling tests..."
	@$(INTEGRATION_TEST_RUNNER) pytest tests/integration/test_error_handling.py -v

test-integration-performance: ## Run performance benchmark tests
	@echo "⚡ Running performance tests..."
	@$(INTEGRATION_TEST_RUNNER) pytest tests/integration/test_performance.py -v \
		--benchmark-json=test-results/benchmarks/benchmark.json

test-integration-consistency: ## Run data consistency tests
	@echo "🔄 Running data consistency tests..."
	@$(INTEGRATION_TEST_RUNNER) pytest tests/integration/test_data_consistency.py -v

test-integration-ci: ## Run integration tests optimized for CI/CD
	@echo "🔄 Running CI/CD optimized integration tests..."
	@$(INTEGRATION_TEST_RUNNER) pytest tests/integration/ \
		--maxfail=5 --timeout=1800 -q \
		--cov=tests/integration \
		--cov-report=xml:test-results/coverage/coverage.xml \
		--junitxml=$(INTEGRATION_REPORTS_DIR)/junit.xml

test-integration-health: ## Check integration test services health
	@echo "🩺 Checking integration test services health..."
	@for i in 1 2 3 4 5; do \
		echo "Health check attempt $$i/5..."; \
		if curl -sf http://localhost:18181/health >/dev/null 2>&1 && \
		   curl -sf http://localhost:18051/health >/dev/null 2>&1 && \
		   curl -sf http://localhost:18053/health >/dev/null 2>&1; then \
			echo "✅ All integration test services healthy"; \
			break; \
		elif [ $$i -eq 5 ]; then \
			echo "❌ Integration test services not ready after 5 attempts"; \
			exit 1; \
		else \
			echo "⏳ Services not ready, waiting..."; \
			sleep 10; \
		fi; \
	done

test-integration-logs: ## Show integration test service logs
	@docker compose -f $(INTEGRATION_COMPOSE) logs --tail=100 -f

test-integration-report: ## Generate comprehensive integration test report
	@echo "📊 Generating integration test report..."
	@$(INTEGRATION_TEST_RUNNER) pytest tests/integration/ \
		-v --cov=tests/integration \
		--cov-report=html:test-results/coverage/html \
		--cov-report=term \
		--junitxml=$(INTEGRATION_REPORTS_DIR)/junit.xml \
		--html=$(INTEGRATION_REPORTS_DIR)/detailed-report.html --self-contained-html
	@echo "✅ Integration test report generated:"
	@echo "  📄 HTML Report: $(INTEGRATION_REPORTS_DIR)/detailed-report.html"
	@echo "  📊 Coverage:    test-results/coverage/html/index.html"

# Integration Testing Workflows
workflow-integration-dev: ## Development integration testing workflow
	@echo "🔧 Running development integration testing workflow..."
	@$(MAKE) test-integration-setup
	@$(MAKE) test-integration-fast
	@echo "✅ Development integration workflow completed"
	@echo "💡 Run 'make test-integration-down' when finished"

workflow-integration-ci: ## CI integration testing workflow
	@echo "🔄 Running CI integration testing workflow..."
	@$(MAKE) test-integration-setup
	@$(MAKE) test-integration-ci
	@$(MAKE) test-integration-down
	@echo "✅ CI integration workflow completed"

lint: ## Run code linting
	@echo "🔍 Running linters..."
	cd python && poetry run ruff check src/ tests/ && poetry run black --check src/ tests/ && poetry run mypy src/
	cd archon-ui-main && npm run lint

format: ## Format code
	@echo "✨ Formatting code..."
	cd python && poetry run black src/ tests/ && poetry run ruff --fix src/ tests/
	cd archon-ui-main && npm run format

# Security Commands
security-scan: ## Run security scans
	@echo "🛡️ Running security scans..."
	docker run --rm -v "$(PWD):/src" aquasec/trivy fs /src
	cd python && poetry run safety check && poetry run bandit -r src/
	cd archon-ui-main && npm audit

# Build Commands
build: ## Build all Docker images
	@echo "🏗️ Building Docker images..."
	docker build -f docker/Dockerfile.backend.prod -t archon-backend:latest .
	docker build -f docker/Dockerfile.frontend.prod -t archon-frontend:latest .

build-push: ## Build and push images to registry
	@echo "🏗️ Building and pushing images..."
	docker build -f docker/Dockerfile.backend.prod -t ghcr.io/$(GITHUB_REPOSITORY)-backend:$(IMAGE_TAG) .
	docker build -f docker/Dockerfile.frontend.prod -t ghcr.io/$(GITHUB_REPOSITORY)-frontend:$(IMAGE_TAG) .
	docker push ghcr.io/$(GITHUB_REPOSITORY)-backend:$(IMAGE_TAG)
	docker push ghcr.io/$(GITHUB_REPOSITORY)-frontend:$(IMAGE_TAG)

# Deployment Commands
deploy-staging: ## Deploy to staging environment
	@echo "🚀 Deploying to staging..."
	docker compose -f deployment/docker-compose.staging.yml down
	docker compose -f deployment/docker-compose.staging.yml up -d
	./scripts/wait-for-services.sh
	./scripts/smoke-tests.sh staging

deploy-production: ## Deploy to production environment
	@echo "🚀 Deploying to production..."
	@read -p "Are you sure you want to deploy to production? (y/N) " confirm && [ "$$confirm" = "y" ]
	docker compose -f deployment/docker-compose.prod.yml down
	docker compose -f deployment/docker-compose.prod.yml up -d
	./scripts/wait-for-services.sh
	./scripts/smoke-tests.sh production

# Kubernetes Commands
k8s-deploy-staging: ## Deploy to Kubernetes staging
	@echo "☸️ Deploying to Kubernetes staging..."
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/staging/ -n archon-staging

k8s-deploy-production: ## Deploy to Kubernetes production
	@echo "☸️ Deploying to Kubernetes production..."
	@read -p "Are you sure you want to deploy to production? (y/N) " confirm && [ "$$confirm" = "y" ]
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/production/ -n archon

k8s-status: ## Check Kubernetes deployment status
	@echo "📊 Kubernetes Status:"
	kubectl get pods,services,ingress -n archon

# Monitoring Commands
monitoring-start: ## Start monitoring stack
	@echo "📊 Starting monitoring stack..."
	docker compose -f monitoring/docker-compose.monitoring.yml up -d
	@echo "✅ Monitoring started!"
	@echo "   Grafana:    http://localhost:3000 (admin/admin123)"
	@echo "   Prometheus: http://localhost:9090"
	@echo "   Alertmanager: http://localhost:9093"

monitoring-stop: ## Stop monitoring stack
	@echo "🛑 Stopping monitoring stack..."
	docker compose -f monitoring/docker-compose.monitoring.yml down

monitoring-logs: ## Show monitoring logs
	docker compose -f monitoring/docker-compose.monitoring.yml logs -f

# Database Commands
db-backup: ## Backup databases
	@echo "💾 Creating database backup..."
	docker compose exec postgres pg_dump -U archon archon > backup_$(shell date +%Y%m%d_%H%M%S).sql
	docker compose exec redis redis-cli BGSAVE

db-restore: ## Restore database from backup (usage: make db-restore BACKUP_FILE=backup.sql)
	@echo "🔄 Restoring database from $(BACKUP_FILE)..."
	docker compose exec -T postgres psql -U archon archon < $(BACKUP_FILE)

db-shell: ## Open database shell
	docker compose exec postgres psql -U archon archon

redis-shell: ## Open Redis shell
	docker compose exec redis redis-cli

# Maintenance Commands
logs: ## Show application logs
	docker compose logs -f archon-server archon-frontend archon-mcp

health: ## Check service health
	@echo "🩺 Checking service health..."
	./scripts/wait-for-services.sh

smoke-test: ## Run smoke tests
	@echo "🧪 Running smoke tests..."
	./scripts/smoke-tests.sh

update: ## Update dependencies
	@echo "⬆️ Updating dependencies..."
	cd python && poetry update
	cd archon-ui-main && npm update
	docker compose pull

clean: ## Clean up Docker resources
	@echo "🧹 Cleaning up Docker resources..."
	docker system prune -f
	docker volume prune -f

clean-all: ## Clean up everything (WARNING: destroys all data)
	@echo "⚠️ This will destroy all data!"
	@read -p "Are you sure? (y/N) " confirm && [ "$$confirm" = "y" ]
	docker compose down -v
	docker system prune -a -f
	docker volume prune -f

# Environment Commands
env-production: ## Copy production environment template
	cp .env.production.example .env.production
	@echo "📝 Edit .env.production with your production values"

env-staging: ## Copy staging environment template
	cp .env.example .env.staging
	@echo "📝 Edit .env.staging with your staging values"

# CI/CD Commands
ci-test: ## Run CI/CD pipeline locally
	@echo "🔄 Running CI/CD pipeline locally..."
	act

ci-build: ## Build images like in CI/CD
	@echo "🏗️ Building images (CI/CD style)..."
	docker build --target runtime -f docker/Dockerfile.backend.prod -t archon-backend:ci .
	docker build --target runtime -f docker/Dockerfile.frontend.prod -t archon-frontend:ci .

# Documentation Commands
docs: ## Generate documentation
	@echo "📚 Generating documentation..."
	@echo "See DEPLOYMENT.md for complete deployment guide"

# Quick commands
up: dev-start ## Alias for dev-start
down: dev-stop ## Alias for dev-stop
restart: dev-restart ## Alias for dev-restart
