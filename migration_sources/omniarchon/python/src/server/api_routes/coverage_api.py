"""Coverage report API endpoints for serving test coverage data."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/coverage", tags=["coverage"])


@router.get("/debug/paths")
async def debug_paths() -> dict[str, Any]:
    """Debug endpoint to check coverage report paths"""
    return {
        "environment": "docker" if Path("/app").exists() else "local",
        "pytest_coverage_path": str(PYTEST_COVERAGE_PATH),
        "pytest_coverage_exists": PYTEST_COVERAGE_PATH.exists(),
        "pytest_json_exists": (PYTEST_COVERAGE_PATH / "coverage.json").exists(),
        "pytest_html_exists": (PYTEST_COVERAGE_PATH / "htmlcov").exists(),
        "vitest_coverage_path": str(VITEST_COVERAGE_PATH),
        "vitest_coverage_exists": VITEST_COVERAGE_PATH.exists(),
        "vitest_summary_exists": (
            VITEST_COVERAGE_PATH / "coverage-summary.json"
        ).exists(),
        "vitest_final_exists": (VITEST_COVERAGE_PATH / "coverage-final.json").exists(),
    }


# Base paths for coverage reports
# Check if we're running in Docker (coverage reports in /app)
if Path("/app").exists():
    # Docker environment - coverage reports are in /app/coverage_reports/
    PYTEST_COVERAGE_PATH = Path("/app/coverage_reports/pytest")
    VITEST_COVERAGE_PATH = Path("/app/coverage_reports/vitest")
else:
    # Local development - relative to Python directory
    PYTHON_BASE_PATH = Path(
        __file__
    ).parent.parent.parent.parent  # Navigate to python/ directory
    PYTEST_COVERAGE_PATH = PYTHON_BASE_PATH / "coverage_reports" / "pytest"

    # Frontend coverage reports are in archon-ui-main
    UI_BASE_PATH = PYTHON_BASE_PATH.parent / "archon-ui-main"
    VITEST_COVERAGE_PATH = UI_BASE_PATH / "public" / "test-results" / "coverage"


@router.get("/pytest/json")
async def get_pytest_coverage_json() -> dict[str, Any]:
    """Get pytest coverage data as JSON"""
    coverage_file = PYTEST_COVERAGE_PATH / "coverage.json"
    if not coverage_file.exists():
        raise HTTPException(status_code=404, detail="Coverage data not found")

    with open(coverage_file) as f:
        return json.load(f)


@router.get("/pytest/html/{path:path}")
async def get_pytest_coverage_html(path: str) -> FileResponse:
    """Serve pytest HTML coverage report files"""
    file_path = PYTEST_COVERAGE_PATH / "htmlcov" / path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Determine content type based on file extension
    content_type = "text/html"
    if path.endswith(".css"):
        content_type = "text/css"
    elif path.endswith(".js"):
        content_type = "application/javascript"
    elif path.endswith(".png"):
        content_type = "image/png"

    return FileResponse(file_path, media_type=content_type)


@router.get("/vitest/json")
async def get_vitest_coverage_json() -> dict[str, Any]:
    """Get vitest coverage data as JSON"""
    coverage_file = VITEST_COVERAGE_PATH / "coverage-final.json"
    if not coverage_file.exists():
        raise HTTPException(status_code=404, detail="Coverage data not found")

    with open(coverage_file) as f:
        return json.load(f)


@router.get("/vitest/summary")
async def get_vitest_coverage_summary() -> dict[str, Any]:
    """Get vitest coverage summary"""
    summary_file = VITEST_COVERAGE_PATH / "coverage-summary.json"
    if not summary_file.exists():
        raise HTTPException(status_code=404, detail="Coverage summary not found")

    with open(summary_file) as f:
        return json.load(f)


@router.get("/vitest/html/{path:path}")
async def get_vitest_coverage_html(path: str) -> FileResponse:
    """Serve vitest HTML coverage report files"""
    file_path = VITEST_COVERAGE_PATH / path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Determine content type based on file extension
    content_type = "text/html"
    if path.endswith(".css"):
        content_type = "text/css"
    elif path.endswith(".js"):
        content_type = "application/javascript"
    elif path.endswith(".png"):
        content_type = "image/png"

    return FileResponse(file_path, media_type=content_type)


@router.get("/combined-summary")
async def get_combined_coverage_summary() -> dict[str, Any]:
    """Get combined coverage summary from all test suites"""
    combined_summary = {
        "backend": None,
        "frontend": None,
        "timestamp": datetime.now().isoformat(),
        "total": {
            "lines": {"pct": 0, "total": 0, "covered": 0, "skipped": 0},
            "statements": {"pct": 0, "total": 0, "covered": 0, "skipped": 0},
            "functions": {"pct": 0, "total": 0, "covered": 0, "skipped": 0},
            "branches": {"pct": 0, "total": 0, "covered": 0, "skipped": 0},
        },
    }

    # Try to get pytest coverage
    pytest_available = False
    try:
        if (
            PYTEST_COVERAGE_PATH.exists()
            and (PYTEST_COVERAGE_PATH / "coverage.json").exists()
        ):
            pytest_cov = await get_pytest_coverage_json()
            combined_summary["backend"] = {
                "summary": pytest_cov.get("totals", {}),
                "files": len(pytest_cov.get("files", {})),
            }
            pytest_available = True
    except Exception:
        # If pytest coverage doesn't exist, that's fine
        combined_summary["backend"] = {
            "summary": {},
            "files": 0,
            "message": "No pytest coverage data available",
        }

    # Try to get vitest coverage
    vitest_available = False
    try:
        vitest_cov = await get_vitest_coverage_summary()
        combined_summary["frontend"] = vitest_cov
        vitest_available = True
    except Exception:
        combined_summary["frontend"] = {
            "total": {},
            "message": "No vitest coverage data available",
        }

    # Calculate combined totals if any coverage is available
    if vitest_available:
        # For now, if only frontend is available, use its values
        frontend_summary = combined_summary["frontend"].get("total", {})
        for metric in ["lines", "statements", "functions", "branches"]:
            if metric in frontend_summary:
                combined_summary["total"][metric] = frontend_summary[metric]

    if pytest_available and vitest_available:
        # If both are available, calculate weighted average
        backend_summary = combined_summary["backend"].get("summary", {})
        frontend_summary = combined_summary["frontend"].get("total", {})

        # Combine metrics
        for metric in ["lines", "statements", "functions", "branches"]:
            backend_metric = backend_summary.get(f"percent_{metric}", 0)
            frontend_metric = frontend_summary.get(metric, {}).get("pct", 0)

            # Simple average for now (could be weighted by file count)
            combined_summary["total"][metric]["pct"] = (
                backend_metric + frontend_metric
            ) / 2

    return combined_summary
