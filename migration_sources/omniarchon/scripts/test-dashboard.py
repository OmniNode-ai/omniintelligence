#!/usr/bin/env python3
"""
Archon MCP Integration Test Dashboard

A comprehensive web dashboard for viewing test results, metrics, and trends.
Provides real-time monitoring of test execution and historical analysis.
"""

import asyncio
import json
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import click
import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
RESULTS_DIR = PROJECT_ROOT / "test-results"
DB_PATH = RESULTS_DIR / "test-history.db"
DASHBOARD_PORT = 8080


class TestResultsDB:
    """Database manager for test results and history"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize the database with required tables"""
        RESULTS_DIR.mkdir(exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS test_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    test_suite TEXT NOT NULL,
                    status TEXT NOT NULL,
                    total_tests INTEGER DEFAULT 0,
                    passed_tests INTEGER DEFAULT 0,
                    failed_tests INTEGER DEFAULT 0,
                    skipped_tests INTEGER DEFAULT 0,
                    duration_seconds REAL DEFAULT 0,
                    coverage_percent REAL DEFAULT 0,
                    commit_hash TEXT,
                    branch TEXT,
                    trigger_type TEXT DEFAULT 'manual',
                    artifacts_path TEXT
                );

                CREATE TABLE IF NOT EXISTS test_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    name TEXT NOT NULL,
                    classname TEXT,
                    status TEXT NOT NULL,
                    duration_seconds REAL DEFAULT 0,
                    error_message TEXT,
                    failure_message TEXT,
                    FOREIGN KEY (run_id) REFERENCES test_runs (id)
                );

                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    metric_unit TEXT,
                    benchmark_name TEXT,
                    FOREIGN KEY (run_id) REFERENCES test_runs (id)
                );

                CREATE TABLE IF NOT EXISTS service_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    service_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_time_ms REAL,
                    error_message TEXT,
                    FOREIGN KEY (run_id) REFERENCES test_runs (id)
                );

                CREATE INDEX IF NOT EXISTS idx_test_runs_timestamp ON test_runs(timestamp);
                CREATE INDEX IF NOT EXISTS idx_test_cases_run_id ON test_cases(run_id);
                CREATE INDEX IF NOT EXISTS idx_performance_run_id ON performance_metrics(run_id);
                CREATE INDEX IF NOT EXISTS idx_service_health_run_id ON service_health(run_id);
            """
            )

    def store_test_run(self, results: Dict[str, Any]) -> int:
        """Store a test run and return the run ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO test_runs (
                    test_suite, status, total_tests, passed_tests, failed_tests,
                    skipped_tests, duration_seconds, coverage_percent, commit_hash,
                    branch, trigger_type, artifacts_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    results.get("test_suite", "unknown"),
                    results.get("status", "unknown"),
                    results.get("total_tests", 0),
                    results.get("passed_tests", 0),
                    results.get("failed_tests", 0),
                    results.get("skipped_tests", 0),
                    results.get("duration_seconds", 0),
                    results.get("coverage_percent", 0),
                    results.get("commit_hash"),
                    results.get("branch"),
                    results.get("trigger_type", "manual"),
                    results.get("artifacts_path"),
                ),
            )
            return cursor.lastrowid

    def get_recent_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent test runs"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM test_runs
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_run_details(self, run_id: int) -> Dict[str, Any]:
        """Get detailed information about a specific test run"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get run info
            cursor.execute("SELECT * FROM test_runs WHERE id = ?", (run_id,))
            run = cursor.fetchone()
            if not run:
                return {}

            # Get test cases
            cursor.execute("SELECT * FROM test_cases WHERE run_id = ?", (run_id,))
            test_cases = [dict(row) for row in cursor.fetchall()]

            # Get performance metrics
            cursor.execute(
                "SELECT * FROM performance_metrics WHERE run_id = ?", (run_id,)
            )
            performance = [dict(row) for row in cursor.fetchall()]

            # Get service health
            cursor.execute("SELECT * FROM service_health WHERE run_id = ?", (run_id,))
            service_health = [dict(row) for row in cursor.fetchall()]

            return {
                "run": dict(run),
                "test_cases": test_cases,
                "performance": performance,
                "service_health": service_health,
            }

    def get_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get test trends over the specified period"""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Success rate trend
            cursor.execute(
                """
                SELECT
                    DATE(timestamp) as date,
                    COUNT(*) as total_runs,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_runs,
                    AVG(duration_seconds) as avg_duration,
                    AVG(coverage_percent) as avg_coverage
                FROM test_runs
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date
            """,
                (cutoff_date,),
            )
            daily_trends = [dict(row) for row in cursor.fetchall()]

            # Test suite performance
            cursor.execute(
                """
                SELECT
                    test_suite,
                    COUNT(*) as runs,
                    AVG(duration_seconds) as avg_duration,
                    AVG(CAST(passed_tests AS FLOAT) / total_tests * 100) as success_rate
                FROM test_runs
                WHERE timestamp >= ? AND total_tests > 0
                GROUP BY test_suite
            """,
                (cutoff_date,),
            )
            suite_performance = [dict(row) for row in cursor.fetchall()]

            # Flaky tests (tests that sometimes pass, sometimes fail)
            cursor.execute(
                """
                SELECT
                    tc.name,
                    tc.classname,
                    COUNT(*) as total_runs,
                    SUM(CASE WHEN tc.status = 'passed' THEN 1 ELSE 0 END) as passed_runs,
                    AVG(tc.duration_seconds) as avg_duration
                FROM test_cases tc
                JOIN test_runs tr ON tc.run_id = tr.id
                WHERE tr.timestamp >= ?
                GROUP BY tc.name, tc.classname
                HAVING total_runs > 1
                   AND passed_runs > 0
                   AND passed_runs < total_runs
                ORDER BY total_runs DESC
            """,
                (cutoff_date,),
            )
            flaky_tests = [dict(row) for row in cursor.fetchall()]

            return {
                "daily_trends": daily_trends,
                "suite_performance": suite_performance,
                "flaky_tests": flaky_tests,
            }


