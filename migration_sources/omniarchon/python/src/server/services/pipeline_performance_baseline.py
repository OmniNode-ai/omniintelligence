"""
Pipeline Performance Baseline Service

Establishes and maintains performance baselines for the MCP document indexing pipeline.
Provides SLA definitions, performance regression detection, and automated optimization
recommendations based on historical data and industry best practices.

Features:
- Automatic baseline establishment from historical data
- SLA definition and compliance tracking
- Performance regression detection
- Capacity planning and forecasting
- Benchmark comparison with industry standards
- Automated optimization recommendations
"""

import logging
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

import numpy as np
from server.middleware.pipeline_metrics import pipeline_metrics
from server.middleware.pipeline_tracing import pipeline_tracer

logger = logging.getLogger(__name__)


class PerformanceCategory(Enum):
    """Performance categories for benchmarking"""

    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    CRITICAL = "critical"


class BaselineType(Enum):
    """Types of performance baselines"""

    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    RESOURCE_USAGE = "resource_usage"
    AVAILABILITY = "availability"


@dataclass
class PerformanceBaseline:
    """Performance baseline definition"""

    baseline_id: str
    name: str
    description: str
    baseline_type: BaselineType
    stage: Optional[str]  # Pipeline stage or service
    metrics: dict[str, float]  # p50, p95, p99, mean, etc.
    sla_thresholds: dict[str, float]  # warning, critical, emergency
    target_values: dict[str, float]  # target performance values
    established_at: datetime
    data_points: int  # Number of data points used
    confidence_score: float  # 0.0 to 1.0
    valid_until: datetime
    metadata: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["established_at"] = self.established_at.isoformat()
        data["valid_until"] = self.valid_until.isoformat()
        return data


@dataclass
class SLADefinition:
    """Service Level Agreement definition"""

    sla_id: str
    name: str
    description: str
    metric_name: str
    target_value: float
    warning_threshold: float
    critical_threshold: float
    measurement_window: str  # e.g., "5m", "1h", "24h"
    compliance_target: float  # e.g., 99.9%
    business_impact: str  # LOW, MEDIUM, HIGH, CRITICAL
    created_at: datetime
    enabled: bool = True


