# Hybrid Scoring Team Onboarding Checklist

**Version**: 1.0.0
**Last Updated**: 2025-10-02
**Estimated Time**: 4-6 hours over 2 days

---

## Pre-Onboarding (Complete Before Day 1)

### Account Access
- [ ] GitHub repository access
- [ ] Slack channels: #hybrid-scoring, #hybrid-scoring-support
- [ ] Grafana dashboard access (monitoring)
- [ ] Prometheus access (metrics)
- [ ] PagerDuty (if on-call rotation)

### Development Environment
- [ ] Docker & Docker Compose installed
- [ ] Python 3.12+ installed
- [ ] Git configured
- [ ] IDE/editor setup (VS Code recommended)
- [ ] kubectl configured (for Kubernetes deployments)

### Repository Setup
```bash
# Clone repository
git clone https://github.com/your-org/archon.git
cd archon

# Checkout hybrid scoring branch
git checkout main

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

---

## Day 1: Foundation (2-3 hours)

### Morning: Documentation Review (1 hour)

- [ ] Read: `/docs/hybrid_scoring/README.md` (10 min)
- [ ] Read: `ADR_001_HYBRID_SCORING_APPROACH.md` (15 min)
- [ ] Read: `ADR_002_CACHING_STRATEGY.md` (15 min)
- [ ] Skim: `API_REFERENCE.md` (10 min)
- [ ] Skim: `INTEGRATION_GUIDE.md` (10 min)

**Checkpoint**: Can you explain:
- What is hybrid scoring and why we use it?
- What are the 70/30 weights?
- Why is caching critical?

### Afternoon: Environment Setup (1-2 hours)

#### Step 1: Deploy Prerequisites

```bash
# Start Phase 1 services (if not already running)
docker compose up -d memgraph qdrant

# Deploy langextract service
docker compose up -d langextract

# Deploy Redis (optional but recommended)
docker compose up -d redis

# Verify all services healthy
curl http://localhost:8156/health | jq .status  # Should be "healthy"
curl http://localhost:6333/collections | jq .   # Qdrant ready
redis-cli ping  # Should return "PONG"
```

- [ ] All services running
- [ ] Health checks passing
- [ ] No errors in logs

#### Step 2: Install Dependencies

```bash
cd services/intelligence

# Install Python dependencies
poetry install

# Install additional Phase 2 dependencies
poetry add httpx pybreaker redis tenacity

# Verify installation
poetry run python -c "import httpx, pybreaker, redis; print('✅ Dependencies OK')"
```

- [ ] Dependencies installed
- [ ] No import errors
- [ ] Poetry environment active

#### Step 3: Run First Test

```bash
# Run unit tests
poetry run pytest tests/unit/test_langextract_client.py -v

# Expected: All tests pass
```

- [ ] Tests running
- [ ] All tests passing
- [ ] Understand test structure

**Checkpoint**: Environment ready for development.

---

## Day 2: Hands-On Training (2-3 hours)

### Morning: Training Modules (2 hours)

- [ ] Complete: Module 1 - Hybrid Scoring Fundamentals (30 min)
- [ ] Complete: Module 2 - Architecture & Components (30 min)
- [ ] Complete: Module 3 - Hands-On Implementation (45 min)
  - Exercise 1: Basic Integration (15 min)
  - Exercise 2: Error Handling (15 min)
  - Exercise 3: Batch Processing (15 min)
- [ ] Complete: Module 4 - Operations & Troubleshooting (15 min)

**Checkpoint**: Can you:
- Implement basic hybrid scoring?
- Add error handling and fallback?
- Process multiple patterns with caching?

### Afternoon: Practice Project (1 hour)

#### Your First Integration

**Goal**: Integrate hybrid scoring into a simple pattern matching service

```python
# File: my_first_hybrid_integration.py

import asyncio
from typing import List, Dict

async def find_best_pattern(
    task_description: str,
    historical_patterns: List[Dict]
) -> Dict:
    """
    Find best matching pattern using hybrid scoring

    Args:
        task_description: User's task description
        historical_patterns: List of historical patterns with:
          - description: Pattern description
          - vector_score: Pre-computed vector similarity

    Returns:
        Best matching pattern with hybrid score
    """
    # TODO: Initialize hybrid scoring components
    # TODO: Implement pattern matching logic
    # TODO: Handle errors and fallback
    # TODO: Return best match with score

    pass  # Replace with your implementation


# Test your implementation
async def test_integration():
    task = "Implement OAuth2 authentication with JWT"

    patterns = [
        {"id": "p1", "description": "Build user authentication", "vector_score": 0.85},
        {"id": "p2", "description": "Create API security", "vector_score": 0.78},
        {"id": "p3", "description": "JWT token generation", "vector_score": 0.82}
    ]

    result = await find_best_pattern(task, patterns)

    print(f"Best match: {result['id']}")
    print(f"Hybrid score: {result['hybrid_score']:.2f}")
    print(f"Used patterns: {result.get('used_patterns', 'N/A')}")


if __name__ == "__main__":
    asyncio.run(test_integration())
```

**Tasks**:
- [ ] Implement `find_best_pattern` function
- [ ] Add proper error handling
- [ ] Test with langextract running
- [ ] Test with langextract stopped (fallback)
- [ ] Verify cache hit rate after multiple runs

**Review**: Submit code for review via PR or share in #hybrid-scoring

---

## Week 1: Production Deployment (Ongoing)

### Deployment Preparation

- [ ] Read: `OPERATIONAL_RUNBOOK.md` - Service Dependencies section
- [ ] Read: `INTEGRATION_GUIDE.md` - Deployment section
- [ ] Understand monitoring setup (Prometheus + Grafana)
- [ ] Review alert rules
- [ ] Join on-call rotation (if applicable)

### Staging Deployment

```bash
# Deploy to staging
kubectl apply -f k8s/staging/hybrid-scoring.yaml

