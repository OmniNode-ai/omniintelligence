# MCP Document Indexing Pipeline - Operations & Monitoring Guide

## Overview

This document provides comprehensive operational guidance for monitoring and maintaining the MCP document indexing pipeline. The pipeline processes documents through multiple microservices with end-to-end performance monitoring, alerting, and automated health checks.

## Architecture Overview

### Pipeline Flow
```
MCP Creation → Server → Bridge → Intelligence → Search → Qdrant/Memgraph
    (2s)      (2s)     (5s)        (10s)        (3s)      (2s)
```

### Service Ecosystem
- **archon-server** (8181): Main FastAPI server with Socket.IO
- **archon-mcp** (8051): MCP protocol server for Claude Code integration
- **archon-bridge** (8054): PostgreSQL-Memgraph synchronization service
- **archon-intelligence** (8053): Entity extraction and knowledge graph processing
- **archon-search** (8055): Vector + Graph + Relational search orchestration
- **qdrant** (6333): High-performance vector database
- **memgraph** (7687): Knowledge graph database
- **archon-langextract** (8156): Language-aware data extraction (optional)

## Performance SLAs

### End-to-End Pipeline
- **Target**: 15 seconds (95% of requests)
- **Warning**: 30 seconds
- **Critical**: 60 seconds
- **Success Rate**: 99.5%

### Individual Services
| Service | Target | Warning | Critical | Business Impact |
|---------|--------|---------|----------|-----------------|
| MCP Creation | 2s | 5s | 10s | HIGH |
| Bridge Sync | 2s | 5s | 10s | MEDIUM |
| Intelligence Processing | 5s | 10s | 20s | HIGH |
| Vector Embedding | 1s | 3s | 5s | MEDIUM |
| Qdrant Indexing | 1s | 2s | 5s | MEDIUM |
| Search Indexing | 2s | 5s | 10s | MEDIUM |

### Availability
- **Target**: 99.9% (8.76 hours downtime/year)
- **Warning**: 99.5%
- **Critical**: 99.0%

## Monitoring Endpoints

### Dashboard & Metrics
- **Performance Dashboard**: `GET /pipeline/monitoring/performance/dashboard`
- **Prometheus Metrics**: `GET /pipeline/monitoring/metrics`
- **Real-time WebSocket**: `WS /pipeline/monitoring/ws/realtime`

### Health Checks
- **Pipeline Status**: `GET /pipeline/health/status`
- **Service Health**: `GET /pipeline/health/services`
- **Deep Health Check**: `GET /pipeline/health/deep`
- **Readiness Probe**: `GET /pipeline/health/ready`
- **Liveness Probe**: `GET /pipeline/health/live`

### Tracing & Analytics
- **Trace Details**: `GET /pipeline/monitoring/traces/{correlation_id}`
- **Performance Analytics**: `GET /pipeline/monitoring/analytics/performance`
- **Active Traces**: `GET /pipeline/monitoring/traces?status=active`

### Alerting
- **Active Alerts**: `GET /pipeline/monitoring/alerts/active`
- **Create Alert**: `POST /pipeline/monitoring/alerts/threshold`
- **Alert Statistics**: `GET /pipeline/monitoring/alerts/statistics`

## Key Metrics to Monitor

### Latency Metrics
```
# End-to-end pipeline duration
archon_pipeline_duration_seconds{stage="end_to_end"}

# Individual service latency
archon_service_latency_seconds{service="archon-intelligence"}

# P95 latency by stage
histogram_quantile(0.95, archon_pipeline_duration_seconds)
```

### Throughput Metrics
```
# Documents processed per minute
archon_processing_rate_per_minute

# Pipeline executions per hour
rate(archon_pipeline_executions_total[1h]) * 3600

# Queue sizes
archon_pipeline_queue_size
```

### Error Metrics
```
# Pipeline error rate
rate(archon_pipeline_errors_total[5m]) / rate(archon_pipeline_executions_total[5m])

# Service error rates
rate(archon_http_errors_total[5m]) / rate(archon_http_requests_total[5m])
```

### Resource Metrics
```
# CPU usage
archon_system_cpu_usage_percent

# Memory usage
archon_system_memory_usage_bytes

# Service health scores
archon_service_health_score
```

## Alerting Configuration

### Critical Alerts (Immediate Response)
1. **Pipeline Latency Critical** (>60s for 3 minutes)
2. **Low Success Rate** (<90% for 10 minutes)
3. **Service Unavailable** (Critical service down)
4. **High Error Rate** (>10% for 10 minutes)

