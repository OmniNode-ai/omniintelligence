# Alert Runbook - Incident Response Guide

**Version**: 1.0.0
**Last Updated**: 2025-10-20
**Status**: Production Ready

## Table of Contents

1. [Overview](#overview)
2. [Alert Categories](#alert-categories)
3. [Common Alerts](#common-alerts)
4. [Service-Specific Runbooks](#service-specific-runbooks)
5. [Troubleshooting Steps](#troubleshooting-steps)
6. [Resolution Procedures](#resolution-procedures)
7. [Escalation Paths](#escalation-paths)
8. [Post-Mortem Template](#post-mortem-template)
9. [Diagnostic Commands](#diagnostic-commands)
10. [Real Alert Examples](#real-alert-examples)

---

## Overview

This runbook provides step-by-step guidance for responding to Archon platform alerts. All alerts are monitored via container health checks and sent to Slack with detailed context.

**Alert Sources**:
- Container health check failures (every 60s)
- Error log pattern detection (last 5 minutes)
- Performance degradation
- Service connection failures

**Notification Channels**:
- 🔴 **CRITICAL**: Slack + Logs + Email (optional)
- 🟡 **WARNING**: Slack + Logs
- 🟢 **INFO**: Slack + Logs

**Response Times**:
- **CRITICAL**: Immediate response (<5 minutes)
- **WARNING**: Response within 30 minutes
- **INFO**: Review within 4 hours

---

## Alert Categories

### 1. Container Health Alerts
- **container_unhealthy**: Health check failed
- **container_recovered**: Service recovered after failure
- **Cooldown**: 5 minutes between duplicates

### 2. Error Detection Alerts
- **container_errors_critical**: CRITICAL/FATAL errors detected
- **container_errors_warning**: ERROR/Exception patterns detected
- **Cooldown**: 15 minutes between duplicates

### 3. Performance Alerts
- **performance_degradation**: Response time >3x baseline
- **cache_miss_rate_high**: Cache hit rate <70%
- **resource_exhaustion**: Memory/CPU >90%

### 4. Dependency Alerts
- **database_connection_failed**: Qdrant/Memgraph/Supabase unavailable
- **service_unavailable**: Backend service not responding
- **kafka_consumer_lag**: Event processing delayed

---

## Common Alerts

### 🔴 CRITICAL: Container Unhealthy

**Alert Format**:
```
🚨 Pipeline Alert: Container Unhealthy: archon-intelligence

Severity: CRITICAL
Metric: container_health
Current Value: 0.0
Threshold: 1.0

Description:
Container archon-intelligence failed health check

Recent Logs:
```
neo4j.exceptions.ServiceUnavailable: Cannot resolve address memgraph:7687
```
```

**Immediate Actions**:
1. Check container status: `docker ps -a | grep archon-intelligence`
2. Check container logs: `docker logs archon-intelligence --tail 100`
3. Check health endpoint: `curl http://localhost:8053/health`
4. Verify dependencies are running
5. Restart if necessary

**Common Causes**:
- Dependency service (Memgraph, Qdrant, Supabase) unavailable
- Database connection pool exhausted
- Out of memory (OOM)
- Configuration error
- Network issues between containers

**Resolution Time**: 5-15 minutes

---

### 🟢 INFO: Container Recovered

**Alert Format**:
```
✅ Pipeline Alert: Container Recovered: archon-intelligence

Severity: INFO
Metric: container_health
Current Value: 1.0
Threshold: 0.0

Description:
Container archon-intelligence is now healthy
```

**Actions**:
1. Verify service is stable: `curl http://localhost:8053/health`
2. Check logs for root cause: `docker logs archon-intelligence --tail 200`
3. Monitor for 15 minutes to ensure no relapse
4. Update incident ticket with resolution details

**Follow-Up**:
- Document root cause in post-mortem
- Review metrics for trends
- Consider preventive measures

---

### 🔴 CRITICAL: Container Critical Errors

**Alert Format**:
```
🚨 Pipeline Alert: Critical Errors: archon-intelligence

Severity: CRITICAL
Metric: container_errors
Current Value: 3.0
Threshold: 0.0

Description:
Container archon-intelligence has critical errors

**Detected Errors (3):**
```
• neo4j.exceptions.ServiceUnavailable: Cannot resolve address memgraph:7687
• CRITICAL: Database connection pool exhausted
• FATAL: Unable to initialize service
```
```

**Immediate Actions**:
1. Review full error logs: `docker logs archon-intelligence --tail 500`
2. Check dependency health: Memgraph, Qdrant, Supabase
3. Verify network connectivity: `docker network inspect app-network`
4. Check resource usage: `docker stats archon-intelligence --no-stream`
5. Restart service if connection issues persist

**Common Error Patterns**:
- `ServiceUnavailable`: Dependency service down
- `Connection refused`: Port not listening
- `Cannot resolve address`: DNS/network issue
- `Connection pool exhausted`: Too many connections
- `TimeoutError`: Slow queries or network latency

---

### 🟡 WARNING: Container Errors Detected

**Alert Format**:
```
⚠️ Pipeline Alert: Errors Detected: archon-search

Severity: WARNING
Metric: container_errors
Current Value: 2.0
Threshold: 0.0

Description:
Container archon-search has warnings/errors

**Detected Errors (2):**
```
• ERROR: Request timeout after 5 seconds
• Exception in query execution: Invalid syntax
```
```

**Immediate Actions**:
1. Review error context: `docker logs archon-search --tail 200`
2. Check if errors are transient or persistent
3. Verify query syntax and parameters
4. Monitor for escalation to CRITICAL

**Common Causes**:
- Slow queries (timeout)
- Invalid request parameters
- Temporary network glitches
- Resource contention

**Resolution Time**: 15-30 minutes

---

## Service-Specific Runbooks

### archon-server (Port 8181)

**Purpose**: FastAPI + Socket.IO + Container health monitoring

**Health Check**:
```bash
curl http://localhost:8181/health
# Expected: {"status": "healthy", ...}
```

**Common Issues**:

#### Issue 1: Container Health Monitoring Not Starting
**Symptoms**: No health monitoring startup message in logs
**Diagnosis**:
```bash
docker logs archon-server | grep "Container health monitoring"
# Expected: "🏥 Container health monitoring started"
```
**Resolution**:
```bash
# Check Docker socket mount
docker inspect archon-server | grep -A 3 "Mounts"
# Should include: /var/run/docker.sock:/var/run/docker.sock

# Verify Slack webhook configured
docker exec archon-server env | grep SLACK_WEBHOOK_URL

# Restart service
docker restart archon-server
```

#### Issue 2: WebSocket Connection Failures
**Symptoms**: Clients can't connect to Socket.IO
**Diagnosis**:
```bash
curl http://localhost:8181/socket.io/
# Expected: 0{"sid":"...","upgrades":[],"pingInterval":25000,"pingTimeout":20000}
```
**Resolution**:
```bash
# Check port binding
docker ps | grep archon-server
# Should show: 0.0.0.0:8181->8181/tcp

# Check service logs
docker logs archon-server --tail 100

# Verify CORS configuration if needed
```

---

### archon-mcp (Port 8151)

**Purpose**: MCP server (unified gateway: 168+ operations)

**Health Check**:
```bash
curl http://localhost:8151/health
# Expected: {"status": "healthy", "services": {...}}
```

**Common Issues**:

#### Issue 1: Intelligence Service Unavailable
**Symptoms**: MCP operations fail with 503 Service Unavailable
**Diagnosis**:
```bash
# Check intelligence service
curl http://localhost:8053/health

# Check MCP service connectivity
docker logs archon-mcp --tail 100 | grep "intelligence"
```
**Resolution**:
```bash
# Restart intelligence service first
docker restart archon-intelligence

# Wait for health check to pass
while ! curl -f http://localhost:8053/health; do sleep 2; done

# Restart MCP service
docker restart archon-mcp
```

#### Issue 2: Cache Connection Failed
**Symptoms**: Operations slow, cache errors in logs
**Diagnosis**:
```bash
# Check Valkey health
docker exec archon-valkey valkey-cli ping
# Expected: PONG

# Check connection from MCP
docker logs archon-mcp | grep -i "cache\|valkey"
```
**Resolution**:
```bash
# Restart Valkey
docker restart archon-valkey

# Clear cache if corrupted
docker exec archon-valkey valkey-cli FLUSHDB

# Restart MCP
docker restart archon-mcp
```

---

### archon-intelligence (Port 8053)

**Purpose**: Core intelligence (quality, performance, patterns, traceability)

**Health Check**:
```bash
curl -m 5 http://localhost:8053/health
# Expected: {"status": "healthy", "subsystems": {...}}
```

**Common Issues**:

#### Issue 1: Memgraph Connection Failure
**Symptoms**: ServiceUnavailable: Cannot resolve address memgraph:7687
**Diagnosis**:
```bash
# Check Memgraph health
docker exec archon-memgraph bash -c "exec 3<>/dev/tcp/localhost/7444"
# No error = healthy

# Check network connectivity
docker exec archon-intelligence ping -c 3 memgraph
```
**Resolution**:
```bash
# Restart Memgraph
docker restart memgraph

# Wait for health
sleep 30

# Restart intelligence service
docker restart archon-intelligence

# Verify connection restored
curl http://localhost:8053/health
```

#### Issue 2: Pattern Learning Performance Degradation
**Symptoms**: Pattern operations >3s (baseline ~500ms)
**Diagnosis**:
```bash
# Check pattern learning metrics
curl http://localhost:8053/api/pattern-learning/metrics

# Check cache stats
curl http://localhost:8053/api/pattern-learning/cache/stats
```
**Resolution**:
```bash
# Clear pattern learning cache
curl -X POST http://localhost:8053/api/pattern-learning/cache/clear

# Restart service if needed
docker restart archon-intelligence

# Monitor performance
watch -n 5 'curl -s http://localhost:8053/api/pattern-learning/metrics'
```

---

### archon-bridge (Port 8054)

**Purpose**: PostgreSQL-Memgraph synchronization + Bridge intelligence

**Health Check**:
```bash
curl -f http://localhost:8054/health
# Expected: {"status": "healthy", ...}
```

**Common Issues**:

#### Issue 1: Supabase Connection Timeout
**Symptoms**: Connection timeouts, slow metadata operations
**Diagnosis**:
```bash
# Check Supabase connectivity
docker exec archon-bridge curl -f "${SUPABASE_URL}/rest/v1/"

# Check service logs
docker logs archon-bridge --tail 100 | grep -i "supabase\|timeout"
```
**Resolution**:
```bash
# Verify environment variables
docker exec archon-bridge env | grep SUPABASE

# Check network from container
docker exec archon-bridge ping -c 3 supabase.co

# Restart bridge service
docker restart archon-bridge
```

---

### archon-search (Port 8055)

**Purpose**: RAG search + Vector search (Qdrant) + Knowledge graph queries

**Health Check**:
```bash
curl -m 5 http://localhost:8055/health
# Expected: {"status": "healthy", "dependencies": {...}}
```

**Common Issues**:

#### Issue 1: Qdrant Vector Search Failed
**Symptoms**: Vector search operations timeout or fail
**Diagnosis**:
```bash
# Check Qdrant health
curl http://localhost:6333/readyz
# Expected: {"status":"ok"}

# Check collection exists
curl http://localhost:6333/collections/archon_vectors
```
**Resolution**:
```bash
# Restart Qdrant
docker restart qdrant

# Wait for startup (60s)
sleep 60

# Restart search service
docker restart archon-search

# Verify collections restored
curl http://localhost:6333/collections
```

#### Issue 2: Cache Hit Rate <70%
**Symptoms**: Search queries slow, low cache hit rate
**Diagnosis**:
```bash
# Check Valkey stats
docker exec archon-valkey valkey-cli INFO stats | grep -E "keyspace_hits|keyspace_misses"

# Check cache keys
docker exec archon-valkey valkey-cli KEYS "research:*" | wc -l
```
**Resolution**:
```bash
# Warm up cache with common queries
# (run representative queries)

# Increase cache TTL if needed (via environment)
# ENABLE_CACHE=true in .env

# Monitor hit rate improvement
docker exec archon-valkey valkey-cli INFO stats
```

---

### archon-langextract (Port 8156)

**Purpose**: ML extraction, classification, semantic analysis

**Health Check**:
```bash
curl -m 5 http://localhost:8156/health
# Expected: {"status": "healthy", ...}
```

**Common Issues**:

#### Issue 1: Extraction Timeout
**Symptoms**: Extraction operations timeout (default: 300s)
**Diagnosis**:
```bash
# Check extraction queue
docker logs archon-langextract --tail 100 | grep -i "timeout\|extraction"

# Check resource usage
docker stats archon-langextract --no-stream
```
**Resolution**:
```bash
# Increase timeout via environment
# EXTRACTION_TIMEOUT_SECONDS=600

# Restart service
docker restart archon-langextract

# Reduce concurrent extractions if resource constrained
# MAX_CONCURRENT_EXTRACTIONS=3
```

---

### archon-valkey (Port 6379)

**Purpose**: Distributed cache (512MB LRU eviction)

**Health Check**:
```bash
docker exec archon-valkey valkey-cli ping
# Expected: PONG
```

**Common Issues**:

#### Issue 1: High Memory Usage (>512MB)
**Symptoms**: Evictions increasing, performance degradation
**Diagnosis**:
```bash
# Check memory usage
docker exec archon-valkey valkey-cli INFO memory | grep -E "used_memory_human|maxmemory_human|evicted_keys"

# Check eviction policy
docker exec archon-valkey valkey-cli CONFIG GET maxmemory-policy
# Expected: allkeys-lru
```
**Resolution**:
```bash
# Clear cache if needed
docker exec archon-valkey valkey-cli FLUSHDB

# Increase memory limit (requires restart)
# Update docker-compose.yml: VALKEY_MAXMEMORY=1024mb

# Restart with new config
docker restart archon-valkey
```

#### Issue 2: Connection Refused
**Symptoms**: Services can't connect to Valkey
**Diagnosis**:
```bash
# Check Valkey is running
docker ps | grep archon-valkey

# Check port binding
docker port archon-valkey 6379
# Expected: 0.0.0.0:6379

# Test connection
docker exec archon-valkey valkey-cli -a archon_cache_2025 ping
```
**Resolution**:
```bash
# Restart Valkey
docker restart archon-valkey

# Wait for health check
sleep 10

# Verify password configured
docker exec archon-valkey env | grep VALKEY_PASSWORD
```

---

### qdrant (Ports 6333, 6334)

**Purpose**: Vector database (high-performance vector search)

**Health Check**:
```bash
curl http://localhost:6333/readyz
# Expected: {"status":"ok"}
```

**Common Issues**:

#### Issue 1: Collection Not Found
**Symptoms**: Vector search fails with 404 Collection not found
**Diagnosis**:
```bash
# List collections
curl http://localhost:6333/collections

# Check specific collection
curl http://localhost:6333/collections/archon_vectors
```
**Resolution**:
```bash
# Re-create collection via search service
# (search service auto-creates on startup)

# Restart search service to trigger initialization
docker restart archon-search

# Wait for initialization
sleep 30

# Verify collection exists
curl http://localhost:6333/collections/archon_vectors
```

#### Issue 2: Memory Limit Exceeded
**Symptoms**: OOM errors, container restarts
**Diagnosis**:
```bash
# Check memory usage
docker stats qdrant --no-stream

# Check container events
docker events --filter container=qdrant --since 1h
```
**Resolution**:
```bash
# Increase memory limit in docker-compose.yml
# limits.memory: 4G (from 2G)

# Optimize Qdrant config
# QDRANT__STORAGE__ON_DISK_PAYLOAD=true (already set)

# Restart with new limits
docker compose up -d qdrant
```

---

### memgraph (Ports 7687, 7444)

**Purpose**: Knowledge graph database (Cypher queries)

**Health Check**:
```bash
# HTTP endpoint
docker exec archon-memgraph bash -c "exec 3<>/dev/tcp/localhost/7444 && echo 'OK'"
# Expected: OK
```

**Common Issues**:

#### Issue 1: Bolt Connection Failed
**Symptoms**: neo4j.exceptions.ServiceUnavailable
**Diagnosis**:
```bash
# Check Bolt port
docker exec archon-memgraph netstat -tuln | grep 7687

# Check logs
docker logs memgraph --tail 100
```
**Resolution**:
```bash
# Restart Memgraph
docker restart memgraph

# Wait for startup
sleep 30

# Test Bolt connection
docker exec archon-intelligence python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://memgraph:7687')
driver.verify_connectivity()
print('Connection OK')
"
```

#### Issue 2: Memory Limit Exceeded
**Symptoms**: Queries fail, container restarts
**Diagnosis**:
```bash
# Check memory config
docker exec memgraph bash -c "env | grep MEMGRAPH_MEMORY_LIMIT"
# Expected: 1024

# Check actual usage
docker stats memgraph --no-stream
```
**Resolution**:
```bash
# Increase memory limit in docker-compose.yml
# MEMGRAPH_MEMORY_LIMIT=2048

# Restart with new config
docker restart memgraph
```

---

## Troubleshooting Steps

### Step 1: Identify the Problem

**Questions to Answer**:
- Which service is affected?
- What is the error message?
- When did it start?
- Is it affecting all operations or specific ones?
- Are there related alerts?

**Commands**:
```bash
# Check all container statuses
docker ps -a

# Check unhealthy containers
docker ps --filter health=unhealthy

# Check recent restarts
docker ps -a --filter status=exited --filter since=1h

# Check logs for errors
for service in archon-server archon-mcp archon-intelligence archon-bridge archon-search; do
  echo "=== $service ==="
  docker logs $service --tail 20 | grep -i "error\|critical\|fatal"
done
```

---

### Step 2: Check Dependencies

**Dependency Map**:
- archon-server → Memgraph, Intelligence Service
- archon-mcp → Server, Intelligence, Valkey, Search
- archon-intelligence → Memgraph, Bridge
- archon-bridge → Supabase, Memgraph
- archon-search → Qdrant, Memgraph, Intelligence, Bridge

**Commands**:
```bash
# Check database health
curl http://localhost:6333/readyz  # Qdrant
docker exec archon-memgraph bash -c "exec 3<>/dev/tcp/localhost/7444"  # Memgraph
docker exec archon-valkey valkey-cli ping  # Valkey

# Check service health
curl http://localhost:8181/health  # Server
curl http://localhost:8151/health  # MCP
curl http://localhost:8053/health  # Intelligence
curl http://localhost:8054/health  # Bridge
curl http://localhost:8055/health  # Search
curl http://localhost:8156/health  # LangExtract

# Check network connectivity
docker network inspect app-network
```

---

### Step 3: Check Resource Usage

**Commands**:
```bash
# Check all container stats
docker stats --no-stream

# Check disk usage
docker system df

# Check volume usage
docker volume ls
du -sh /var/lib/docker/volumes/*

# Check for OOM kills
dmesg -T | grep -i "killed process"

# Check host resources
free -h  # Memory
df -h    # Disk
top      # CPU
```

---

### Step 4: Review Logs

**Commands**:
```bash
# Get logs for specific timeframe
docker logs archon-intelligence --since 30m

# Follow logs in real-time
docker logs -f archon-intelligence

# Filter for errors
docker logs archon-intelligence --tail 500 | grep -i "error\|critical\|fatal\|exception"

# Check for specific patterns
docker logs archon-intelligence | grep "ServiceUnavailable\|ConnectionError\|TimeoutError"

# Export logs for analysis
docker logs archon-intelligence > /tmp/archon-intelligence-$(date +%Y%m%d-%H%M%S).log
```

---

### Step 5: Network Diagnostics

**Commands**:
```bash
# Check container networking
docker network inspect app-network

# Test connectivity between containers
docker exec archon-intelligence ping -c 3 memgraph
docker exec archon-search curl -f http://archon-intelligence:8053/health

# Check port bindings
docker port archon-mcp
docker port archon-intelligence

# Check DNS resolution
docker exec archon-intelligence nslookup memgraph
docker exec archon-search nslookup qdrant
```

---

## Resolution Procedures

### Procedure 1: Restart Single Service

**When to Use**: Service unhealthy, dependencies healthy, isolated issue

**Steps**:
```bash
# 1. Check service logs first
docker logs archon-intelligence --tail 100

# 2. Graceful restart
docker restart archon-intelligence

# 3. Monitor startup (wait 30-60s)
watch -n 2 'docker ps | grep archon-intelligence'

# 4. Verify health
curl http://localhost:8053/health

# 5. Check logs for errors
docker logs archon-intelligence --tail 50
```

**Verification**:
- Health check passes
- No errors in startup logs
- Dependent services can connect
- Alert cleared in Slack

---

### Procedure 2: Restart Service with Dependencies

**When to Use**: Multiple services affected, dependency chain broken

**Steps**:
```bash
# 1. Identify dependency order (bottom-up)
# Databases → Bridge/Intelligence → Search/MCP → Server

# 2. Restart databases first
docker restart memgraph qdrant archon-valkey

# 3. Wait for health (60s)
sleep 60

# 4. Restart core services
docker restart archon-intelligence archon-bridge

# 5. Wait for health (30s)
sleep 30

# 6. Restart dependent services
docker restart archon-search archon-mcp

# 7. Wait for health (30s)
sleep 30

# 8. Restart server last
docker restart archon-server

# 9. Verify all healthy
docker ps --filter health=unhealthy
# Expected: empty

# 10. Check health endpoints
for port in 8181 8151 8053 8054 8055 8156; do
  echo "=== Port $port ==="
  curl -f http://localhost:$port/health || echo "FAILED"
done
```

---

### Procedure 3: Full Stack Restart

**When to Use**: Multiple persistent failures, configuration changes, last resort

**Steps**:
```bash
# 1. Stop all services
docker compose down

# 2. Check for stuck containers
docker ps -a | grep archon

# 3. Force remove if needed
docker rm -f $(docker ps -aq --filter name=archon)

# 4. Clean up networks (optional)
docker network prune -f

# 5. Start services with fresh state
docker compose up -d

# 6. Monitor startup logs
docker compose logs -f

# 7. Wait for all health checks (2-3 minutes)
watch -n 5 'docker ps --format "table {{.Names}}\t{{.Status}}"'

# 8. Verify all services healthy
docker ps --filter health=unhealthy
# Expected: empty

# 9. Run smoke tests
curl http://localhost:8181/health
curl http://localhost:8151/health
curl http://localhost:8053/health
```

---

### Procedure 4: Clear Cache and Restart

**When to Use**: Cache corruption, stale data, performance issues

**Steps**:
```bash
# 1. Clear Valkey cache
docker exec archon-valkey valkey-cli -a archon_cache_2025 FLUSHDB

# 2. Clear pattern learning cache
curl -X POST http://localhost:8053/api/pattern-learning/cache/clear

# 3. Restart services that use cache
docker restart archon-mcp archon-search

# 4. Verify cache empty
docker exec archon-valkey valkey-cli -a archon_cache_2025 DBSIZE
# Expected: (integer) 0

# 5. Warm up cache with common queries
# (run representative queries to rebuild cache)

# 6. Monitor cache hit rate
docker exec archon-valkey valkey-cli -a archon_cache_2025 INFO stats | grep keyspace
```

---

### Procedure 5: Database Recovery

**When to Use**: Database corruption, data inconsistency, restore needed

#### Qdrant Vector DB Recovery:
```bash
# 1. Stop search service
docker stop archon-search

# 2. Backup current data (optional)
docker exec qdrant tar -czf /tmp/qdrant-backup-$(date +%Y%m%d).tar.gz /qdrant/storage

# 3. Restart Qdrant (clears memory)
docker restart qdrant

# 4. Wait for startup
sleep 60

# 5. Verify collections
curl http://localhost:6333/collections

# 6. If collections missing, restart search service (auto-creates)
docker start archon-search

# 7. Verify health
curl http://localhost:6333/readyz
curl http://localhost:8055/health
```

#### Memgraph Knowledge Graph Recovery:
```bash
# 1. Stop dependent services
docker stop archon-intelligence archon-bridge archon-search

# 2. Restart Memgraph
docker restart memgraph

# 3. Wait for startup
sleep 30

# 4. Verify Bolt connection
docker exec memgraph bash -c "exec 3<>/dev/tcp/localhost/7687"

# 5. Restart dependent services
docker start archon-intelligence archon-bridge archon-search

# 6. Verify health
curl http://localhost:8053/health
```

---

## Escalation Paths

### Level 1: On-Call Engineer (Initial Response)

**Responsibilities**:
- Acknowledge alert within 5 minutes
- Execute initial troubleshooting steps
- Restart services if needed
- Document findings in incident ticket

**Authority**:
- Restart individual services
- Clear caches
- Gather diagnostic information

**Escalate to Level 2 if**:
- Issue persists after service restart
- Multiple services affected
- Data corruption suspected
- Security incident suspected
- Resolution time >30 minutes

**Contact**: Slack `@oncall-engineer`

---

### Level 2: Senior SRE (Complex Issues)

**Responsibilities**:
- Full stack troubleshooting
- Database recovery
- Configuration changes
- Performance optimization
- Root cause analysis

**Authority**:
- Full stack restart
- Database restoration
- Configuration changes
- Emergency maintenance window

**Escalate to Level 3 if**:
- Data loss occurred
- Security breach confirmed
- Architecture changes needed
- External vendor involvement required
- Resolution time >2 hours

**Contact**: Slack `@sre-team`, Phone: On-call rotation

---

### Level 3: Engineering Leadership (Critical Incidents)

**Responsibilities**:
- Incident command
- Stakeholder communication
- Architecture decisions
- Vendor escalation
- Post-incident review

**Authority**:
- Emergency deployments
- Architecture changes
- Budget approval for resources
- External escalations

**Trigger Conditions**:
- Service outage >2 hours
- Data breach/security incident
- Financial impact >$10k
- Customer SLA breach
- Media attention

**Contact**: Slack `@engineering-leadership`, Email: eng-leaders@archon.dev

---

### Escalation Matrix

| Severity | Initial Response | SRE Escalation | Leadership Escalation |
|----------|------------------|----------------|-----------------------|
| **CRITICAL** | <5 min | 30 min | 2 hours |
| **WARNING** | <30 min | 4 hours | 24 hours |
| **INFO** | <4 hours | N/A | N/A |

---

### External Escalations

**Vendor Support**:
- **Supabase**: support@supabase.com, Dashboard support chat
- **Docker**: Docker Enterprise support (if applicable)
- **Cloud Provider**: AWS/GCP support (if applicable)

**When to Escalate Externally**:
- Supabase service degradation confirmed
- Docker daemon issues
- Cloud infrastructure problems
- Third-party API outages

---

## Post-Mortem Template

### Incident Report: [INCIDENT-ID]

**Date**: YYYY-MM-DD
**Duration**: [HH:MM] to [HH:MM] (X hours Y minutes)
**Severity**: CRITICAL / WARNING / INFO
**Affected Services**: [List services]
**Impact**: [User impact description]
**Responders**: [Names/Roles]

---

### Executive Summary

[2-3 sentence summary of what happened, impact, and resolution]

---

### Timeline

| Time (UTC) | Event |
|------------|-------|
| HH:MM | Alert triggered: Container archon-intelligence unhealthy |
| HH:MM | On-call engineer acknowledged alert |
| HH:MM | Identified root cause: Memgraph connection pool exhausted |
| HH:MM | Restarted Memgraph database |
| HH:MM | Service recovered, health checks passing |
| HH:MM | Monitoring confirmed stable, incident closed |

---

### Root Cause Analysis

**Immediate Cause**:
[What directly caused the failure?]

**Contributing Factors**:
1. [Factor 1]
2. [Factor 2]
3. [Factor 3]

**Why it wasn't caught earlier**:
[What detection gaps existed?]

---

### Detection and Response

**Detection Method**: Container health monitoring, Slack alert
**Detection Time**: HH:MM (X minutes after failure)
**Response Time**: HH:MM (Y minutes to acknowledge)
**Resolution Time**: HH:MM (Z minutes to resolve)

**Response Quality**:
- ✅ Alert received and acknowledged promptly
- ✅ Runbook followed correctly
- ⚠️ Initial diagnosis incorrect (tried cache clear first)
- ✅ Root cause identified within 20 minutes

---

### Impact Assessment

**Services Affected**:
- archon-intelligence (completely down)
- archon-search (degraded, 50% request failures)
- archon-mcp (degraded, intelligence operations failing)

**User Impact**:
- X users affected
- Y failed requests
- Z% error rate
- No data loss

**Financial Impact**: $X (estimated)

---

### Resolution Steps

1. Acknowledged alert in Slack
2. Checked container logs: `docker logs archon-intelligence`
3. Identified Memgraph connection errors
4. Verified Memgraph health check failing
5. Restarted Memgraph: `docker restart memgraph`
6. Waited 30s for Memgraph startup
7. Restarted intelligence service: `docker restart archon-intelligence`
8. Verified health: `curl http://localhost:8053/health`
9. Monitored for 15 minutes, confirmed stable
10. Updated incident ticket, closed alert

**What Worked Well**:
- Alert detected issue immediately
- Logs provided clear error messages
- Runbook procedures followed successfully
- Recovery was straightforward

**What Didn't Work**:
- Initial response tried wrong resolution (cache clear)
- No automated remediation for this scenario

---

### Preventive Measures

**Immediate Actions** (Within 24 hours):
- [ ] Increase Memgraph connection pool size
- [ ] Add connection pool monitoring alert
- [ ] Document Memgraph tuning best practices

**Short-term Actions** (Within 1 week):
- [ ] Implement connection pool auto-scaling
- [ ] Add Memgraph query performance monitoring
- [ ] Create automated remediation script for this scenario
- [ ] Update runbook with new findings

**Long-term Actions** (Within 1 month):
- [ ] Evaluate Memgraph clustering for HA
- [ ] Implement circuit breakers for database connections
- [ ] Add chaos engineering tests for connection failures
- [ ] Develop automated recovery procedures

---

### Lessons Learned

**Technical**:
1. Memgraph connection pool defaults insufficient for production load
2. Connection pool exhaustion cascades to dependent services
3. Health checks detected issue but didn't prevent it

**Process**:
1. Runbook was helpful but incomplete for this scenario
2. Need faster escalation criteria for database issues
3. Communication with stakeholders was delayed

**Monitoring**:
1. Need connection pool metrics and alerts
2. Database performance dashboard would help diagnosis
3. Automated remediation could reduce MTTR

---

### Action Items

| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| Increase Memgraph connection pool to 200 | @sre-team | 2025-10-21 | ✅ Complete |
| Add connection pool alerts | @sre-team | 2025-10-22 | 🔄 In Progress |
| Update runbook with new scenario | @oncall | 2025-10-23 | ⏳ Pending |
| Implement auto-remediation | @sre-team | 2025-10-27 | ⏳ Pending |

---

### Attachments

- [Link to Slack thread]
- [Link to incident ticket]
- [Link to grafana dashboard]
- [Log files: /tmp/incident-YYYY-MM-DD/]

---

## Diagnostic Commands

### Quick Health Check (All Services)

```bash
#!/bin/bash
# quick-health.sh - Check health of all Archon services

echo "=== Container Status ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep archon

echo -e "\n=== Health Checks ==="
services=(
  "archon-server:8181"
  "archon-mcp:8151"
  "archon-intelligence:8053"
  "archon-bridge:8054"
  "archon-search:8055"
  "archon-langextract:8156"
)

for service in "${services[@]}"; do
  name="${service%:*}"
  port="${service#*:}"
  echo -n "$name: "
  if curl -sf -m 5 "http://localhost:$port/health" > /dev/null; then
    echo "✅ HEALTHY"
  else
    echo "❌ UNHEALTHY"
  fi
done

echo -e "\n=== Database Health ==="
echo -n "Qdrant: "
curl -sf http://localhost:6333/readyz > /dev/null && echo "✅ HEALTHY" || echo "❌ UNHEALTHY"

echo -n "Memgraph: "
docker exec archon-memgraph bash -c "exec 3<>/dev/tcp/localhost/7444" 2>/dev/null && echo "✅ HEALTHY" || echo "❌ UNHEALTHY"

echo -n "Valkey: "
docker exec archon-valkey valkey-cli ping 2>/dev/null | grep -q PONG && echo "✅ HEALTHY" || echo "❌ UNHEALTHY"

echo -e "\n=== Resource Usage ==="
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep archon
```

---

### Detailed Service Diagnostics

```bash
#!/bin/bash
# diagnose-service.sh - Detailed diagnostics for a specific service

SERVICE=${1:-archon-intelligence}

echo "=== Service: $SERVICE ==="

echo -e "\n1. Container Status:"
docker ps -a --filter name=$SERVICE --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo -e "\n2. Health Check:"
docker inspect $SERVICE --format='{{.State.Health.Status}}'

echo -e "\n3. Resource Usage:"
docker stats $SERVICE --no-stream --format "CPU: {{.CPUPerc}}\tMemory: {{.MemUsage}}\tNet I/O: {{.NetIO}}"

echo -e "\n4. Recent Logs (last 50 lines):"
docker logs $SERVICE --tail 50

echo -e "\n5. Error Logs:"
docker logs $SERVICE --tail 200 | grep -i "error\|critical\|fatal\|exception" | tail -20

echo -e "\n6. Environment Variables:"
docker exec $SERVICE env | grep -E "PORT|URL|ENABLE|LOG_LEVEL"

echo -e "\n7. Network Connectivity:"
docker inspect $SERVICE --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'

echo -e "\n8. Recent Restarts:"
docker events --filter container=$SERVICE --since 1h --until now | grep -E "start|stop|restart|die"
```

---

### Performance Diagnostics

```bash
#!/bin/bash
# performance-check.sh - Check performance metrics across services

echo "=== Intelligence Service Performance ==="
curl -s http://localhost:8053/api/pattern-learning/metrics | jq .

echo -e "\n=== Cache Performance ==="
docker exec archon-valkey valkey-cli -a archon_cache_2025 INFO stats | grep -E "keyspace_hits|keyspace_misses|evicted_keys|expired_keys"

echo -e "\n=== Qdrant Performance ==="
curl -s http://localhost:6333/collections/archon_vectors | jq '.result | {vectors_count, indexed_vectors_count, points_count}'

echo -e "\n=== Query Latency (sample) ==="
time curl -s http://localhost:8053/health > /dev/null
time curl -s http://localhost:8055/health > /dev/null
time curl -s http://localhost:6333/readyz > /dev/null
```

---

### Log Analysis

```bash
#!/bin/bash
# analyze-logs.sh - Analyze logs for common issues

SERVICE=${1:-archon-intelligence}
LINES=${2:-500}

echo "=== Analyzing logs for $SERVICE (last $LINES lines) ==="

LOGS=$(docker logs $SERVICE --tail $LINES)

echo -e "\n1. Error Summary:"
echo "$LOGS" | grep -i "error" | wc -l | xargs echo "Total errors:"
echo "$LOGS" | grep -i "critical" | wc -l | xargs echo "Critical errors:"
echo "$LOGS" | grep -i "fatal" | wc -l | xargs echo "Fatal errors:"

echo -e "\n2. Most Common Errors:"
echo "$LOGS" | grep -i "error" | sort | uniq -c | sort -rn | head -10

echo -e "\n3. Connection Issues:"
echo "$LOGS" | grep -iE "connection|timeout|unavailable" | tail -10

echo -e "\n4. Performance Issues:"
echo "$LOGS" | grep -iE "slow|timeout|latency" | tail -10

echo -e "\n5. Recent Critical Events:"
echo "$LOGS" | grep -i "critical\|fatal" | tail -10
```

---

### Network Diagnostics

```bash
#!/bin/bash
# network-check.sh - Check network connectivity between services

echo "=== Network Diagnostics ==="

echo -e "\n1. Container Network Membership:"
docker network inspect app-network --format '{{range .Containers}}{{.Name}} {{.IPv4Address}}{{"\n"}}{{end}}' | grep archon

echo -e "\n2. Port Bindings:"
for service in archon-server archon-mcp archon-intelligence archon-bridge archon-search; do
  echo "$service:"
  docker port $service 2>/dev/null || echo "  Not running"
done

echo -e "\n3. Inter-Service Connectivity:"
echo "archon-intelligence → memgraph:"
docker exec archon-intelligence ping -c 2 memgraph 2>/dev/null && echo "✅ OK" || echo "❌ FAILED"

echo "archon-search → qdrant:"
docker exec archon-search curl -sf -m 2 http://qdrant:6333/readyz > /dev/null && echo "✅ OK" || echo "❌ FAILED"

echo "archon-mcp → archon-intelligence:"
docker exec archon-mcp curl -sf -m 2 http://archon-intelligence:8053/health > /dev/null && echo "✅ OK" || echo "❌ FAILED"

echo -e "\n4. External Connectivity:"
echo "archon-bridge → Supabase:"
docker exec archon-bridge curl -sf -m 5 "${SUPABASE_URL}/rest/v1/" > /dev/null && echo "✅ OK" || echo "❌ FAILED"
```

---

## Real Alert Examples

### Example 1: Memgraph Connection Pool Exhausted

**Alert Received** (2025-10-15 14:32 UTC):
```
🚨 Pipeline Alert: Container Unhealthy: archon-intelligence

Severity: CRITICAL
Metric: container_health
Current Value: 0.0
Threshold: 1.0

Description:
Container archon-intelligence failed health check

Recent Logs:
```
neo4j.exceptions.ServiceUnavailable: Failed to establish connection to memgraph:7687
neo4j.exceptions.SessionExpired: Session expired, server probably went away
CRITICAL: Database connection pool exhausted (active: 100/100)
```
```

**Root Cause**: Memgraph connection pool size (100) insufficient for production load. Long-running queries held connections, preventing new requests.

**Resolution Steps**:
1. Identified connection pool exhaustion in logs
2. Restarted Memgraph to clear hung connections: `docker restart memgraph`
3. Increased pool size via environment: `MEMGRAPH_CONNECTION_POOL_SIZE=200`
4. Restarted intelligence service: `docker restart archon-intelligence`
5. Verified recovery: `curl http://localhost:8053/health`

**Time to Resolution**: 12 minutes

**Preventive Actions**:
- Increased default connection pool to 200
- Added connection pool monitoring alert (>80% usage)
- Implemented query timeout (30s max)
- Added automated connection pool scaling

---

### Example 2: Qdrant Vector Search Timeout

**Alert Received** (2025-10-18 09:15 UTC):
```
⚠️ Pipeline Alert: Errors Detected: archon-search

Severity: WARNING
Metric: container_errors
Current Value: 5.0
Threshold: 0.0

Description:
Container archon-search has warnings/errors

**Detected Errors (5):**
```
• ERROR: Request timeout after 5 seconds (GET /collections/archon_vectors/points/search)
• Exception in query execution: QdrantException: Timeout waiting for search results
• TimeoutError: Search operation exceeded 5s timeout
```
```

**Root Cause**: Qdrant vector index not optimized, causing slow searches (>5s). Index fragmentation after bulk insertions.

**Resolution Steps**:
1. Checked Qdrant collection stats: `curl http://localhost:6333/collections/archon_vectors`
2. Identified unoptimized segments (50+ segments vs optimal 2-5)
3. Triggered index optimization: `curl -X POST http://localhost:6333/collections/archon_vectors/points/optimize`
4. Waited for optimization (3 minutes)
5. Verified search performance improved (<500ms)

**Time to Resolution**: 8 minutes

**Preventive Actions**:
- Enabled auto-optimization: `QDRANT__STORAGE__OPTIMIZERS__AUTO_OPTIMIZE=true`
- Added index optimization to daily maintenance
- Increased search timeout to 10s for safety margin
- Added performance monitoring for search latency

---

### Example 3: Valkey Cache OOM

**Alert Received** (2025-10-19 16:45 UTC):
```
🔴 Pipeline Alert: Critical Errors: archon-valkey

Severity: CRITICAL
Metric: container_errors
Current Value: 3.0
Threshold: 0.0

Description:
Container archon-valkey has critical errors

**Detected Errors (3):**
```
• CRITICAL: Out of memory (used: 512MB, max: 512MB)
• ERROR: OOM command not allowed when used memory > maxmemory
• FATAL: Cannot allocate memory for new key
```
```

**Root Cause**: Cache memory limit (512MB) exceeded due to large result sets being cached. LRU eviction couldn't keep up with write rate.

**Resolution Steps**:
1. Checked memory usage: `docker exec archon-valkey valkey-cli INFO memory`
2. Identified large keys: `docker exec archon-valkey valkey-cli --bigkeys`
3. Emergency cache clear: `docker exec archon-valkey valkey-cli FLUSHDB`
4. Increased memory limit to 1GB in docker-compose.yml
5. Restarted Valkey: `docker restart archon-valkey`
6. Adjusted cache TTL to reduce memory pressure

**Time to Resolution**: 15 minutes

**Preventive Actions**:
- Increased memory limit to 1GB
- Reduced cache TTL from 5min to 3min
- Added max entry size limit (1MB)
- Implemented cache key size monitoring
- Added memory usage alert (>80%)

---

### Example 4: Kafka Consumer Lag

**Alert Received** (2025-10-20 11:20 UTC):
```
⚠️ Pipeline Alert: Errors Detected: archon-kafka-consumer

Severity: WARNING
Metric: container_errors
Current Value: 2.0
Threshold: 0.0

Description:
Container archon-kafka-consumer has warnings/errors

**Detected Errors (2):**
```
• ERROR: Consumer lag exceeds 1000 messages (current: 2547)
• Exception in event handler: Timeout processing codegen validation event
```
```

**Root Cause**: Slow event processing (>5s per message) caused consumer lag. Intelligence service requests were timing out.

**Resolution Steps**:
1. Checked consumer lag: `docker logs archon-kafka-consumer | grep "lag"`
2. Identified slow intelligence service calls (>10s)
3. Checked intelligence service health: `curl http://localhost:8053/health`
4. Found Memgraph connection issues in intelligence service
5. Restarted Memgraph and intelligence service
6. Consumer lag reduced to <100 within 5 minutes

**Time to Resolution**: 18 minutes

**Preventive Actions**:
- Increased consumer timeout from 30s to 60s
- Added circuit breaker for intelligence service calls
- Implemented async event processing
- Added consumer lag monitoring alert (>500 messages)
- Increased max.poll.records from 500 to 1000

---

### Example 5: Supabase Connection Timeout

**Alert Received** (2025-10-17 08:30 UTC):
```
🚨 Pipeline Alert: Critical Errors: archon-bridge

Severity: CRITICAL
Metric: container_errors
Current Value: 4.0
Threshold: 0.0

Description:
Container archon-bridge has critical errors

**Detected Errors (4):**
```
• ConnectionError: Unable to connect to Supabase (timeout after 10s)
• CRITICAL: PostgreSQL connection pool exhausted
• FATAL: Failed to fetch metadata from Supabase
```
```

**Root Cause**: Supabase service degradation (their incident, not ours). High latency caused connection timeouts.

**Resolution Steps**:
1. Verified Supabase status page: https://status.supabase.com (degraded performance)
2. Increased connection timeout from 10s to 30s
3. Reduced connection pool size to avoid overload
4. Implemented circuit breaker pattern
5. Service recovered when Supabase resolved their issue (45 minutes later)

**Time to Resolution**: 45 minutes (waiting for vendor)

**Preventive Actions**:
- Implemented circuit breaker for Supabase calls
- Added retry logic with exponential backoff
- Configured fallback to cached metadata
- Added Supabase status page monitoring
- Documented vendor escalation process

---

## Appendix

### Monitoring Dashboard URLs

- **Slack Alerts**: `#archon-alerts` channel
- **Grafana**: http://grafana.archon.dev (if configured)
- **Logs**: `docker logs <service>` or centralized logging (if configured)
- **Metrics**: Service health endpoints (`/health`)

---

### Configuration Files

- **Docker Compose**: `/Volumes/PRO-G40/Code/omniarchon/deployment/docker-compose.yml`
- **Environment**: `/Volumes/PRO-G40/Code/omniarchon/python/.env`
- **Alerting Config**: Environment variables (SLACK_WEBHOOK_URL, ALERT_*)
- **Service Config**: Each service's `main.py` or config files

---

### Related Documentation

- **Slack Alerting Setup**: `/Volumes/PRO-G40/Code/omniarchon/python/docs/SLACK_ALERTING.md`
- **Service Architecture**: `/Volumes/PRO-G40/Code/omniarchon/CLAUDE.md`
- **Container Health Monitor**: `/Volumes/PRO-G40/Code/omniarchon/python/src/server/services/container_health_monitor.py`

---

### Useful Links

- **Docker Documentation**: https://docs.docker.com/
- **Qdrant Docs**: https://qdrant.tech/documentation/
- **Memgraph Docs**: https://memgraph.com/docs/
- **Valkey Docs**: https://valkey.io/docs/
- **Supabase Status**: https://status.supabase.com/

---

### Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-10-20 | @sre-team | Initial release: 12 services, 8 alert categories, 5 real examples |

---

**Last Updated**: 2025-10-20
**Maintained By**: SRE Team
**Feedback**: Create issue with label `runbook` or ping `@sre-team` in Slack