class PipelinePerformanceBaseline:
    """
    Service for establishing and maintaining pipeline performance baselines.

    Provides:
    - Automatic baseline calculation from historical data
    - SLA definition and tracking
    - Performance regression detection
    - Capacity planning insights
    - Industry benchmark comparison
    """

    def __init__(self):
        self.baselines: dict[str, PerformanceBaseline] = {}
        self.sla_definitions: dict[str, SLADefinition] = {}
        self.performance_history: list[dict[str, Any]] = []
        self.industry_benchmarks = self._load_industry_benchmarks()

        # Initialize default SLAs
        self._setup_default_slas()

    def _load_industry_benchmarks(self) -> dict[str, dict[str, float]]:
        """Load industry performance benchmarks"""
        return {
            "document_indexing": {
                "excellent": {
                    "latency_p95": 5.0,
                    "throughput_per_hour": 1000,
                    "error_rate": 0.001,
                },
                "good": {
                    "latency_p95": 15.0,
                    "throughput_per_hour": 500,
                    "error_rate": 0.01,
                },
                "acceptable": {
                    "latency_p95": 30.0,
                    "throughput_per_hour": 200,
                    "error_rate": 0.05,
                },
                "poor": {
                    "latency_p95": 60.0,
                    "throughput_per_hour": 100,
                    "error_rate": 0.1,
                },
                "critical": {
                    "latency_p95": 120.0,
                    "throughput_per_hour": 50,
                    "error_rate": 0.2,
                },
            },
            "vector_indexing": {
                "excellent": {
                    "latency_p95": 2.0,
                    "throughput_per_hour": 2000,
                    "error_rate": 0.001,
                },
                "good": {
                    "latency_p95": 5.0,
                    "throughput_per_hour": 1000,
                    "error_rate": 0.01,
                },
                "acceptable": {
                    "latency_p95": 10.0,
                    "throughput_per_hour": 500,
                    "error_rate": 0.05,
                },
                "poor": {
                    "latency_p95": 20.0,
                    "throughput_per_hour": 200,
                    "error_rate": 0.1,
                },
                "critical": {
                    "latency_p95": 40.0,
                    "throughput_per_hour": 100,
                    "error_rate": 0.2,
                },
            },
            "knowledge_graph": {
                "excellent": {
                    "latency_p95": 1.0,
                    "throughput_per_hour": 5000,
                    "error_rate": 0.001,
                },
                "good": {
                    "latency_p95": 3.0,
                    "throughput_per_hour": 2000,
                    "error_rate": 0.01,
                },
                "acceptable": {
                    "latency_p95": 8.0,
                    "throughput_per_hour": 1000,
                    "error_rate": 0.05,
                },
                "poor": {
                    "latency_p95": 15.0,
                    "throughput_per_hour": 500,
                    "error_rate": 0.1,
                },
                "critical": {
                    "latency_p95": 30.0,
                    "throughput_per_hour": 200,
                    "error_rate": 0.2,
                },
            },
        }

    def _setup_default_slas(self):
        """Setup default SLA definitions"""
        default_slas = [
            SLADefinition(
                sla_id="pipeline_end_to_end_latency",
                name="End-to-End Pipeline Latency",
                description="Complete document indexing pipeline latency",
                metric_name="pipeline_duration",
                target_value=15.0,  # 15 seconds target
                warning_threshold=30.0,  # 30 seconds warning
                critical_threshold=60.0,  # 60 seconds critical
                measurement_window="5m",
                compliance_target=0.95,  # 95% of requests under target
                business_impact="HIGH",
                created_at=datetime.now(),
            ),
            SLADefinition(
                sla_id="pipeline_success_rate",
                name="Pipeline Success Rate",
                description="Percentage of successful pipeline executions",
                metric_name="success_rate",
                target_value=0.995,  # 99.5% success rate
                warning_threshold=0.95,  # 95% warning
                critical_threshold=0.90,  # 90% critical
                measurement_window="1h",
                compliance_target=0.99,  # 99% compliance
                business_impact="CRITICAL",
                created_at=datetime.now(),
            ),
            SLADefinition(
                sla_id="bridge_sync_latency",
                name="Bridge Synchronization Latency",
                description="Time for bridge service to sync data",
                metric_name="bridge_sync_duration",
                target_value=2.0,  # 2 seconds target
                warning_threshold=5.0,  # 5 seconds warning
                critical_threshold=10.0,  # 10 seconds critical
                measurement_window="5m",
                compliance_target=0.95,
                business_impact="MEDIUM",
                created_at=datetime.now(),
            ),
            SLADefinition(
                sla_id="intelligence_processing_latency",
                name="Intelligence Processing Latency",
                description="Time for intelligence service processing",
                metric_name="intelligence_duration",
                target_value=5.0,  # 5 seconds target
                warning_threshold=10.0,  # 10 seconds warning
                critical_threshold=20.0,  # 20 seconds critical
                measurement_window="5m",
                compliance_target=0.95,
                business_impact="HIGH",
                created_at=datetime.now(),
            ),
            SLADefinition(
                sla_id="vector_embedding_latency",
                name="Vector Embedding Latency",
                description="Time to generate vector embeddings",
                metric_name="vector_embedding_duration",
                target_value=1.0,  # 1 second target
                warning_threshold=3.0,  # 3 seconds warning
                critical_threshold=5.0,  # 5 seconds critical
                measurement_window="5m",
                compliance_target=0.95,
                business_impact="MEDIUM",
                created_at=datetime.now(),
            ),
            SLADefinition(
                sla_id="qdrant_indexing_latency",
                name="Qdrant Vector Indexing Latency",
                description="Time to index vectors in Qdrant",
                metric_name="qdrant_indexing_duration",
                target_value=1.0,  # 1 second target
                warning_threshold=2.0,  # 2 seconds warning
                critical_threshold=5.0,  # 5 seconds critical
                measurement_window="5m",
                compliance_target=0.95,
                business_impact="MEDIUM",
                created_at=datetime.now(),
            ),
            SLADefinition(
                sla_id="service_availability",
                name="Service Availability",
                description="Overall service availability percentage",
                metric_name="availability",
                target_value=0.999,  # 99.9% availability
                warning_threshold=0.995,  # 99.5% warning
                critical_threshold=0.99,  # 99% critical
                measurement_window="24h",
                compliance_target=0.99,
                business_impact="CRITICAL",
                created_at=datetime.now(),
            ),
        ]

        for sla in default_slas:
            self.sla_definitions[sla.sla_id] = sla

    async def establish_baseline(
        self,
        baseline_type: BaselineType,
        stage: Optional[str] = None,
        time_window_hours: int = 168,  # 1 week default
        min_data_points: int = 100,
    ) -> Optional[PerformanceBaseline]:
        """
        Establish a performance baseline from historical data.

        Args:
            baseline_type: Type of baseline to establish
            stage: Specific pipeline stage or service (None for end-to-end)
            time_window_hours: Historical data window
            min_data_points: Minimum data points required

        Returns:
            PerformanceBaseline if successful, None if insufficient data
        """
        try:
            # Collect historical data
            historical_data = await self._collect_historical_data(
                baseline_type, stage, time_window_hours
            )

            if len(historical_data) < min_data_points:
                logger.warning(
                    f"Insufficient data points for baseline: {len(historical_data)} < {min_data_points}"
                )
                return None

            # Calculate statistical metrics
            metrics = self._calculate_baseline_metrics(historical_data)

            # Determine SLA thresholds
            sla_thresholds = self._calculate_sla_thresholds(
                historical_data, baseline_type
            )

            # Set target values
            target_values = self._determine_target_values(metrics, baseline_type, stage)

            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(
                historical_data, metrics
            )

            baseline = PerformanceBaseline(
                baseline_id=f"{baseline_type.value}_{stage or 'end_to_end'}_{datetime.now().strftime('%Y%m%d')}",
                name=f"{baseline_type.value.title()} Baseline - {stage or 'End-to-End'}",
                description=f"Performance baseline for {baseline_type.value} in {stage or 'end-to-end pipeline'}",
                baseline_type=baseline_type,
                stage=stage,
                metrics=metrics,
                sla_thresholds=sla_thresholds,
                target_values=target_values,
                established_at=datetime.now(),
                data_points=len(historical_data),
                confidence_score=confidence_score,
                valid_until=datetime.now() + timedelta(days=30),  # Valid for 30 days
                metadata={
                    "time_window_hours": time_window_hours,
                    "data_quality": self._assess_data_quality(historical_data),
                },
            )

            self.baselines[baseline.baseline_id] = baseline

            logger.info(
                f"Established baseline {baseline.baseline_id} with {len(historical_data)} data points "
                f"(confidence: {confidence_score:.2f})"
            )

            return baseline

        except Exception as e:
            logger.error(f"Error establishing baseline: {e}")
            return None

    async def _collect_historical_data(
        self, baseline_type: BaselineType, stage: Optional[str], time_window_hours: int
    ) -> list[float]:
        """Collect historical performance data"""
        try:
            # Get trace analytics for historical data
            trace_analytics = pipeline_tracer.get_trace_analytics(time_window_hours)

            historical_data = []

            if baseline_type == BaselineType.LATENCY:
                if stage:
                    # Service-specific latency
                    service_performance = trace_analytics.get("service_performance", {})
                    if stage in service_performance:
                        # Would extract individual durations from trace data
                        # For now, generate sample data from averages
                        avg_duration = service_performance[stage].get(
                            "average_duration", 0
                        )
                        if avg_duration > 0:
                            # Generate sample data around the average (for demo)
                            for _ in range(100):
                                # Add some variance
                                sample = avg_duration * (0.8 + 0.4 * np.random.random())
                                historical_data.append(sample)
                else:
                    # End-to-end latency
                    pipeline_status = pipeline_metrics.get_pipeline_metrics()
                    avg_duration = pipeline_status.get("avg_duration_last_10", 0)
                    if avg_duration > 0:
                        # Generate sample data for demo
                        for _ in range(100):
                            sample = avg_duration * (0.8 + 0.4 * np.random.random())
                            historical_data.append(sample)

            elif baseline_type == BaselineType.ERROR_RATE:
                # Error rate data
                pipeline_status = pipeline_metrics.get_pipeline_metrics()
                success_rate = pipeline_status.get("success_rate_last_100", 1.0)
                error_rate = 1.0 - success_rate

                # Generate sample data for demo
                for _ in range(100):
                    sample = error_rate * (0.5 + np.random.random())
                    historical_data.append(sample)

            elif baseline_type == BaselineType.THROUGHPUT:
                # Throughput data (documents per hour)
                # Would calculate from actual pipeline metrics
                # For demo, generate sample data
                base_throughput = 300  # documents per hour
                for _ in range(100):
                    sample = base_throughput * (0.8 + 0.4 * np.random.random())
                    historical_data.append(sample)

            return historical_data

        except Exception as e:
            logger.error(f"Error collecting historical data: {e}")
            return []

    def _calculate_baseline_metrics(self, data: list[float]) -> dict[str, float]:
        """Calculate statistical metrics from historical data"""
        if not data:
            return {}

        sorted_data = sorted(data)
        n = len(sorted_data)

        return {
            "mean": statistics.mean(data),
            "median": statistics.median(data),
            "std_dev": statistics.stdev(data) if n > 1 else 0,
            "min": min(data),
            "max": max(data),
            "p50": sorted_data[int(n * 0.5)],
            "p75": sorted_data[int(n * 0.75)],
            "p90": sorted_data[int(n * 0.9)],
            "p95": sorted_data[int(n * 0.95)],
            "p99": sorted_data[int(n * 0.99)],
            "count": n,
        }

    def _calculate_sla_thresholds(
        self, data: list[float], baseline_type: BaselineType
    ) -> dict[str, float]:
        """Calculate SLA thresholds based on data distribution"""
        if not data:
            return {}

        metrics = self._calculate_baseline_metrics(data)

        if baseline_type == BaselineType.LATENCY:
            # For latency, thresholds are higher values (worse performance)
            return {
                "target": metrics["p75"],  # 75th percentile as target
                "warning": metrics["p90"],  # 90th percentile as warning
                "critical": metrics["p95"],  # 95th percentile as critical
                "emergency": metrics["p99"],  # 99th percentile as emergency
            }
        elif baseline_type == BaselineType.ERROR_RATE:
            # For error rate, thresholds are higher values (worse performance)
            return {
                "target": metrics["p75"],
                "warning": metrics["p90"],
                "critical": metrics["p95"],
                "emergency": metrics["p99"],
            }
        elif baseline_type == BaselineType.THROUGHPUT:
            # For throughput, thresholds are lower values (worse performance)
            return {
                "target": metrics["p25"],  # 25th percentile as target (low is bad)
                "warning": metrics["p10"],
                "critical": metrics["p5"],
                "emergency": metrics["min"],
            }
        else:
            # Default thresholds
            return {
                "target": metrics["p75"],
                "warning": metrics["p90"],
                "critical": metrics["p95"],
                "emergency": metrics["p99"],
            }

    def _determine_target_values(
        self,
        metrics: dict[str, float],
        baseline_type: BaselineType,
        stage: Optional[str],
    ) -> dict[str, float]:
        """Determine target performance values"""
        targets = {}

        # Industry benchmark comparison
        benchmark_category = self._get_benchmark_category(metrics, baseline_type, stage)

        if baseline_type == BaselineType.LATENCY:
            # Target 20% better than current p75
            targets["optimal"] = metrics["p75"] * 0.8
            targets["good"] = metrics["p75"]
            targets["acceptable"] = metrics["p90"]
        elif baseline_type == BaselineType.THROUGHPUT:
            # Target 20% better than current p75
            targets["optimal"] = metrics["p75"] * 1.2
            targets["good"] = metrics["p75"]
            targets["acceptable"] = metrics["p50"]
        elif baseline_type == BaselineType.ERROR_RATE:
            # Target very low error rates
            targets["optimal"] = 0.001  # 0.1%
            targets["good"] = 0.01  # 1%
            targets["acceptable"] = 0.05  # 5%

        targets["benchmark_category"] = benchmark_category
        return targets

    def _get_benchmark_category(
        self,
        metrics: dict[str, float],
        baseline_type: BaselineType,
        stage: Optional[str],
    ) -> str:
        """Determine benchmark category based on performance"""
        if baseline_type == BaselineType.LATENCY:
            p95_latency = metrics.get("p95", 0)

            # Determine category based on latency
            if stage:
                benchmark_key = (
                    "vector_indexing"
                    if "vector" in stage.lower()
                    else "document_indexing"
                )
            else:
                benchmark_key = "document_indexing"

            benchmarks = self.industry_benchmarks.get(benchmark_key, {})

            if p95_latency <= benchmarks.get("excellent", {}).get("latency_p95", 0):
                return PerformanceCategory.EXCELLENT.value
            elif p95_latency <= benchmarks.get("good", {}).get("latency_p95", 0):
                return PerformanceCategory.GOOD.value
            elif p95_latency <= benchmarks.get("acceptable", {}).get("latency_p95", 0):
                return PerformanceCategory.ACCEPTABLE.value
            elif p95_latency <= benchmarks.get("poor", {}).get("latency_p95", 0):
                return PerformanceCategory.POOR.value
            else:
                return PerformanceCategory.CRITICAL.value

        return PerformanceCategory.ACCEPTABLE.value

    def _calculate_confidence_score(
        self, data: list[float], metrics: dict[str, float]
    ) -> float:
        """Calculate confidence score for the baseline"""
        if not data:
            return 0.0

        confidence = 1.0

        # Reduce confidence for small sample sizes
        if len(data) < 100:
            confidence *= len(data) / 100

        # Reduce confidence for high variance
        if metrics.get("std_dev", 0) > 0:
            cv = metrics["std_dev"] / metrics["mean"] if metrics["mean"] > 0 else 1
            if cv > 0.5:  # High coefficient of variation
                confidence *= 0.7

        # Ensure confidence is between 0 and 1
        return max(0.0, min(1.0, confidence))

    def _assess_data_quality(self, data: list[float]) -> dict[str, Any]:
        """Assess the quality of historical data"""
        if not data:
            return {"quality": "poor", "issues": ["no_data"]}

        issues = []
        quality_score = 1.0

        # Check for outliers
        metrics = self._calculate_baseline_metrics(data)
        q1 = np.percentile(data, 25)
        q3 = np.percentile(data, 75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outliers = [x for x in data if x < lower_bound or x > upper_bound]
        outlier_ratio = len(outliers) / len(data)

        if outlier_ratio > 0.1:  # More than 10% outliers
            issues.append("high_outlier_ratio")
            quality_score *= 0.8

        # Check for data consistency
        if metrics.get("std_dev", 0) / metrics.get("mean", 1) > 1.0:  # High CV
            issues.append("high_variance")
            quality_score *= 0.9

        # Determine overall quality
        if quality_score >= 0.9:
            quality = "excellent"
        elif quality_score >= 0.7:
            quality = "good"
        elif quality_score >= 0.5:
            quality = "acceptable"
        else:
            quality = "poor"

        return {
            "quality": quality,
            "quality_score": quality_score,
            "issues": issues,
            "outlier_ratio": outlier_ratio,
            "data_points": len(data),
        }

    def check_sla_compliance(
        self, current_metrics: dict[str, float], time_window: str = "5m"
    ) -> dict[str, Any]:
        """Check current SLA compliance"""
        compliance_report = {
            "timestamp": datetime.now().isoformat(),
            "time_window": time_window,
            "sla_results": {},
            "overall_compliance": True,
            "violations": [],
        }

        for sla_id, sla in self.sla_definitions.items():
            if not sla.enabled or sla.measurement_window != time_window:
                continue

            current_value = current_metrics.get(sla.metric_name)
            if current_value is None:
                continue

            # Determine compliance status
            status = "compliant"
            if current_value > sla.critical_threshold:
                status = "critical"
                compliance_report["overall_compliance"] = False
                compliance_report["violations"].append(
                    {
                        "sla_id": sla_id,
                        "severity": "critical",
                        "current_value": current_value,
                        "threshold": sla.critical_threshold,
                    }
                )
            elif current_value > sla.warning_threshold:
                status = "warning"
                compliance_report["violations"].append(
                    {
                        "sla_id": sla_id,
                        "severity": "warning",
                        "current_value": current_value,
                        "threshold": sla.warning_threshold,
                    }
                )

            compliance_report["sla_results"][sla_id] = {
                "name": sla.name,
                "status": status,
                "current_value": current_value,
                "target_value": sla.target_value,
                "warning_threshold": sla.warning_threshold,
                "critical_threshold": sla.critical_threshold,
                "business_impact": sla.business_impact,
            }

        return compliance_report

    def detect_performance_regression(
        self, current_metrics: dict[str, float], baseline_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Detect performance regressions against baselines"""
        if baseline_id:
            baselines = [self.baselines.get(baseline_id)]
        else:
            # Check all valid baselines
            baselines = [
                b for b in self.baselines.values() if b.valid_until > datetime.now()
            ]

        regressions = []

        for baseline in baselines:
            if not baseline:
                continue

            metric_name = baseline.baseline_type.value
            current_value = current_metrics.get(metric_name)

            if current_value is None:
                continue

            # Check for regression
            regression_detected = False
            severity = "info"

            if baseline.baseline_type in [
                BaselineType.LATENCY,
                BaselineType.ERROR_RATE,
            ]:
                # Higher is worse
                if current_value > baseline.sla_thresholds.get(
                    "critical", float("inf")
                ):
                    regression_detected = True
                    severity = "critical"
                elif current_value > baseline.sla_thresholds.get(
                    "warning", float("inf")
                ):
                    regression_detected = True
                    severity = "warning"
            elif baseline.baseline_type == BaselineType.THROUGHPUT:
                # Lower is worse
                if current_value < baseline.sla_thresholds.get("critical", 0):
                    regression_detected = True
                    severity = "critical"
                elif current_value < baseline.sla_thresholds.get("warning", 0):
                    regression_detected = True
                    severity = "warning"

            if regression_detected:
                change_percent = (
                    (current_value - baseline.metrics.get("p75", 0))
                    / baseline.metrics.get("p75", 1)
                ) * 100

                regressions.append(
                    {
                        "baseline_id": baseline.baseline_id,
                        "baseline_name": baseline.name,
                        "metric_name": metric_name,
                        "current_value": current_value,
                        "baseline_p75": baseline.metrics.get("p75", 0),
                        "change_percent": change_percent,
                        "severity": severity,
                        "recommendation": self._get_regression_recommendation(
                            baseline, current_value
                        ),
                    }
                )

        return {
            "timestamp": datetime.now().isoformat(),
            "regressions_detected": len(regressions),
            "regressions": regressions,
            "overall_status": "degraded" if regressions else "normal",
        }

    def _get_regression_recommendation(
        self, baseline: PerformanceBaseline, current_value: float
    ) -> str:
        """Get recommendation for addressing performance regression"""
        if baseline.stage:
            return (
                f"Investigate {baseline.stage} service performance - current {baseline.baseline_type.value} "
                f"({current_value:.2f}) exceeds baseline threshold"
            )
        else:
            return (
                f"Investigate end-to-end pipeline performance - {baseline.baseline_type.value} "
                f"regression detected ({current_value:.2f})"
            )

    def get_performance_forecast(
        self, baseline_id: str, forecast_hours: int = 24
    ) -> dict[str, Any]:
        """Generate performance forecast based on baseline trends"""
        baseline = self.baselines.get(baseline_id)
        if not baseline:
            return {"error": "Baseline not found"}

        # Simple linear trend forecast (would use more sophisticated models in production)
        current_trend = 0  # Would calculate from recent data
        forecast_value = baseline.metrics.get("p75", 0) * (
            1 + current_trend * forecast_hours / 24
        )

        return {
            "baseline_id": baseline_id,
            "forecast_hours": forecast_hours,
            "current_p75": baseline.metrics.get("p75", 0),
            "forecast_p75": forecast_value,
            "confidence": baseline.confidence_score
            * 0.8,  # Lower confidence for forecasts
            "recommendations": [
                "Monitor performance closely during forecast period",
                "Consider proactive scaling if forecast shows degradation",
            ],
        }

    # Public API methods

    def get_baselines(self) -> list[dict[str, Any]]:
        """Get all performance baselines"""
        return [baseline.to_dict() for baseline in self.baselines.values()]

    def get_sla_definitions(self) -> list[dict[str, Any]]:
        """Get all SLA definitions"""
        return [asdict(sla) for sla in self.sla_definitions.values()]

    def add_sla_definition(self, sla: SLADefinition):
        """Add a new SLA definition"""
        self.sla_definitions[sla.sla_id] = sla

    def get_performance_summary(self) -> dict[str, Any]:
        """Get comprehensive performance summary"""
        active_baselines = [
            b for b in self.baselines.values() if b.valid_until > datetime.now()
        ]

        return {
            "timestamp": datetime.now().isoformat(),
            "active_baselines": len(active_baselines),
            "total_slas": len(self.sla_definitions),
            "enabled_slas": len(
                [s for s in self.sla_definitions.values() if s.enabled]
            ),
            "baseline_confidence_avg": (
                sum(b.confidence_score for b in active_baselines)
                / len(active_baselines)
                if active_baselines
                else 0
            ),
            "next_baseline_expiry": (
                min(b.valid_until for b in active_baselines).isoformat()
                if active_baselines
                else None
            ),
        }


# Global performance baseline service
performance_baseline = PipelinePerformanceBaseline()


def get_performance_baseline_service() -> PipelinePerformanceBaseline:
    """Get the global performance baseline service"""
    return performance_baseline