# Verify deployment
kubectl get pods -n staging | grep hybrid
kubectl logs -f <pod-name> -n staging

# Run smoke tests
poetry run pytest tests/integration/test_hybrid_scoring_e2e.py --env=staging
```

- [ ] Staging deployment successful
- [ ] All health checks passing
- [ ] Smoke tests passing
- [ ] Monitoring dashboards showing data

### Production Deployment (Gradual Rollout)

**Week 1.1**: 10% Traffic
```bash
# Enable hybrid scoring for 10% of traffic
kubectl set env deployment/intelligence -n production USE_HYBRID_SCORING_PERCENT=10

# Monitor for 48 hours
# - Cache hit rate
# - Latency (p95, p99)
# - Error rate
# - Fallback rate
```

- [ ] 10% rollout successful
- [ ] Metrics within targets
- [ ] No production incidents
- [ ] Team review completed

**Week 1.2**: 50% Traffic (if 10% successful)
```bash
kubectl set env deployment/intelligence -n production USE_HYBRID_SCORING_PERCENT=50
```

- [ ] 50% rollout successful
- [ ] Continued monitoring
- [ ] No degradation observed

**Week 1.3**: 100% Traffic (if 50% successful)
```bash
kubectl set env deployment/intelligence -n production USE_HYBRID_SCORING_PERCENT=100
```

- [ ] 100% rollout successful
- [ ] Full production deployment complete
- [ ] Post-deployment review completed

---

## Ongoing: Mastery (Weeks 2-4)

### Week 2: Monitoring & Optimization

- [ ] Setup personal Grafana dashboards
- [ ] Configure Slack alerts
- [ ] Review weekly performance reports
- [ ] Tune cache configuration for your workload
- [ ] Optimize langextract timeout settings

### Week 3: Advanced Topics

- [ ] Read: `ADR_003_ADAPTIVE_WEIGHTS.md`
- [ ] Read: `ADR_004_CIRCUIT_BREAKER_PATTERN.md`
- [ ] Experiment with adaptive weights
- [ ] Implement A/B testing for weight optimization
- [ ] Contribute to documentation improvements

### Week 4: Team Contribution

- [ ] Answer questions in #hybrid-scoring-support
- [ ] Review team member PRs
- [ ] Participate in on-call rotation
- [ ] Present learning at team meeting
- [ ] Identify and propose improvements

---

## Certification

### Knowledge Assessment (80% to pass)

**Complete the post-onboarding quiz** (10 questions):

1. What is the hybrid scoring formula?
2. Why is the cache hit rate critical?
3. When does the circuit breaker open?
4. What is the fallback strategy?
5. What are the 5 pattern similarity components?
6. How does adaptive weight adjustment work?
7. What metrics should you monitor?
8. What's the recommended deployment strategy?
9. How do you debug low cache hit rate?
10. What's the purpose of the circuit breaker?

### Practical Assessment

**Submit working code that demonstrates**:
- [ ] Basic hybrid scoring integration
- [ ] Proper error handling with fallback
- [ ] Cache warming implementation
- [ ] Monitoring integration (metrics + logging)
- [ ] Unit tests with >80% coverage

### Code Review

- [ ] Code review from senior team member
- [ ] Feedback incorporated
- [ ] Final approval received

### Certification Badge

🏆 **Hybrid Scoring Certified Developer**

**Awarded**: [Date]
**Certificate ID**: [Auto-generated]
**Expires**: 1 year (re-certification required)

---

## Resources

### Documentation
- `/docs/hybrid_scoring/API_REFERENCE.md`
- `/docs/hybrid_scoring/INTEGRATION_GUIDE.md`
- `/docs/hybrid_scoring/OPERATIONAL_RUNBOOK.md`
- `/docs/hybrid_scoring/adr/` (all ADRs)

### Training Materials
- `/docs/hybrid_scoring/training/HYBRID_SCORING_TRAINING_GUIDE.md`
- `/docs/hybrid_scoring/training/FAQ.md`

### Support
- **Slack**: #hybrid-scoring-support
- **Email**: ml-team@company.com
- **On-call**: ml-oncall@company.com

### Office Hours
- **Tuesday 2-3 PM PT**: ML Team
- **Thursday 10-11 AM PT**: DevOps Team

---

## Onboarding Checklist Summary

- [ ] **Pre-Onboarding**: Access & environment setup
- [ ] **Day 1 AM**: Documentation review
- [ ] **Day 1 PM**: Environment setup
- [ ] **Day 2 AM**: Training modules
- [ ] **Day 2 PM**: Practice project
- [ ] **Week 1**: Production deployment (gradual)
- [ ] **Week 2**: Monitoring & optimization
- [ ] **Week 3**: Advanced topics
- [ ] **Week 4**: Team contribution
- [ ] **Certification**: Quiz + practical + code review

**Estimated Total Time**: 20-30 hours over 4 weeks

---

**Onboarding Checklist Version**: 1.0.0
**Last Updated**: 2025-10-02
**Maintained by**: ML Team

**Questions?** Contact your onboarding buddy or post in #hybrid-scoring-support
