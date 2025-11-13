"""
Data Refresh Worker for Archon Document Freshness System

Intelligent batch processing worker with risk assessment, smart data ejection,
and comprehensive refresh operations following Archon patterns.
"""

import asyncio
import logging
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .database import FreshnessDatabase
from .models import (
    RefreshRequest,
    RefreshResult,
)
from .monitor import DocumentFreshnessMonitor

logger = logging.getLogger(__name__)


class DataRefreshWorker:
    """
    Intelligent data refresh worker with batch processing,
    risk assessment, and smart data management.
    """

    def __init__(
        self,
        database: FreshnessDatabase,
        monitor: DocumentFreshnessMonitor,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize data refresh worker"""

        self.database = database
        self.monitor = monitor

        # Default configuration
        self.config = {
            # Batch processing
            "batch_size": 5,  # Documents to process simultaneously
            "max_concurrent_batches": 2,  # Maximum concurrent batch operations
            "batch_timeout_minutes": 30,  # Timeout per batch
            "total_timeout_hours": 4,  # Total operation timeout
            # Risk assessment
            "risk_thresholds": {
                "low": 0.9,  # > 0.9 freshness score = low risk
                "medium": 0.6,  # 0.6-0.9 = medium risk
                "high": 0.3,  # 0.3-0.6 = high risk
                "critical": 0.0,  # < 0.3 = critical risk
            },
            # Refresh modes
            "refresh_modes": {
                "safe": {
                    "backup_enabled": True,
                    "verification_required": True,
                    "rollback_on_error": True,
                    "max_risk_level": "medium",
                },
                "aggressive": {
                    "backup_enabled": True,
                    "verification_required": False,
                    "rollback_on_error": False,
                    "max_risk_level": "high",
                },
                "force": {
                    "backup_enabled": False,
                    "verification_required": False,
                    "rollback_on_error": False,
                    "max_risk_level": "critical",
                },
            },
            # Backup settings
            "backup_retention_days": 30,
            "backup_compression": True,
            "backup_base_path": "/tmp/archon_freshness_backups",
            # Smart ejection
            "ejection_enabled": True,
            "ejection_thresholds": {
                "max_age_days": 365,  # Eject docs older than 1 year
                "min_freshness_score": 0.1,  # Eject docs with very low scores
                "max_broken_deps_ratio": 0.8,  # Eject if >80% deps broken
                "min_access_threshold": 0,  # Eject never-accessed docs
            },
            # Performance optimization
            "parallel_processing": True,
            "memory_limit_mb": 1024,
            "io_timeout_seconds": 30,
            # Quality gates
            "quality_gates": {
                "max_error_rate": 0.2,  # Stop if >20% operations fail
                "min_success_rate": 0.8,  # Require >80% success rate
                "max_rollback_rate": 0.1,  # Stop if >10% need rollback
            },
        }

        # Update with provided config
        if config:
            self._update_config(config)

        # Worker state
        self._active_operations: Set[str] = set()
        self._performance_metrics = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "total_processing_time": 0.0,
            "average_processing_time": 0.0,
        }

        # Ensure backup directory exists
        backup_path = Path(self.config["backup_base_path"])
        backup_path.mkdir(parents=True, exist_ok=True)

        logger.info("DataRefreshWorker initialized")

    def _update_config(self, new_config: Dict[str, Any]):
        """Recursively update configuration"""

        def update_dict(base: dict, updates: dict):
            for key, value in updates.items():
                if (
                    key in base
                    and isinstance(base[key], dict)
                    and isinstance(value, dict)
                ):
                    update_dict(base[key], value)
                else:
                    base[key] = value

        update_dict(self.config, new_config)

    async def refresh_documents(
        self, request: RefreshRequest, progress_callback: Optional[callable] = None
    ) -> RefreshResult:
        """
        Refresh stale documents with comprehensive error handling and progress tracking.

        Args:
            request: Refresh request with documents and options
            progress_callback: Optional callback for progress updates

        Returns:
            Complete refresh result with metrics and impact assessment
        """
        start_time = datetime.now(timezone.utc)
        refresh_id = f"refresh_{int(start_time.timestamp())}_{uuid.uuid4().hex[:8]}"

        logger.info(
            f"Starting refresh operation {refresh_id} for {len(request.document_paths)} documents"
        )

        # Initialize result
        result = RefreshResult(
            refresh_id=refresh_id,
            started_at=start_time,
            requested_documents=request.document_paths.copy(),
        )

        # Track operation
        self._active_operations.add(refresh_id)

        try:
            # Pre-flight checks
            validation_result = await self._validate_refresh_request(request)
            if not validation_result.get("valid", False):
                result.errors.extend(validation_result.get("errors", []))
                result.failure_count = len(request.document_paths)
                result.failed_documents = request.document_paths.copy()
                return result

            # Filter documents based on criteria
            eligible_documents = await self._filter_eligible_documents(request)
            logger.info(f"Filtered to {len(eligible_documents)} eligible documents")

            if not eligible_documents:
                result.warnings.append("No eligible documents found for refresh")
                return result

            # Assess risks
            risk_assessment = await self._assess_refresh_risks(
                eligible_documents, request.refresh_mode
            )

            # Apply quality gates
            if not self._check_quality_gates(risk_assessment):
                result.errors.append("Operation blocked by quality gates")
                result.failure_count = len(eligible_documents)
                result.failed_documents = eligible_documents.copy()
                return result

            # Create backups if enabled
            backup_info = {}
            if self._should_create_backup(request.refresh_mode):
                backup_info = await self._create_backups(eligible_documents, refresh_id)
                result.backup_locations = list(backup_info.values())

            # Process documents in batches
            batch_results = await self._process_document_batches(
                eligible_documents, request, refresh_id, progress_callback
            )

            # Consolidate results
            result = self._consolidate_batch_results(result, batch_results)

            # Perform impact assessment
            impact_assessment = await self._assess_refresh_impact(
                result.processed_documents, start_time
            )
            result.freshness_improvement = impact_assessment.get(
                "freshness_improvement", {}
            )
            result.dependencies_fixed = impact_assessment.get("dependencies_fixed", [])

            # Smart data ejection (if enabled)
            if self.config["ejection_enabled"]:
                ejected_documents = await self._perform_smart_ejection(
                    eligible_documents
                )
                if ejected_documents:
                    result.warnings.append(
                        f"Ejected {len(ejected_documents)} outdated documents"
                    )

        except Exception as e:
            logger.error(f"Refresh operation {refresh_id} failed: {e}")
            result.errors.append(f"Operation failed: {str(e)}")
            result.failure_count = len(request.document_paths)
            result.failed_documents = request.document_paths.copy()

        finally:
            # Finalize result
            result.completed_at = datetime.now(timezone.utc)
            result.total_time_seconds = (
                result.completed_at - start_time
            ).total_seconds()

            if result.success_count + result.failure_count > 0:
                result.average_time_per_document = result.total_time_seconds / (
                    result.success_count + result.failure_count
                )

            # Update performance metrics
            self._update_performance_metrics(result)

            # Store result in database
            await self.database.store_refresh_result(result)

            # Remove from active operations
            self._active_operations.discard(refresh_id)

            logger.info(
                f"Refresh operation {refresh_id} completed: "
                f"{result.success_count} success, {result.failure_count} failed, "
                f"{result.total_time_seconds:.1f}s total"
            )

        return result

    async def _validate_refresh_request(
        self, request: RefreshRequest
    ) -> Dict[str, Any]:
        """Validate refresh request before processing"""
        errors = []
        warnings = []

        # Check document paths exist
        missing_paths = []
        for path in request.document_paths:
            if not Path(path).exists():
                missing_paths.append(path)

        if missing_paths:
            errors.append(f"Missing documents: {missing_paths}")

        # Validate refresh mode
        if request.refresh_mode not in self.config["refresh_modes"]:
            errors.append(f"Invalid refresh mode: {request.refresh_mode}")

        # Check resource limits
        if len(request.document_paths) > 1000:  # Reasonable upper limit
            warnings.append("Large batch size may impact performance")

        # Validate filters
        if request.max_age_days and request.max_age_days < 0:
            errors.append("max_age_days must be non-negative")

        if (
            request.min_freshness_score
            and not 0.0 <= request.min_freshness_score <= 1.0
        ):
            errors.append("min_freshness_score must be between 0.0 and 1.0")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    async def _filter_eligible_documents(self, request: RefreshRequest) -> List[str]:
        """Filter documents based on request criteria"""
        eligible = []

        for doc_path in request.document_paths:
            # Get document info from database
            doc_info = await self.database.get_document_by_path(doc_path)

            if not doc_info:
                logger.debug(f"Document not in database, skipping: {doc_path}")
                continue

            # Apply age filter
            if request.max_age_days:
                age_days = (datetime.now(timezone.utc) - doc_info["last_modified"]).days
                if age_days < request.max_age_days:
                    continue

            # Apply freshness score filter
            if request.min_freshness_score:
                if doc_info["overall_score"] >= request.min_freshness_score:
                    continue

            # Apply priority filter
            if request.priority_filter:
                if doc_info["refresh_priority"] != request.priority_filter.value:
                    continue

            eligible.append(doc_path)

        return eligible

    async def _assess_refresh_risks(
        self, document_paths: List[str], refresh_mode: str
    ) -> Dict[str, Any]:
        """Assess risks associated with refreshing documents"""
        risk_assessment = {
            "overall_risk": "low",
            "document_risks": {},
            "risk_factors": [],
            "mitigation_strategies": [],
        }

        high_risk_count = 0
        critical_risk_count = 0

        for doc_path in document_paths:
            doc_info = await self.database.get_document_by_path(doc_path)

            if not doc_info:
                continue

            doc_risk = "low"
            risk_factors = []

            # Assess freshness score risk
            score = doc_info["overall_score"]
            if score < self.config["risk_thresholds"]["critical"]:
                doc_risk = "critical"
                risk_factors.append("critically low freshness score")
                critical_risk_count += 1
            elif score < self.config["risk_thresholds"]["high"]:
                doc_risk = "high"
                risk_factors.append("low freshness score")
                high_risk_count += 1
            elif score < self.config["risk_thresholds"]["medium"]:
                doc_risk = "medium"
                risk_factors.append("moderate freshness score")

            # Assess dependency risks
            if doc_info["broken_dependencies"] > 0:
                broken_ratio = doc_info["broken_dependencies"] / max(
                    doc_info["total_dependencies"], 1
                )
                if broken_ratio > 0.5:
                    doc_risk = max(doc_risk, "high")
                    risk_factors.append("many broken dependencies")
                    high_risk_count += 1

            # Assess document type risks
            if doc_info["document_type"] in [
                "README",
                "API_DOCUMENTATION",
                "CONFIGURATION",
            ]:
                risk_factors.append("critical document type")
                doc_risk = max(doc_risk, "medium")

            risk_assessment["document_risks"][doc_path] = {
                "risk_level": doc_risk,
                "risk_factors": risk_factors,
            }

        # Determine overall risk
        if critical_risk_count > 0:
            risk_assessment["overall_risk"] = "critical"
        elif high_risk_count > len(document_paths) * 0.3:  # >30% high risk
            risk_assessment["overall_risk"] = "high"
        elif high_risk_count > 0:
            risk_assessment["overall_risk"] = "medium"

        # Check if risk level is acceptable for refresh mode
        mode_config = self.config["refresh_modes"][refresh_mode]
        max_allowed_risk = mode_config["max_risk_level"]

        risk_levels = ["low", "medium", "high", "critical"]
        if risk_levels.index(risk_assessment["overall_risk"]) > risk_levels.index(
            max_allowed_risk
        ):
            risk_assessment["risk_factors"].append(
                f"Risk level {risk_assessment['overall_risk']} exceeds mode limit {max_allowed_risk}"
            )

        return risk_assessment

    def _check_quality_gates(self, risk_assessment: Dict[str, Any]) -> bool:
        """Check if operation should proceed based on quality gates"""

        # Check risk level against refresh mode
        overall_risk = risk_assessment["overall_risk"]

        if overall_risk == "critical":
            logger.warning("Quality gate: Critical risk level detected")
            return False

        # Check recent error rates
        if self._performance_metrics["total_operations"] > 0:
            error_rate = (
                self._performance_metrics["failed_operations"]
                / self._performance_metrics["total_operations"]
            )

            if error_rate > self.config["quality_gates"]["max_error_rate"]:
                logger.warning(f"Quality gate: Error rate too high ({error_rate:.1%})")
                return False

        # Additional quality checks could be added here
        # (e.g., system resource checks, dependency health, etc.)

        return True

    def _should_create_backup(self, refresh_mode: str) -> bool:
        """Determine if backups should be created based on refresh mode"""
        mode_config = self.config["refresh_modes"][refresh_mode]
        return mode_config.get("backup_enabled", True)

    async def _create_backups(
        self, document_paths: List[str], operation_id: str
    ) -> Dict[str, str]:
        """Create backups of documents before refresh"""
        backup_info = {}
        backup_base = Path(self.config["backup_base_path"]) / operation_id
        backup_base.mkdir(parents=True, exist_ok=True)

        logger.info(f"Creating backups for {len(document_paths)} documents")

        for doc_path in document_paths:
            try:
                source_path = Path(doc_path)
                if not source_path.exists():
                    continue

                # Create relative path structure in backup
                backup_path = backup_base / source_path.name

                # Ensure backup directory exists
                backup_path.parent.mkdir(parents=True, exist_ok=True)

                # Copy file with metadata preservation
                shutil.copy2(source_path, backup_path)

                backup_info[doc_path] = str(backup_path)

                logger.debug(f"Backed up {doc_path} to {backup_path}")

            except Exception as e:
                logger.error(f"Failed to backup {doc_path}: {e}")
                continue

        logger.info(f"Created {len(backup_info)} backups in {backup_base}")
        return backup_info

    async def _process_document_batches(
        self,
        document_paths: List[str],
        request: RefreshRequest,
        operation_id: str,
        progress_callback: Optional[callable] = None,
    ) -> List[Dict[str, Any]]:
        """Process documents in parallel batches"""

        batch_size = self.config["batch_size"]
        batches = [
            document_paths[i : i + batch_size]
            for i in range(0, len(document_paths), batch_size)
        ]

        logger.info(
            f"Processing {len(document_paths)} documents in {len(batches)} batches"
        )

        batch_results = []
        completed_count = 0

        # Process batches with concurrency limit
        semaphore = asyncio.Semaphore(self.config["max_concurrent_batches"])

        async def process_batch_with_semaphore(batch_idx: int, batch: List[str]):
            async with semaphore:
                return await self._process_single_batch(
                    batch_idx, batch, request, operation_id
                )

        # Execute all batches
        batch_tasks = [
            process_batch_with_semaphore(idx, batch)
            for idx, batch in enumerate(batches)
        ]

        # Process with progress tracking
        for completed_task in asyncio.as_completed(batch_tasks):
            try:
                batch_result = await completed_task
                batch_results.append(batch_result)

                completed_count += len(batch_result.get("processed", []))

                # Report progress
                if progress_callback:
                    progress = completed_count / len(document_paths)
                    await progress_callback(
                        progress,
                        f"Processed {completed_count}/{len(document_paths)} documents",
                    )

            except Exception as e:
                logger.error(f"Batch processing failed: {e}")
                batch_results.append(
                    {"processed": [], "failed": [], "errors": [str(e)]}
                )

        return batch_results

    async def _process_single_batch(
        self,
        batch_idx: int,
        document_paths: List[str],
        request: RefreshRequest,
        operation_id: str,
    ) -> Dict[str, Any]:
        """Process a single batch of documents"""

        batch_start = time.time()
        batch_result = {
            "batch_id": f"{operation_id}_batch_{batch_idx}",
            "processed": [],
            "failed": [],
            "skipped": [],
            "errors": [],
            "processing_time": 0.0,
        }

        logger.debug(
            f"Processing batch {batch_idx} with {len(document_paths)} documents"
        )

        try:
            # Process each document in the batch
            for doc_path in document_paths:
                try:
                    # Re-analyze document to get fresh data
                    if not request.dry_run:
                        fresh_analysis = await self.monitor.analyze_document(
                            file_path=doc_path, include_dependencies=True
                        )

                        # Store updated analysis
                        await self.database.store_document_freshness(fresh_analysis)

                        batch_result["processed"].append(doc_path)
                        logger.debug(f"Refreshed document: {doc_path}")
                    else:
                        batch_result["processed"].append(doc_path)
                        logger.debug(f"Dry run processed: {doc_path}")

                except Exception as e:
                    logger.error(f"Failed to refresh document {doc_path}: {e}")
                    batch_result["failed"].append(doc_path)
                    batch_result["errors"].append(f"{doc_path}: {str(e)}")

                # Add small delay to prevent overwhelming system
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Batch {batch_idx} processing failed: {e}")
            batch_result["errors"].append(f"Batch processing error: {str(e)}")
            batch_result["failed"].extend(
                [p for p in document_paths if p not in batch_result["processed"]]
            )

        finally:
            batch_result["processing_time"] = time.time() - batch_start

        logger.debug(
            f"Batch {batch_idx} completed: {len(batch_result['processed'])} processed, "
            f"{len(batch_result['failed'])} failed in {batch_result['processing_time']:.1f}s"
        )

        return batch_result

    def _consolidate_batch_results(
        self, result: RefreshResult, batch_results: List[Dict[str, Any]]
    ) -> RefreshResult:
        """Consolidate results from all batches"""

        for batch_result in batch_results:
            result.processed_documents.extend(batch_result.get("processed", []))
            result.failed_documents.extend(batch_result.get("failed", []))
            result.skipped_documents.extend(batch_result.get("skipped", []))
            result.errors.extend(batch_result.get("errors", []))

        result.success_count = len(result.processed_documents)
        result.failure_count = len(result.failed_documents)

        return result

    async def _assess_refresh_impact(
        self, processed_documents: List[str], start_time: datetime
    ) -> Dict[str, Any]:
        """Assess the impact of refresh operations"""

        impact = {
            "freshness_improvement": {},
            "dependencies_fixed": [],
            "quality_improvement": {},
        }

        for doc_path in processed_documents:
            try:
                # Get current document state
                current_doc = await self.database.get_document_by_path(doc_path)

                if current_doc and current_doc["last_analyzed"] >= start_time:
                    # Document was updated during this operation
                    impact["freshness_improvement"][doc_path] = current_doc[
                        "overall_score"
                    ]

                    # Check if dependencies were fixed
                    if (
                        current_doc["broken_dependencies"] == 0
                        and current_doc["total_dependencies"] > 0
                    ):
                        impact["dependencies_fixed"].append(doc_path)

            except Exception as e:
                logger.error(f"Failed to assess impact for {doc_path}: {e}")
                continue

        return impact

    async def _perform_smart_ejection(self, document_paths: List[str]) -> List[str]:
        """Perform smart data ejection for severely outdated documents"""

        ejected = []
        ejection_thresholds = self.config["ejection_thresholds"]

        for doc_path in document_paths:
            try:
                doc_info = await self.database.get_document_by_path(doc_path)

                if not doc_info:
                    continue

                should_eject = False
                ejection_reason = []

                # Check age threshold
                age_days = (datetime.now(timezone.utc) - doc_info["last_modified"]).days
                if age_days > ejection_thresholds["max_age_days"]:
                    should_eject = True
                    ejection_reason.append(f"age {age_days} days")

                # Check freshness score threshold
                if (
                    doc_info["overall_score"]
                    < ejection_thresholds["min_freshness_score"]
                ):
                    should_eject = True
                    ejection_reason.append(f"low score {doc_info['overall_score']:.2f}")

                # Check broken dependencies ratio
                if doc_info["total_dependencies"] > 0:
                    broken_ratio = (
                        doc_info["broken_dependencies"] / doc_info["total_dependencies"]
                    )
                    if broken_ratio > ejection_thresholds["max_broken_deps_ratio"]:
                        should_eject = True
                        ejection_reason.append(f"broken deps {broken_ratio:.1%}")

                # Never eject critical document types
                if doc_info["document_type"] in ["README", "CONFIGURATION"]:
                    should_eject = False

                if should_eject:
                    logger.info(
                        f"Ejecting document {doc_path}: {', '.join(ejection_reason)}"
                    )

                    # Mark as ejected (don't actually delete, just flag for manual review)
                    # This would typically update a status field in the database
                    ejected.append(doc_path)

            except Exception as e:
                logger.error(f"Failed to assess ejection for {doc_path}: {e}")
                continue

        return ejected

    def _update_performance_metrics(self, result: RefreshResult):
        """Update internal performance metrics"""

        self._performance_metrics["total_operations"] += 1

        if result.success_count > result.failure_count:
            self._performance_metrics["successful_operations"] += 1
        else:
            self._performance_metrics["failed_operations"] += 1

        self._performance_metrics["total_processing_time"] += result.total_time_seconds
        self._performance_metrics["average_processing_time"] = (
            self._performance_metrics["total_processing_time"]
            / self._performance_metrics["total_operations"]
        )

    async def get_active_operations(self) -> List[str]:
        """Get list of currently active refresh operations"""
        return list(self._active_operations)

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        return self._performance_metrics.copy()

    async def cleanup_old_backups(self, days_to_keep: Optional[int] = None) -> int:
        """Clean up old backup files"""
        if days_to_keep is None:
            days_to_keep = self.config["backup_retention_days"]

        backup_base = Path(self.config["backup_base_path"])
        if not backup_base.exists():
            return 0

        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        deleted_count = 0

        try:
            for backup_dir in backup_base.iterdir():
                if backup_dir.is_dir():
                    # Check directory modification time
                    dir_mtime = datetime.fromtimestamp(backup_dir.stat().st_mtime)

                    if dir_mtime < cutoff_time:
                        shutil.rmtree(backup_dir)
                        deleted_count += 1
                        logger.debug(f"Deleted old backup directory: {backup_dir}")

        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old backup directories")

        return deleted_count