### Warning Alerts (Monitor Closely)
1. **Pipeline Latency Warning** (>30s for 5 minutes)
2. **Service Health Degraded** (<80% health score)
3. **High Queue Backlog** (>100 items for 5 minutes)
4. **Resource Usage High** (>80% CPU/Memory for 15 minutes)

### Notification Channels
- **Email**: operations@company.com
- **Slack**: #pipeline-alerts
- **Webhook**: For integration with incident management
- **SMS**: For critical alerts during off-hours

## Troubleshooting Runbooks

### High Pipeline Latency (>30s)

#### Immediate Actions
1. **Check Service Health**:
   ```bash
   curl http://localhost:8181/pipeline/health/status
   ```

2. **Identify Bottleneck**:
   ```bash
   curl http://localhost:8181/pipeline/monitoring/performance/dashboard?time_window=1h
   ```

3. **Check Active Traces**:
   ```bash
   curl http://localhost:8181/pipeline/monitoring/traces?status=active&limit=10
   ```

#### Investigation Steps
1. **Service-by-Service Analysis**:
   - Bridge Service: Check PostgreSQL/Memgraph connectivity
   - Intelligence Service: Monitor CPU/memory usage
   - Search Service: Check Qdrant performance
   - Vector Processing: Monitor embedding generation

2. **Resource Utilization**:
   ```bash
   # Check container resources
   docker stats

   # Check service metrics
   curl http://localhost:8181/monitoring/health/services
   ```

3. **Database Performance**:
   ```bash
   # Qdrant health
   curl http://localhost:6333/readyz

   # Memgraph connectivity
   curl http://localhost:7444/
   ```

#### Resolution Actions
- **Scale Services**: Increase container resources for bottlenecked services
- **Optimize Queries**: Review slow database operations
- **Cache Implementation**: Add caching for frequently accessed data
- **Load Balancing**: Distribute load across service instances

### Low Success Rate (<95%)

#### Immediate Actions
1. **Check Error Patterns**:
   ```bash
   curl http://localhost:8181/pipeline/monitoring/analytics/performance?group_by=service
   ```

2. **Review Recent Failures**:
   ```bash
   curl http://localhost:8181/pipeline/monitoring/traces?status=failed&limit=20
   ```

#### Investigation Steps
1. **Error Analysis by Service**:
   - Check service logs for error details
   - Identify common failure patterns
   - Review dependency health

2. **Data Quality Issues**:
   - Validate input document formats
   - Check for processing timeouts
   - Review extraction failures

#### Resolution Actions
- **Service Restart**: Restart failing services
- **Configuration Review**: Verify service configurations
- **Data Validation**: Implement stricter input validation
- **Timeout Adjustment**: Increase processing timeouts if needed

### Service Unavailable

#### Immediate Actions
1. **Service Health Check**:
   ```bash
   curl http://localhost:8181/pipeline/health/services/{service_name}
   ```

2. **Container Status**:
   ```bash
   docker ps -a | grep {service_name}
   docker logs {container_name} --tail=100
   ```

#### Recovery Steps
1. **Container Restart**:
   ```bash
   docker restart {container_name}
   ```

2. **Health Verification**:
   ```bash
   # Wait 30 seconds, then check
   curl http://localhost:8181/pipeline/health/ready
   ```

3. **Dependency Check**:
   ```bash
   curl http://localhost:8181/pipeline/health/services/{service_name}/dependencies
   ```

### High Resource Usage

#### Investigation
1. **Resource Monitoring**:
   ```bash
   # System resources
   htop
   df -h

   # Container resources
   docker stats --no-stream
   ```

2. **Service Performance**:
   ```bash
   curl http://localhost:8181/monitoring/performance/trends
   ```

#### Optimization Actions
- **Memory Optimization**: Increase container memory limits
- **CPU Scaling**: Add more CPU cores to intensive services
- **Storage Cleanup**: Clean up old logs and temporary files
- **Connection Pooling**: Optimize database connection pools

## Performance Optimization

### Baseline Establishment
```bash
# Establish performance baseline
curl -X POST http://localhost:8181/pipeline/monitoring/performance/baseline \
  -H "Content-Type: application/json" \
  -d '{"operation_name": "document_indexing", "duration_minutes": 60}'
```

### Optimization Opportunities
```bash
# Get optimization recommendations
curl http://localhost:8181/pipeline/monitoring/optimization/opportunities
```

### Performance Forecasting
```bash
# Get performance forecast
curl http://localhost:8181/pipeline/monitoring/performance/forecast?baseline_id={id}&hours=24
```

## Capacity Planning

### Traffic Patterns
- **Peak Hours**: 9 AM - 5 PM business hours
- **Expected Growth**: 20% increase per quarter
- **Seasonal Variations**: Higher load during product releases