class TestResultsParser:
    """Parser for various test result formats"""

    @staticmethod
    def parse_junit_xml(xml_path: Path) -> Dict[str, Any]:
        """Parse JUnit XML results"""
        if not xml_path.exists():
            return {}

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            # Handle both testsuite and testsuites root elements
            if root.tag == "testsuites":
                testsuite = root.find("testsuite")
            else:
                testsuite = root

            if testsuite is None:
                return {}

            result = {
                "total_tests": int(testsuite.get("tests", 0)),
                "failed_tests": int(testsuite.get("failures", 0)),
                "error_tests": int(testsuite.get("errors", 0)),
                "skipped_tests": int(testsuite.get("skipped", 0)),
                "duration_seconds": float(testsuite.get("time", 0)),
                "test_cases": [],
            }

            result["passed_tests"] = (
                result["total_tests"]
                - result["failed_tests"]
                - result["error_tests"]
                - result["skipped_tests"]
            )

            # Parse individual test cases
            for testcase in testsuite.findall("testcase"):
                case = {
                    "name": testcase.get("name"),
                    "classname": testcase.get("classname"),
                    "duration_seconds": float(testcase.get("time", 0)),
                    "status": "passed",
                    "error_message": None,
                    "failure_message": None,
                }

                # Check for failures or errors
                failure = testcase.find("failure")
                error = testcase.find("error")
                skipped = testcase.find("skipped")

                if failure is not None:
                    case["status"] = "failed"
                    case["failure_message"] = failure.text
                elif error is not None:
                    case["status"] = "error"
                    case["error_message"] = error.text
                elif skipped is not None:
                    case["status"] = "skipped"

                result["test_cases"].append(case)

            return result

        except ET.ParseError as e:
            print(f"Error parsing JUnit XML: {e}")
            return {}

    @staticmethod
    def parse_coverage_xml(xml_path: Path) -> float:
        """Parse coverage XML and return coverage percentage"""
        if not xml_path.exists():
            return 0.0

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            # Look for coverage element with line-rate attribute
            coverage_elem = root.find(".//coverage")
            if coverage_elem is not None:
                line_rate = coverage_elem.get("line-rate")
                if line_rate:
                    return float(line_rate) * 100

            return 0.0

        except (ET.ParseError, ValueError) as e:
            print(f"Error parsing coverage XML: {e}")
            return 0.0

    @staticmethod
    def parse_benchmark_json(json_path: Path) -> List[Dict[str, Any]]:
        """Parse pytest-benchmark JSON results"""
        if not json_path.exists():
            return []

        try:
            with open(json_path, "r") as f:
                data = json.load(f)

            benchmarks = []
            for benchmark in data.get("benchmarks", []):
                benchmarks.append(
                    {
                        "name": benchmark.get("name"),
                        "fullname": benchmark.get("fullname"),
                        "min_time": benchmark.get("stats", {}).get("min"),
                        "max_time": benchmark.get("stats", {}).get("max"),
                        "mean_time": benchmark.get("stats", {}).get("mean"),
                        "median_time": benchmark.get("stats", {}).get("median"),
                        "stddev": benchmark.get("stats", {}).get("stddev"),
                        "rounds": benchmark.get("stats", {}).get("rounds"),
                    }
                )

            return benchmarks

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing benchmark JSON: {e}")
            return []


