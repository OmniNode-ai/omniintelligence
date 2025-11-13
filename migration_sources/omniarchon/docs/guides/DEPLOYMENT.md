# Archon CI/CD Pipeline and Deployment Guide

This guide covers the complete setup and deployment of the Archon microservices application using modern DevOps practices, containerization, and cloud-native technologies.

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Development Setup](#development-setup)
4. [CI/CD Pipeline](#cicd-pipeline)
5. [Docker Containerization](#docker-containerization)
6. [Production Deployment](#production-deployment)
7. [Kubernetes Deployment](#kubernetes-deployment)
8. [Monitoring & Observability](#monitoring--observability)
9. [Security Considerations](#security-considerations)
10. [Troubleshooting](#troubleshooting)

## 🏗️ Architecture Overview

Archon is built as a true microservices architecture with the following components:

```
┌─────────────────────────────────────────────────────────────┐
│                    Production Architecture                   │
├─────────────────┬─────────────────┬─────────────────────────┤
│   Load Balancer │   Application   │       Data Layer        │
│   (Nginx/Traefik) │     Layer       │                         │
├─────────────────┼─────────────────┼─────────────────────────┤
│ • SSL/TLS       │ • React Frontend│ • PostgreSQL            │
│ • Rate Limiting │ • FastAPI Backend│ • Redis Cache          │
│ • Compression   │ • MCP Server    │ • Qdrant Vector DB     │
│ • Health Checks │ • Intelligence  │ • Memgraph Graph DB    │
├─────────────────┼─────────────────┼─────────────────────────┤
│   Monitoring    │   CI/CD         │       Security          │
├─────────────────┼─────────────────┼─────────────────────────┤
│ • Prometheus    │ • GitHub Actions│ • Container Scanning   │
│ • Grafana       │ • Docker Build  │ • Dependency Checks    │
│ • Loki Logs     │ • Auto Deploy   │ • Security Headers     │
│ • Alertmanager  │ • Smoke Tests   │ • Non-root Users       │
└─────────────────┴─────────────────┴─────────────────────────┘
```

## 🔧 Prerequisites

### Development Environment
- **Docker** & Docker Compose (v20.10+)
- **Node.js** (v18+) and **npm**
- **Python** (3.12+) with **poetry** package manager
- **Git** for version control

### Production Environment
- **Kubernetes cluster** (1.25+) or **Docker Swarm**
- **Container registry** (GitHub Container Registry recommended)
- **Domain name** with DNS management
- **SSL certificate** (Let's Encrypt via cert-manager)

### Cloud Services (Optional)
- **Supabase** for managed PostgreSQL
- **OpenAI API** for AI features
- **Sentry** for error tracking
- **AWS S3** for backups

## 🚀 Development Setup

### 1. Clone and Configure

```bash
# Clone the repository
git clone https://github.com/your-org/archon.git
cd archon

# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

### 2. Start Development Environment

```bash
# Start core services
docker compose up -d

# Start with AI agents (optional)
docker compose --profile agents up -d

# Verify services
./scripts/wait-for-services.sh
```

### 3. Access Applications

- **Frontend**: http://localhost:3737
- **Backend API**: http://localhost:8181
- **MCP Server**: http://localhost:8051
- **Intelligence Service**: http://localhost:8053

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow

Our CI/CD pipeline includes comprehensive testing, security scanning, and deployment automation:

```mermaid
graph TD
    A[Push to Branch] --> B[Security Scan]
    B --> C[Code Quality]
    C --> D[Backend Tests]
    D --> E[Frontend Tests]
    E --> F[E2E Tests]
    F --> G[Build Images]
    G --> H{Branch?}
    H -->|develop| I[Deploy Staging]
    H -->|main| J[Deploy Production]
    I --> K[Smoke Tests]
    J --> K
    K --> L[Notify Success]
```

### Pipeline Stages

1. **Security Scanning**
   - Trivy vulnerability scanner
   - Python security analysis (Safety, Bandit)
   - JavaScript audit (npm audit)

2. **Code Quality**
   - Python: Ruff, Black, mypy
   - JavaScript: ESLint, TypeScript checks

3. **Testing**
   - Backend: pytest with coverage
   - Frontend: Vitest with coverage
   - E2E: Docker Compose integration tests

4. **Image Building**
   - Multi-architecture builds (amd64, arm64)
   - Multi-stage Dockerfiles for optimization
   - Registry push with proper tagging

5. **Deployment**
   - Staging: Automatic on `develop` branch
   - Production: Automatic on `main` branch or releases

### Setting Up CI/CD

1. **Configure GitHub Secrets**:
```bash
# Required secrets in GitHub repository settings:
GITHUB_TOKEN                 # Automatic
SUPABASE_URL                # Your Supabase URL
SUPABASE_SERVICE_KEY        # Supabase service key
OPENAI_API_KEY              # OpenAI API key
POSTGRES_PASSWORD           # Database password
SERVICE_AUTH_TOKEN          # Inter-service authentication
GRAFANA_ADMIN_PASSWORD      # Grafana admin password
```

2. **Configure Branch Protection**:
- Require status checks before merging
- Require pull request reviews
- Dismiss stale reviews on new commits

## 🐳 Docker Containerization

### Production-Optimized Dockerfiles

#### Backend (FastAPI)
```dockerfile
# Multi-stage build with security hardening
FROM python:3.12-slim AS builder
# ... build dependencies

FROM python:3.12-slim AS runtime
# Non-root user, read-only filesystem, minimal packages
# Gunicorn with multiple workers for production
```

#### Frontend (React + Nginx)
```dockerfile
# Build static assets
FROM node:18-alpine AS builder
# ... npm build

FROM nginx:alpine AS runtime
# Custom Nginx config with security headers
# Non-root user, optimized for serving static files
```

### Container Security Features

- **Non-root users** in all containers
- **Read-only root filesystems** where possible
- **Dropped capabilities** and privilege escalation prevention
- **Multi-stage builds** to reduce attack surface
- **Minimal base images** (Alpine Linux)
- **Health checks** for all services
- **Resource limits** and reservations

## 🌐 Production Deployment

### Docker Compose Production

```bash
# Copy production environment
cp .env.production.example .env.production
# Edit with your production values

# Deploy to production
docker compose -f docker-compose.prod.yml up -d

# Run smoke tests
./scripts/smoke-tests.sh production
```

### Key Production Features

- **Reverse proxy** with SSL termination (Traefik)
- **Horizontal scaling** with load balancing
- **Persistent volumes** for databases
- **Health checks** and automatic restarts
- **Resource limits** and monitoring
- **Backup automation**

### Environment Configuration

Production requires these key configurations:

```bash
# Domain and SSL
DOMAIN_NAME=archon.yourdomain.com
ACME_EMAIL=admin@yourdomain.com

# Database (use strong passwords)
POSTGRES_PASSWORD=secure_random_password
SERVICE_AUTH_TOKEN=secure_random_token

# External services
OPENAI_API_KEY=your_openai_key
SENTRY_DSN=your_sentry_dsn

# Enable production features
SSL_ENABLED=true
RATE_LIMIT_ENABLED=true
LOG_LEVEL=INFO
```

## ☸️ Kubernetes Deployment

### Prerequisites

```bash
# Install kubectl and helm
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install cert-manager for SSL
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.12.0/cert-manager.yaml

# Install ingress-nginx
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml
```

### Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Create secrets
kubectl create secret generic archon-secrets \
  --from-literal=supabase-url="$SUPABASE_URL" \
  --from-literal=supabase-service-key="$SUPABASE_SERVICE_KEY" \
  --from-literal=openai-api-key="$OPENAI_API_KEY" \
  --from-literal=postgres-password="$POSTGRES_PASSWORD" \
  --from-literal=service-auth-token="$SERVICE_AUTH_TOKEN" \
  -n archon

# Deploy databases
kubectl apply -f k8s/production/databases.yaml

# Deploy applications
kubectl apply -f k8s/production/backend-deployment.yaml
kubectl apply -f k8s/production/frontend-deployment.yaml

# Verify deployment
kubectl get pods -n archon
kubectl get services -n archon
```

### Kubernetes Features

- **StatefulSets** for databases
- **Horizontal Pod Autoscaling** based on CPU/memory
- **Rolling updates** with zero downtime
- **Ingress** with automatic SSL certificates
- **Network policies** for security
- **Resource quotas** and limits
- **Persistent volumes** for data
- **Service mesh** ready (Istio compatible)

## 📊 Monitoring & Observability

### Monitoring Stack

Deploy comprehensive monitoring with Prometheus, Grafana, and Loki:

```bash
# Start monitoring stack
docker compose -f monitoring/docker-compose.monitoring.yml up -d

# Access dashboards
# Grafana: http://localhost:3000 (admin/admin123)
# Prometheus: http://localhost:9090
# Alertmanager: http://localhost:9093
```

### Key Metrics Monitored

#### Application Metrics
- **Request rate** and response time
- **Error rate** and success rate
- **Active connections** and queue lengths
- **Custom business metrics**

#### Infrastructure Metrics
- **CPU, Memory, Disk** utilization
- **Network I/O** and latency
- **Container metrics** (Docker/K8s)
- **Database performance**

#### Alerts Configured
- **Service down** or unhealthy
- **High error rate** (>5% for 5 minutes)
- **High response time** (>2s for 5 minutes)
- **Resource exhaustion** (>90% usage)
- **Database connectivity** issues

### Log Management

- **Centralized logging** with Loki
- **Structured JSON** logs
- **Log correlation** with trace IDs
- **Log retention** policies
- **Real-time log** streaming

## 🔒 Security Considerations

### Container Security

- **Non-root users** in all containers
- **Read-only root filesystems**
- **Capability dropping**
- **Security scanning** in CI/CD
- **Regular base image** updates

### Network Security

- **TLS encryption** for all external communication
- **Internal service mesh** with mTLS
- **Network policies** in Kubernetes
- **Rate limiting** and DDoS protection
- **Web Application Firewall** (WAF)

### Application Security

- **Input validation** and sanitization
- **SQL injection** prevention
- **XSS protection** headers
- **CSRF protection**
- **Secure session** management
- **API authentication** and authorization

### Secrets Management

- **Environment variables** for configuration
- **Kubernetes secrets** for sensitive data
- **External secrets** operator (HashiCorp Vault)
- **Rotation policies** for credentials
- **Encryption at rest** and in transit

## 🔧 Troubleshooting

### Common Issues

#### Services Not Starting

```bash
# Check container logs
docker compose logs archon-server

# Check resource usage
docker stats

# Verify network connectivity
docker compose exec archon-server ping postgres

# Check environment variables
docker compose config
```

#### Database Connection Issues

```bash
# Check database status
docker compose exec postgres pg_isready -U archon

# Test connection from application
docker compose exec archon-server python -c "
import psycopg2
conn = psycopg2.connect('postgresql://archon:password@postgres:5432/archon')
print('Connected successfully')
"

# Check database logs
docker compose logs postgres
```

#### Performance Issues

```bash
# Monitor resource usage
docker stats

# Check application metrics
curl http://localhost:8181/metrics

# Analyze slow queries
docker compose exec postgres psql -U archon -c "
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;"
```

#### SSL/TLS Issues

```bash
# Check certificate validity
openssl s_client -connect yourdomain.com:443 -servername yourdomain.com

# Verify certificate chain
curl -vvI https://yourdomain.com

# Check Let's Encrypt rate limits
curl -s https://crt.sh/?q=yourdomain.com | jq
```

### Monitoring and Debugging

#### Application Health

```bash
# Run comprehensive health check
./scripts/smoke-tests.sh production

# Check individual service health
curl -f http://localhost:8181/health
curl -f http://localhost:8051/health
curl -f http://localhost:8053/health
```

#### Performance Monitoring

```bash
# Check response times
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8181/api/projects

# Monitor database performance
docker compose exec postgres psql -U archon -c "
SELECT schemaname,tablename,attname,n_distinct,correlation
FROM pg_stats
WHERE tablename='projects';"
```

#### Log Analysis

```bash
# Application logs
docker compose logs -f archon-server | jq

# Error patterns
docker compose logs archon-server | grep ERROR

# Performance logs
docker compose logs archon-server | grep "slow_query"
```

## 📚 Additional Resources

### Documentation Links
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Prometheus Monitoring](https://prometheus.io/docs/)
- [Nginx Configuration](https://nginx.org/en/docs/)

### Useful Commands

```bash
# Quick development start
make dev-start

# Run all tests
make test

# Deploy to staging
make deploy-staging

# Deploy to production
make deploy-production

# Backup databases
make backup

# Restore from backup
make restore BACKUP_FILE=backup.sql
```

### Support and Maintenance

#### Regular Maintenance Tasks
1. **Update dependencies** monthly
2. **Security patches** weekly
3. **Database maintenance** weekly
4. **Log rotation** daily
5. **Backup verification** weekly
6. **Performance review** monthly

#### Scaling Considerations
- **Horizontal scaling** for stateless services
- **Vertical scaling** for databases
- **CDN** for static assets
- **Caching** strategies
- **Database sharding** for large datasets

---

## 🎯 Quick Start Checklist

- [ ] Clone repository and configure environment
- [ ] Set up development environment with Docker
- [ ] Configure GitHub repository with secrets
- [ ] Run CI/CD pipeline tests
- [ ] Deploy to staging environment
- [ ] Run smoke tests
- [ ] Set up monitoring dashboards
- [ ] Configure SSL certificates
- [ ] Deploy to production
- [ ] Set up alerting rules
- [ ] Document operational procedures

For immediate support, check our [troubleshooting guide](#troubleshooting) or contact the DevOps team.

---

**Built with ❤️ for modern DevOps practices and cloud-native deployment**
