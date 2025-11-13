"""
Platform Health Models

Response models for platform-level health monitoring.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ServiceHealthDetail(BaseModel):
    """Individual service health details."""

    name: str = Field(..., description="Service name")
    status: str = Field(..., description="Service status (healthy/degraded/unhealthy)")
    uptime: Optional[str] = Field(None, description="Service uptime (e.g., '99.9%')")
    latency_ms: Optional[float] = Field(
        None, description="Service response latency in milliseconds"
    )
    message: Optional[str] = Field(None, description="Status message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional service-specific details"
    )
    last_checked: datetime = Field(..., description="Last health check timestamp")


class DatabaseHealth(BaseModel):
    """Database health status."""

    status: str = Field(..., description="Database status (healthy/degraded/unhealthy)")
    latency_ms: float = Field(..., description="Database query latency in milliseconds")
    message: Optional[str] = Field(None, description="Status message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Database-specific details (table count, size, etc.)"
    )


class KafkaHealth(BaseModel):
    """Kafka health status."""

    status: str = Field(..., description="Kafka status (healthy/degraded/unhealthy)")
    lag: int = Field(..., description="Consumer lag")
    message: Optional[str] = Field(None, description="Status message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Kafka-specific details (brokers, topics, etc.)"
    )


class PlatformHealthResponse(BaseModel):
    """Complete platform health response."""

    overall_status: str = Field(
        ..., description="Overall platform status (healthy/degraded/unhealthy)"
    )
    database: DatabaseHealth = Field(..., description="Database health")
    kafka: KafkaHealth = Field(..., description="Kafka health")
    services: List[ServiceHealthDetail] = Field(
        ..., description="Individual service health status"
    )
    total_response_time_ms: float = Field(
        ..., description="Total health check time in milliseconds"
    )
    checked_at: datetime = Field(..., description="Health check timestamp")
    healthy_count: int = Field(..., description="Number of healthy services")
    degraded_count: int = Field(..., description="Number of degraded services")
    unhealthy_count: int = Field(..., description="Number of unhealthy services")