class TestDashboard:
    """Main dashboard application"""

    def __init__(self):
        self.app = FastAPI(title="Archon MCP Integration Test Dashboard")
        self.db = TestResultsDB(DB_PATH)
        self.active_connections: List[WebSocket] = []
        self.setup_routes()

    def setup_routes(self):
        """Setup FastAPI routes"""

        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Main dashboard page"""
            return HTMLResponse(content=self.get_dashboard_html())

        @self.app.get("/api/recent-runs")
        async def get_recent_runs():
            """Get recent test runs"""
            runs = self.db.get_recent_runs(50)
            return JSONResponse(content=runs)

        @self.app.get("/api/run/{run_id}")
        async def get_run_details(run_id: int):
            """Get detailed information about a specific run"""
            details = self.db.get_run_details(run_id)
            if not details:
                raise HTTPException(status_code=404, detail="Test run not found")
            return JSONResponse(content=details)

        @self.app.get("/api/trends")
        async def get_trends(days: int = 30):
            """Get test trends"""
            trends = self.db.get_trends(days)
            return JSONResponse(content=trends)

        @self.app.get("/api/scan-results")
        async def scan_results():
            """Scan for new test results and update database"""
            await self.scan_and_import_results()
            return JSONResponse(content={"status": "success"})

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates"""
            await websocket.accept()
            self.active_connections.append(websocket)
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                self.active_connections.remove(websocket)

    def get_dashboard_html(self) -> str:
        """Generate the main dashboard HTML"""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Archon MCP Integration Test Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f8f9fa;
            color: #333;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            border: 1px solid #e9ecef;
        }
        .metric {
            text-align: center;
            padding: 15px;
        }
        .metric-value {
            font-size: 2.5rem;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .metric-label {
            color: #6c757d;
            font-size: 0.9rem;
        }
        .status-success { color: #28a745; }
        .status-failure { color: #dc3545; }
        .status-warning { color: #ffc107; }
        .status-info { color: #17a2b8; }
        .chart-container {
            position: relative;
            height: 300px;
            margin-top: 20px;
        }
        .runs-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        .runs-table th,
        .runs-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #dee2e6;
        }
        .runs-table th {
            background: #f8f9fa;
            font-weight: 600;
        }
        .runs-table tbody tr:hover {
            background: #f8f9fa;
        }
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        .badge-success { background: #d4edda; color: #155724; }
        .badge-failure { background: #f8d7da; color: #721c24; }
        .badge-warning { background: #fff3cd; color: #856404; }
        .loading {
            text-align: center;
            padding: 40px;
            color: #6c757d;
        }
        .refresh-btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin-bottom: 15px;
        }
        .refresh-btn:hover { background: #0056b3; }
        .connection-status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 15px;
            border-radius: 5px;
            font-size: 0.8rem;
        }
        .connected { background: #d4edda; color: #155724; }
        .disconnected { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <h1>🧪 Archon MCP Integration Test Dashboard</h1>
            <p>Real-time monitoring and analysis of MCP document indexing pipeline tests</p>
        </div>
    </div>

    <div class="connection-status" id="connectionStatus">Connecting...</div>

    <div class="container">
        <button class="refresh-btn" onclick="refreshData()">🔄 Refresh Data</button>

        <div class="grid">
            <div class="card">
                <h3>📊 Test Summary</h3>
                <div class="grid" style="grid-template-columns: repeat(2, 1fr); gap: 10px;">
                    <div class="metric">
                        <div class="metric-value status-success" id="totalRuns">-</div>
                        <div class="metric-label">Total Runs</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value status-info" id="successRate">-</div>
                        <div class="metric-label">Success Rate</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <h3>⏱️ Performance</h3>
                <div class="grid" style="grid-template-columns: repeat(2, 1fr); gap: 10px;">
                    <div class="metric">
                        <div class="metric-value status-info" id="avgDuration">-</div>
                        <div class="metric-label">Avg Duration</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value status-info" id="avgCoverage">-</div>
                        <div class="metric-label">Avg Coverage</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <h3>🎯 Recent Status</h3>
                <div class="metric">
                    <div class="metric-value" id="lastRunStatus">-</div>
                    <div class="metric-label" id="lastRunTime">-</div>
                </div>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <h3>📈 Success Rate Trend</h3>
                <div class="chart-container">
                    <canvas id="successTrendChart"></canvas>
                </div>
            </div>

            <div class="card">
                <h3>⚡ Duration Trend</h3>
                <div class="chart-container">
                    <canvas id="durationTrendChart"></canvas>
                </div>
            </div>
        </div>

        <div class="card">
            <h3>📋 Recent Test Runs</h3>
            <table class="runs-table">
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Suite</th>
                        <th>Status</th>
                        <th>Tests</th>
                        <th>Duration</th>
                        <th>Coverage</th>
                    </tr>
                </thead>
                <tbody id="runsTableBody">
                    <tr><td colspan="6" class="loading">Loading test runs...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        let ws = null;
        let successTrendChart = null;
        let durationTrendChart = null;

        // Initialize the dashboard
        document.addEventListener('DOMContentLoaded', function() {
            initWebSocket();
            refreshData();

            // Auto-refresh every 30 seconds
            setInterval(refreshData, 30000);
        });

        function initWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;

            ws = new WebSocket(wsUrl);

            ws.onopen = function() {
                document.getElementById('connectionStatus').textContent = 'Connected';
                document.getElementById('connectionStatus').className = 'connection-status connected';
            };

            ws.onclose = function() {
                document.getElementById('connectionStatus').textContent = 'Disconnected';
                document.getElementById('connectionStatus').className = 'connection-status disconnected';

                // Reconnect after 5 seconds
                setTimeout(initWebSocket, 5000);
            };

            ws.onerror = function() {
                document.getElementById('connectionStatus').textContent = 'Connection Error';
                document.getElementById('connectionStatus').className = 'connection-status disconnected';
            };
        }

        async function refreshData() {
            try {
                // Scan for new results
                await fetch('/api/scan-results');

                // Load recent runs
                const runsResponse = await fetch('/api/recent-runs');
                const runs = await runsResponse.json();
                updateRunsTable(runs);
                updateSummaryMetrics(runs);

                // Load trends
                const trendsResponse = await fetch('/api/trends?days=30');
                const trends = await trendsResponse.json();
                updateTrendCharts(trends);

            } catch (error) {
                console.error('Error refreshing data:', error);
            }
        }

        function updateRunsTable(runs) {
            const tbody = document.getElementById('runsTableBody');

            if (runs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="loading">No test runs found</td></tr>';
                return;
            }

            tbody.innerHTML = runs.map(run => `
                <tr onclick="showRunDetails(${run.id})" style="cursor: pointer;">
                    <td>${new Date(run.timestamp).toLocaleString()}</td>
                    <td>${run.test_suite}</td>
                    <td><span class="badge badge-${run.status === 'success' ? 'success' : 'failure'}">${run.status}</span></td>
                    <td>${run.passed_tests}/${run.total_tests}</td>
                    <td>${run.duration_seconds.toFixed(1)}s</td>
                    <td>${run.coverage_percent.toFixed(1)}%</td>
                </tr>
            `).join('');
        }

        function updateSummaryMetrics(runs) {
            if (runs.length === 0) return;

            const totalRuns = runs.length;
            const successfulRuns = runs.filter(r => r.status === 'success').length;
            const successRate = (successfulRuns / totalRuns * 100).toFixed(1);
            const avgDuration = (runs.reduce((sum, r) => sum + r.duration_seconds, 0) / totalRuns).toFixed(1);
            const avgCoverage = (runs.reduce((sum, r) => sum + r.coverage_percent, 0) / totalRuns).toFixed(1);

            document.getElementById('totalRuns').textContent = totalRuns;
            document.getElementById('successRate').textContent = `${successRate}%`;
            document.getElementById('avgDuration').textContent = `${avgDuration}s`;
            document.getElementById('avgCoverage').textContent = `${avgCoverage}%`;

            // Update last run status
            const lastRun = runs[0];
            const statusEl = document.getElementById('lastRunStatus');
            statusEl.textContent = lastRun.status.toUpperCase();
            statusEl.className = `metric-value status-${lastRun.status === 'success' ? 'success' : 'failure'}`;
            document.getElementById('lastRunTime').textContent = new Date(lastRun.timestamp).toLocaleString();
        }

        function updateTrendCharts(trends) {
            updateSuccessTrendChart(trends.daily_trends);
            updateDurationTrendChart(trends.daily_trends);
        }

        function updateSuccessTrendChart(dailyTrends) {
            const ctx = document.getElementById('successTrendChart').getContext('2d');

            if (successTrendChart) {
                successTrendChart.destroy();
            }

            const labels = dailyTrends.map(d => d.date);
            const successRates = dailyTrends.map(d =>
                d.total_runs > 0 ? (d.successful_runs / d.total_runs * 100) : 0
            );

            successTrendChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Success Rate (%)',
                        data: successRates,
                        borderColor: '#28a745',
                        backgroundColor: 'rgba(40, 167, 69, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100
                        }
                    }
                }
            });
        }

        function updateDurationTrendChart(dailyTrends) {
            const ctx = document.getElementById('durationTrendChart').getContext('2d');

            if (durationTrendChart) {
                durationTrendChart.destroy();
            }

            const labels = dailyTrends.map(d => d.date);
            const durations = dailyTrends.map(d => d.avg_duration || 0);

            durationTrendChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Avg Duration (seconds)',
                        data: durations,
                        borderColor: '#007bff',
                        backgroundColor: 'rgba(0, 123, 255, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }

        function showRunDetails(runId) {
            // This would open a modal or navigate to a details page
            // For now, just log the run ID
            console.log('Show details for run:', runId);
            // TODO: Implement detailed view
        }
    </script>
</body>
</html>
        """

    async def scan_and_import_results(self):
        """Scan for new test results and import them"""
        if not RESULTS_DIR.exists():
            return

        # Look for recent JUnit XML files
        junit_files = list(RESULTS_DIR.glob("**/junit.xml"))

        for junit_file in junit_files:
            # Check if this file has already been processed
            junit_file.stat()

            # Parse the results
            junit_results = TestResultsParser.parse_junit_xml(junit_file)
            if not junit_results:
                continue

            # Look for corresponding coverage file
            coverage_file = junit_file.parent / "coverage.xml"
            coverage_percent = TestResultsParser.parse_coverage_xml(coverage_file)

            # Look for benchmark results
            benchmark_file = junit_file.parent.parent / "benchmarks" / "benchmark.json"
            benchmarks = TestResultsParser.parse_benchmark_json(benchmark_file)

            # Determine test suite from file path
            test_suite = "unknown"
            if "integration" in str(junit_file):
                test_suite = "integration"

            # Determine status
            status = (
                "success"
                if junit_results["failed_tests"] == 0
                and junit_results["error_tests"] == 0
                else "failure"
            )

            # Store the results
            result_data = {
                "test_suite": test_suite,
                "status": status,
                "total_tests": junit_results["total_tests"],
                "passed_tests": junit_results["passed_tests"],
                "failed_tests": junit_results["failed_tests"]
                + junit_results["error_tests"],
                "skipped_tests": junit_results["skipped_tests"],
                "duration_seconds": junit_results["duration_seconds"],
                "coverage_percent": coverage_percent,
                "artifacts_path": str(junit_file.parent),
                "trigger_type": "manual",  # Could be enhanced to detect CI vs manual
            }

            run_id = self.db.store_test_run(result_data)

            # Store individual test cases
            with sqlite3.connect(self.db.db_path) as conn:
                for test_case in junit_results["test_cases"]:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO test_cases (
                            run_id, name, classname, status, duration_seconds,
                            error_message, failure_message
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            run_id,
                            test_case["name"],
                            test_case["classname"],
                            test_case["status"],
                            test_case["duration_seconds"],
                            test_case["error_message"],
                            test_case["failure_message"],
                        ),
                    )

                # Store benchmark data
                for benchmark in benchmarks:
                    if benchmark["mean_time"]:
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO performance_metrics (
                                run_id, metric_name, metric_value, metric_unit, benchmark_name
                            ) VALUES (?, ?, ?, ?, ?)
                        """,
                            (
                                run_id,
                                "mean_duration",
                                benchmark["mean_time"],
                                "seconds",
                                benchmark["name"],
                            ),
                        )

        # Notify connected clients
        await self.notify_clients({"type": "data_updated"})

    async def notify_clients(self, message: Dict[str, Any]):
        """Send message to all connected WebSocket clients"""
        if not self.active_connections:
            return

        message_json = json.dumps(message)
        for connection in self.active_connections[
            :
        ]:  # Copy list to avoid modification during iteration
            try:
                await connection.send_text(message_json)
            except:
                # Remove disconnected clients
                self.active_connections.remove(connection)


@click.command()
@click.option("--port", default=DASHBOARD_PORT, help="Port to run the dashboard on")
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--scan", is_flag=True, help="Scan for existing results on startup")
@click.option("--watch", is_flag=True, help="Watch for new result files")
def main(port: int, host: str, scan: bool, watch: bool):
    """Launch the Archon MCP Integration Test Dashboard"""
    dashboard = TestDashboard()

    if scan:
        print("Scanning for existing test results...")
        asyncio.run(dashboard.scan_and_import_results())
        print("Scan complete.")

    print("🚀 Starting Archon MCP Integration Test Dashboard")
    print(f"📊 Dashboard URL: http://{host}:{port}")
    print(f"🗃️  Database: {DB_PATH}")
    print(f"📁 Results directory: {RESULTS_DIR}")

    if watch:
        print("👀 Watching for new test results...")
        # In a real implementation, you'd set up file system watching here

    uvicorn.run(dashboard.app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
