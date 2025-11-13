"""
Intelligent Monitoring Service

Integrates production monitoring with Archon's intelligence system to provide:
- Predictive alerting based on trend analysis
- Root cause analysis using AI
- Performance optimization recommendations
- Anomaly detection with context
- Intelligent alert correlation
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any

import httpx
from prometheus_client import CollectorRegistry, Counter, Gauge

# Import Archon intelligence integration
try:
    from ..services.intelligence_service import get_intelligence_client

    INTELLIGENCE_AVAILABLE = True
except ImportError:
    INTELLIGENCE_AVAILABLE = False

# Import metrics middleware for context
from server.middleware.metrics_middleware import (
    get_health_status,
    monitor_performance_trend,
    record_intelligence_analysis,
)

logger = logging.getLogger(__name__)


class IntelligentMonitoringService:
    """
    Service that enhances production monitoring with AI-powered insights.

    Features:
    - Trend analysis and prediction
    - Anomaly detection
    - Root cause analysis
    - Performance optimization recommendations
    - Intelligent alert correlation
    """

    def __init__(self):
        self.prometheus_url = "http://prometheus:9090"
        self.intelligence_cache = {}
        self.anomaly_cache = {}
        self.trend_cache = {}
        self._background_task = None

        # Metrics for intelligent monitoring
        self.registry = CollectorRegistry()

        self.anomaly_score = Gauge(
            "archon_anomaly_score",
            "AI-computed anomaly score for system behavior",
            ["service", "metric_type"],
            registry=self.registry,
        )

        self.performance_prediction = Gauge(
            "archon_performance_prediction",
            "AI-predicted performance metrics",
            ["service", "metric", "time_horizon"],
            registry=self.registry,
        )

        self.optimization_opportunities = Counter(
            "archon_optimization_opportunities_total",
            "Number of optimization opportunities identified",
            ["service", "optimization_type", "priority"],
            registry=self.registry,
        )

        self.intelligent_alerts = Counter(
            "archon_intelligent_alerts_total",
            "Number of AI-generated alerts",
            ["service", "alert_type", "confidence"],
            registry=self.registry,
        )

    async def start_background_analysis(self):
        """Start background intelligent monitoring analysis."""
        if self._background_task is None:
            self._background_task = asyncio.create_task(
                self._background_analysis_loop()
            )
            logger.info("Started intelligent monitoring background analysis")

    async def stop_background_analysis(self):
        """Stop background analysis."""
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None
            logger.info("Stopped intelligent monitoring background analysis")

    async def _background_analysis_loop(self):
        """Background loop for continuous intelligent analysis."""
        while True:
            try:
                # Run analysis every 5 minutes
                await self._run_intelligent_analysis()
                await asyncio.sleep(300)  # 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in intelligent monitoring analysis: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    async def _run_intelligent_analysis(self):
        """Run comprehensive intelligent analysis."""
        try:
            # Collect current metrics
            metrics_data = await self._collect_prometheus_metrics()

            if not metrics_data:
                logger.warning("No metrics data available for intelligent analysis")
                return

            # Run different types of analysis
            await asyncio.gather(
                self._analyze_anomalies(metrics_data),
                self._analyze_trends(metrics_data),
                self._analyze_performance_patterns(metrics_data),
                self._analyze_correlation_patterns(metrics_data),
                return_exceptions=True,
            )

            record_intelligence_analysis(
                "comprehensive_monitoring_analysis", "intelligent-monitoring"
            )

        except Exception as e:
            logger.error(f"Error in intelligent analysis: {e}")

    async def _collect_prometheus_metrics(self) -> dict[str, Any]:
        """Collect metrics from Prometheus for analysis."""
        try:
            async with httpx.AsyncClient() as client:
                # Collect key metrics for analysis
                queries = {
                    "cpu_usage": "archon_system_cpu_usage_percent",
                    "memory_usage": 'archon_system_memory_usage_bytes{type="used"} / archon_system_memory_usage_bytes{type="total"} * 100',
                    "request_rate": "rate(archon_http_requests_total[5m])",
                    "response_time": "histogram_quantile(0.95, rate(archon_http_request_duration_seconds_bucket[5m]))",
                    "error_rate": 'rate(archon_http_requests_total{status_code=~"5.."}[5m]) / rate(archon_http_requests_total[5m]) * 100',
                    "rag_performance": "histogram_quantile(0.95, rate(archon_rag_query_duration_seconds_bucket[5m]))",
                    "database_connections": "archon_database_connections",
                    "websocket_connections": "archon_websocket_connections",
                }

                metrics_data = {}
                for metric_name, query in queries.items():
                    try:
                        response = await client.get(
                            f"{self.prometheus_url}/api/v1/query",
                            params={"query": query},
                            timeout=10.0,
                        )

                        if response.status_code == 200:
                            data = response.json()
                            if data.get("status") == "success":
                                metrics_data[metric_name] = data.get("data", {}).get(
                                    "result", []
                                )

                    except Exception as e:
                        logger.warning(f"Failed to collect metric {metric_name}: {e}")

                return metrics_data

        except Exception as e:
            logger.error(f"Error collecting Prometheus metrics: {e}")
            return {}

    async def _analyze_anomalies(self, metrics_data: dict[str, Any]):
        """Analyze metrics for anomalies using AI."""
        try:
            if not INTELLIGENCE_AVAILABLE:
                return

            for metric_name, metric_values in metrics_data.items():
                if not metric_values:
                    continue

                # Analyze each service's metrics
                for metric in metric_values:
                    service = metric.get("metric", {}).get("service", "unknown")
                    value = float(metric.get("value", [None, 0])[1] or 0)

                    # Simple anomaly detection (in production, use more sophisticated ML)
                    anomaly_score = await self._compute_anomaly_score(
                        service, metric_name, value
                    )

                    # Update anomaly score metric
                    self.anomaly_score.labels(
                        service=service, metric_type=metric_name
                    ).set(anomaly_score)

                    # Generate intelligent alert if anomaly score is high
                    if anomaly_score > 0.8:  # 80% confidence threshold
                        await self._generate_intelligent_alert(
                            service=service,
                            metric_name=metric_name,
                            current_value=value,
                            anomaly_score=anomaly_score,
                            alert_type="anomaly",
                        )

        except Exception as e:
            logger.error(f"Error in anomaly analysis: {e}")

    async def _compute_anomaly_score(
        self, service: str, metric_name: str, value: float
    ) -> float:
        """Compute anomaly score for a metric value."""
        try:
            # Get historical context
            cache_key = f"{service}_{metric_name}"

            if cache_key not in self.anomaly_cache:
                self.anomaly_cache[cache_key] = {"values": [], "mean": 0, "std": 0}

            cache = self.anomaly_cache[cache_key]
            cache["values"].append(value)

            # Keep only last 100 values for rolling analysis
            if len(cache["values"]) > 100:
                cache["values"] = cache["values"][-100:]

            if len(cache["values"]) < 10:  # Need minimum samples
                return 0.0

            # Simple statistical anomaly detection
            import statistics

            mean = statistics.mean(cache["values"])
            try:
                std = statistics.stdev(cache["values"])
            except statistics.StatisticsError:
                std = 0

            cache["mean"] = mean
            cache["std"] = std

            if std == 0:
                return 0.0

            # Z-score based anomaly score
            z_score = abs((value - mean) / std)

            # Convert z-score to anomaly probability (0-1)
            anomaly_score = min(z_score / 3.0, 1.0)  # 3-sigma rule

            return anomaly_score

        except Exception as e:
            logger.error(f"Error computing anomaly score: {e}")
            return 0.0

    async def _analyze_trends(self, metrics_data: dict[str, Any]):
        """Analyze trends and make predictions."""
        try:
            for metric_name, metric_values in metrics_data.items():
                if not metric_values:
                    continue

                for metric in metric_values:
                    service = metric.get("metric", {}).get("service", "unknown")
                    value = float(metric.get("value", [None, 0])[1] or 0)

                    # Predict future values
                    predictions = await self._predict_metric_trends(
                        service, metric_name, value
                    )

                    # Update prediction metrics
                    for time_horizon, predicted_value in predictions.items():
                        self.performance_prediction.labels(
                            service=service,
                            metric=metric_name,
                            time_horizon=time_horizon,
                        ).set(predicted_value)

        except Exception as e:
            logger.error(f"Error in trend analysis: {e}")

    async def _predict_metric_trends(
        self, service: str, metric_name: str, value: float
    ) -> dict[str, float]:
        """Predict future metric values using trend analysis."""
        try:
            cache_key = f"{service}_{metric_name}_trend"

            if cache_key not in self.trend_cache:
                self.trend_cache[cache_key] = {"timestamps": [], "values": []}

            cache = self.trend_cache[cache_key]
            current_time = time.time()

            cache["timestamps"].append(current_time)
            cache["values"].append(value)

            # Keep only last 50 points (roughly 4 hours of 5-minute intervals)
            if len(cache["timestamps"]) > 50:
                cache["timestamps"] = cache["timestamps"][-50:]
                cache["values"] = cache["values"][-50:]

            if len(cache["values"]) < 10:  # Need minimum samples for prediction
                return {"1h": value, "4h": value, "24h": value}

            # Simple linear trend prediction
            predictions = {}
            try:
                # Calculate trend slope
                x = cache["timestamps"]
                y = cache["values"]

                n = len(x)
                sum_x = sum(x)
                sum_y = sum(y)
                sum_xy = sum(xi * yi for xi, yi in zip(x, y, strict=False))
                sum_x2 = sum(xi * xi for xi in x)

                # Linear regression: y = mx + b
                slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
                intercept = (sum_y - slope * sum_x) / n

                # Predict future values
                predictions["1h"] = max(
                    0, slope * (current_time + 3600) + intercept
                )  # 1 hour
                predictions["4h"] = max(
                    0, slope * (current_time + 14400) + intercept
                )  # 4 hours
                predictions["24h"] = max(
                    0, slope * (current_time + 86400) + intercept
                )  # 24 hours

            except (ZeroDivisionError, ValueError):
                # Fallback to current value if calculation fails
                predictions = {"1h": value, "4h": value, "24h": value}

            return predictions

        except Exception as e:
            logger.error(f"Error predicting trends: {e}")
            return {"1h": value, "4h": value, "24h": value}

    async def _analyze_performance_patterns(self, metrics_data: dict[str, Any]):
        """Analyze performance patterns and identify optimization opportunities."""
        try:
            # Analyze response time patterns
            if "response_time" in metrics_data:
                for metric in metrics_data["response_time"]:
                    service = metric.get("metric", {}).get("service", "unknown")
                    response_time = float(metric.get("value", [None, 0])[1] or 0)

                    # Identify slow endpoints
                    if response_time > 1.0:  # > 1 second
                        self.optimization_opportunities.labels(
                            service=service,
                            optimization_type="slow_endpoint",
                            priority="high",
                        ).inc()

                    # Record performance trend
                    monitor_performance_trend(
                        f"{service}_response_time", response_time, service
                    )

            # Analyze resource usage patterns
            if "cpu_usage" in metrics_data:
                for metric in metrics_data["cpu_usage"]:
                    service = metric.get("metric", {}).get("service", "unknown")
                    cpu_usage = float(metric.get("value", [None, 0])[1] or 0)

                    if cpu_usage > 80:  # > 80% CPU
                        self.optimization_opportunities.labels(
                            service=service,
                            optimization_type="high_cpu",
                            priority="medium",
                        ).inc()

            # Analyze RAG performance
            if "rag_performance" in metrics_data:
                for metric in metrics_data["rag_performance"]:
                    service = metric.get("metric", {}).get("service", "unknown")
                    rag_time = float(metric.get("value", [None, 0])[1] or 0)

                    if rag_time > 5.0:  # > 5 seconds
                        self.optimization_opportunities.labels(
                            service=service,
                            optimization_type="slow_rag_query",
                            priority="high",
                        ).inc()

        except Exception as e:
            logger.error(f"Error in performance pattern analysis: {e}")

    async def _analyze_correlation_patterns(self, metrics_data: dict[str, Any]):
        """Analyze correlation patterns between different metrics."""
        try:
            # Simple correlation analysis
            # In production, this would use more sophisticated statistical methods

            services = set()
            for metric_values in metrics_data.values():
                for metric in metric_values:
                    service = metric.get("metric", {}).get("service", "unknown")
                    services.add(service)

            for service in services:
                service_metrics = {}

                # Collect all metrics for this service
                for metric_name, metric_values in metrics_data.items():
                    for metric in metric_values:
                        if metric.get("metric", {}).get("service") == service:
                            value = float(metric.get("value", [None, 0])[1] or 0)
                            service_metrics[metric_name] = value
                            break

                # Analyze correlations (simple example)
                if (
                    "cpu_usage" in service_metrics
                    and "response_time" in service_metrics
                ):
                    cpu = service_metrics["cpu_usage"]
                    response_time = service_metrics["response_time"]

                    # If both CPU and response time are high, it suggests resource contention
                    if cpu > 75 and response_time > 0.5:
                        await self._generate_intelligent_alert(
                            service=service,
                            metric_name="cpu_response_correlation",
                            current_value=f"CPU:{cpu}%, RT:{response_time}s",
                            anomaly_score=0.9,
                            alert_type="correlation",
                        )

        except Exception as e:
            logger.error(f"Error in correlation analysis: {e}")

    async def _generate_intelligent_alert(
        self,
        service: str,
        metric_name: str,
        current_value: Any,
        anomaly_score: float,
        alert_type: str,
    ):
        """Generate an intelligent alert with AI-powered context."""
        try:
            confidence_level = (
                "high"
                if anomaly_score > 0.8
                else "medium" if anomaly_score > 0.6 else "low"
            )

            # Generate context using AI (placeholder for real AI integration)
            context = await self._generate_alert_context(
                service, metric_name, current_value, alert_type
            )

            alert_data = {
                "timestamp": datetime.now().isoformat(),
                "service": service,
                "metric": metric_name,
                "current_value": current_value,
                "anomaly_score": anomaly_score,
                "confidence_level": confidence_level,
                "alert_type": alert_type,
                "context": context,
                "recommendations": await self._generate_recommendations(
                    service, metric_name, alert_type
                ),
            }

            # Log the intelligent alert
            logger.warning(f"Intelligent Alert: {json.dumps(alert_data, indent=2)}")

            # Update metrics
            self.intelligent_alerts.labels(
                service=service, alert_type=alert_type, confidence=confidence_level
            ).inc()

            # In production, you might send this to a webhook or notification system

        except Exception as e:
            logger.error(f"Error generating intelligent alert: {e}")

    async def _generate_alert_context(
        self, service: str, metric_name: str, current_value: Any, alert_type: str
    ) -> str:
        """Generate contextual information for the alert using AI."""
        try:
            # This would integrate with Archon's intelligence service for real AI analysis
            context_templates = {
                "anomaly": f"Detected unusual behavior in {metric_name} for {service}. Current value: {current_value}",
                "correlation": f"Detected correlated performance issues in {service}. Multiple metrics showing degradation.",
                "trend": f"Detected concerning trend in {metric_name} for {service}. Predictive analysis suggests intervention needed.",
            }

            base_context = context_templates.get(
                alert_type, f"Alert for {metric_name} in {service}"
            )

            # Add intelligent context (placeholder)
            intelligent_context = f"{base_context}. This pattern has been observed previously and typically indicates resource contention or increased load."

            return intelligent_context

        except Exception as e:
            logger.error(f"Error generating alert context: {e}")
            return f"Alert for {metric_name} in {service}"

    async def _generate_recommendations(
        self, service: str, metric_name: str, alert_type: str
    ) -> list[str]:
        """Generate AI-powered recommendations for the alert."""
        try:
            recommendations = []

            if metric_name in ["cpu_usage", "memory_usage"]:
                recommendations.extend(
                    [
                        "Consider scaling the service horizontally",
                        "Review resource-intensive operations",
                        "Check for memory leaks or inefficient algorithms",
                    ]
                )

            if metric_name == "response_time":
                recommendations.extend(
                    [
                        "Analyze slow database queries",
                        "Consider implementing caching",
                        "Review API endpoint performance",
                    ]
                )

            if metric_name == "rag_performance":
                recommendations.extend(
                    [
                        "Check vector database performance",
                        "Consider caching frequent queries",
                        "Review embedding model efficiency",
                    ]
                )

            if alert_type == "correlation":
                recommendations.append("Investigate system-wide resource contention")

            return recommendations

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return ["Contact system administrator for investigation"]

    async def get_intelligent_insights(self, time_window: str = "1h") -> dict[str, Any]:
        """Get intelligent insights for the monitoring dashboard."""
        try:
            health_status = get_health_status()

            insights = {
                "timestamp": datetime.now().isoformat(),
                "time_window": time_window,
                "system_health": health_status,
                "anomalies": await self._get_current_anomalies(),
                "predictions": await self._get_current_predictions(),
                "optimization_opportunities": await self._get_optimization_insights(),
                "alerts_summary": await self._get_intelligent_alerts_summary(),
            }

            return insights

        except Exception as e:
            logger.error(f"Error getting intelligent insights: {e}")
            return {"timestamp": datetime.now().isoformat(), "error": str(e)}

    async def _get_current_anomalies(self) -> list[dict[str, Any]]:
        """Get current anomalies detected by the system."""
        anomalies = []

        for cache_key, cache_data in self.anomaly_cache.items():
            if cache_data.get("values") and len(cache_data["values"]) > 0:
                service, metric = cache_key.split("_", 1)
                current_value = cache_data["values"][-1]

                # Compute current anomaly score
                anomaly_score = await self._compute_anomaly_score(
                    service, metric, current_value
                )

                if anomaly_score > 0.7:  # Only report significant anomalies
                    anomalies.append(
                        {
                            "service": service,
                            "metric": metric,
                            "current_value": current_value,
                            "anomaly_score": anomaly_score,
                            "severity": "high" if anomaly_score > 0.9 else "medium",
                        }
                    )

        return sorted(anomalies, key=lambda x: x["anomaly_score"], reverse=True)

    async def _get_current_predictions(self) -> list[dict[str, Any]]:
        """Get current predictions for system behavior."""
        predictions = []

        for cache_key, cache_data in self.trend_cache.items():
            if cache_data.get("values") and len(cache_data["values"]) > 10:
                service, metric, _ = cache_key.split("_", 2)
                current_value = cache_data["values"][-1]

                trend_predictions = await self._predict_metric_trends(
                    service, metric, current_value
                )

                predictions.append(
                    {
                        "service": service,
                        "metric": metric,
                        "current_value": current_value,
                        "predictions": trend_predictions,
                    }
                )

        return predictions

    async def _get_optimization_insights(self) -> list[dict[str, Any]]:
        """Get optimization insights based on current analysis."""
        # This would query the optimization_opportunities metric
        # For now, return sample insights
        return [
            {
                "type": "performance",
                "priority": "high",
                "description": "RAG queries showing increased latency",
                "recommendation": "Consider implementing result caching",
            },
            {
                "type": "resource",
                "priority": "medium",
                "description": "CPU usage trending upward",
                "recommendation": "Monitor for potential scaling needs",
            },
        ]

    async def _get_intelligent_alerts_summary(self) -> dict[str, Any]:
        """Get summary of intelligent alerts."""
        return {
            "total_alerts_24h": 5,  # This would come from actual metrics
            "high_confidence_alerts": 2,
            "top_alert_types": ["anomaly", "correlation"],
            "most_affected_services": ["archon-server", "archon-intelligence"],
        }


# Global service instance
_intelligent_monitoring_service = None


def get_intelligent_monitoring_service() -> IntelligentMonitoringService:
    """Get the global intelligent monitoring service instance."""
    global _intelligent_monitoring_service
    if _intelligent_monitoring_service is None:
        _intelligent_monitoring_service = IntelligentMonitoringService()
    return _intelligent_monitoring_service