### Scaling Thresholds
- **CPU Usage**: Scale at 70% sustained usage
- **Memory Usage**: Scale at 80% usage
- **Queue Depth**: Scale at 50 items in queue
- **Response Time**: Scale at 20s average latency

### Resource Requirements
| Service | CPU (cores) | Memory (GB) | Storage (GB) |
|---------|-------------|-------------|--------------|
| archon-server | 2-4 | 4-8 | 10 |
| archon-intelligence | 4-8 | 8-16 | 20 |
| archon-search | 2-4 | 4-8 | 10 |
| qdrant | 4-8 | 8-16 | 100-500 |
| memgraph | 2-4 | 4-8 | 50-200 |

## Maintenance Windows

### Regular Maintenance
- **Daily**: Log rotation and cleanup (2 AM UTC)
- **Weekly**: Performance baseline updates (Sunday 3 AM UTC)
- **Monthly**: Capacity planning review and optimization

### Planned Downtime
- **Database Maintenance**: 1st Sunday of month, 2-4 AM UTC
- **Service Updates**: 3rd Sunday of month, 1-3 AM UTC
- **Infrastructure Updates**: As needed, coordinated with stakeholders

## Disaster Recovery

### Backup Strategy
- **Configuration**: Daily automated backups
- **Vector Data**: Daily incremental, weekly full backups
- **Knowledge Graph**: Daily automated exports
- **Monitoring Data**: 90-day retention with weekly aggregation

### Recovery Procedures
1. **Service Recovery**: Restore from container images
2. **Data Recovery**: Restore from latest backup
3. **Configuration Recovery**: Apply infrastructure as code
4. **Validation**: Run full health checks and performance tests

### Recovery Time Objectives (RTO)
- **Critical Services**: 15 minutes
- **Full Pipeline**: 30 minutes
- **Complete System**: 2 hours

### Recovery Point Objectives (RPO)
- **Configuration Data**: 1 hour
- **Vector Indexes**: 4 hours
- **Knowledge Graph**: 4 hours

## Security Monitoring

### Security Metrics
- **Authentication Failures**: Monitor for brute force attempts
- **API Rate Limiting**: Track excessive API usage
- **Resource Access**: Monitor unauthorized access attempts
- **Data Integrity**: Validate data checksums and integrity

### Security Alerts
- **Multiple Failed Logins**: >5 failures in 5 minutes
- **Unusual Traffic Patterns**: >2x normal request rate
- **Unauthorized Access**: Access to restricted endpoints
- **Data Integrity Issues**: Checksum mismatches

## Compliance & Auditing

### Audit Trail
- **API Access Logs**: 90-day retention
- **Performance Metrics**: 1-year retention with aggregation
- **Security Events**: 2-year retention
- **Configuration Changes**: Permanent retention

### Compliance Reporting
- **Monthly**: Performance SLA compliance reports
- **Quarterly**: Capacity planning and optimization reports
- **Annually**: Security audit and compliance review

## Contact Information

### On-Call Rotation
- **Primary**: DevOps Engineer (Slack: @devops-oncall)
- **Secondary**: Platform Engineer (Slack: @platform-oncall)
- **Escalation**: Engineering Manager (Slack: @eng-manager)

### Support Channels
- **Slack**: #pipeline-ops (monitoring alerts)
- **Email**: pipeline-ops@company.com
- **Incident Management**: PagerDuty integration
- **Documentation**: Internal wiki and runbooks

## Quick Reference Commands

### Health Checks
```bash
# Quick health check
curl -s http://localhost:8181/pipeline/health/status | jq '.overall_status'

# Deep health check
curl -s http://localhost:8181/pipeline/health/deep | jq '.overall_health.status'

# Service-specific health
curl -s http://localhost:8181/pipeline/health/services/archon-intelligence | jq '.health.status'
```

### Performance Monitoring
```bash
# Current performance metrics
curl -s http://localhost:8181/pipeline/monitoring/status | jq '.metrics'

# Active pipeline executions
curl -s http://localhost:8181/pipeline/monitoring/traces?status=active | jq '.total_count'

# Error rate
curl -s http://localhost:8181/pipeline/monitoring/analytics/performance | jq '.performance_stats.error_rate'
```

### Alerting
```bash
# Active alerts
curl -s http://localhost:8181/pipeline/monitoring/alerts/active | jq '.active_alerts'

# Alert statistics
curl -s http://localhost:8181/pipeline/monitoring/alerts/statistics | jq '.'
```

This operational guide should be reviewed and updated quarterly to reflect changes in the pipeline architecture, performance requirements, and operational procedures.
