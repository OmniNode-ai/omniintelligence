#!/usr/bin/env python3
"""
Pipeline Issue Diagnostic Script

Traces a test document through the ENTIRE pipeline to identify where data is lost.
Shows every transformation and logs exactly where fields disappear.

Usage:
    python3 scripts/diagnose_pipeline_issue.py --field file_extension
    python3 scripts/diagnose_pipeline_issue.py --field language
    python3 scripts/diagnose_pipeline_issue.py --file-path /path/to/test.py
"""

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from neo4j import GraphDatabase


# ANSI color codes
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def colored(text: str, color: str, bold: bool = False) -> str:
    """Return colored text for terminal output."""
    prefix = f"{Colors.BOLD}{color}" if bold else color
    return f"{prefix}{text}{Colors.RESET}"


class PipelineDiagnostic:
    """Trace document flow through the pipeline."""

    def __init__(self, field_to_trace: str, file_path: Optional[str] = None):
        self.field = field_to_trace
        self.file_path = file_path or "/Volumes/PRO-G40/Code/omniarchon/README.md"
        self.trace_results = []

    def log_step(self, step: str, status: str, details: Dict[str, Any]) -> None:
        """Log a pipeline step."""
        self.trace_results.append(
            {
                "step": step,
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "details": details,
            }
        )

        # Print to console
        status_icon = {
            "PASS": colored("✅", Colors.GREEN),
            "FAIL": colored("❌", Colors.RED),
            "WARN": colored("⚠️", Colors.YELLOW),
            "INFO": colored("ℹ️", Colors.BLUE),
        }.get(status, "")

        print(f"\n{status_icon} {colored(step, Colors.CYAN, bold=True)}")
        print(f"   Status: {status}")

        for key, value in details.items():
            # Truncate long values
            value_str = str(value)
            if len(value_str) > 200:
                value_str = value_str[:200] + "..."
            print(f"   {key}: {value_str}")

    def step1_read_file(self) -> Optional[str]:
        """Step 1: Read file content."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.log_step(
                "Step 1: Read File",
                "PASS",
                {
                    "file_path": self.file_path,
                    "content_length": len(content),
                    "content_preview": content[:100] if content else "(empty)",
                },
            )
            return content

        except Exception as e:
            self.log_step(
                "Step 1: Read File",
                "FAIL",
                {"file_path": self.file_path, "error": str(e)},
            )
            return None

    def step2_extract_metadata(self, content: str) -> Dict[str, Any]:
        """Step 2: Extract file metadata (language, extension)."""
        import os

        file_name = os.path.basename(self.file_path)
        file_extension = os.path.splitext(file_name)[1]

        # Simple language detection based on extension
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".md": "markdown",
            ".txt": "text",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
        }

        language = language_map.get(file_extension.lower(), "unknown")

        metadata = {
            "file_name": file_name,
            "file_extension": file_extension,
            "language": language,
            "size_bytes": len(content),
        }

        field_present = self.field in metadata and metadata[self.field]
        status = "PASS" if field_present else "WARN"

        self.log_step(
            "Step 2: Extract Metadata",
            status,
            {
                "extracted_metadata": metadata,
                f"{self.field}_present": field_present,
                f"{self.field}_value": metadata.get(self.field, "(missing)"),
            },
        )

        return metadata

    def step3_call_intelligence_service(
        self, content: str, metadata: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Step 3: Call intelligence service /process/document endpoint."""
        try:
            payload = {
                "file_path": self.file_path,
                "content": content,
                "project_name": "diagnostic-test",
                "correlation_id": f"diagnostic-{int(time.time())}",
            }

            response = requests.post(
                "http://localhost:8053/process/document", json=payload, timeout=30
            )

            if response.status_code == 200:
                result = response.json()

                field_present = self.field in result and result[self.field]
                status = "PASS" if field_present else "WARN"

                self.log_step(
                    "Step 3: Intelligence Service",
                    status,
                    {
                        "endpoint": "/process/document",
                        "status_code": response.status_code,
                        f"{self.field}_present": field_present,
                        f"{self.field}_value": result.get(self.field, "(missing)"),
                        "response_keys": list(result.keys()),
                    },
                )

                return result
            else:
                self.log_step(
                    "Step 3: Intelligence Service",
                    "FAIL",
                    {
                        "endpoint": "/process/document",
                        "status_code": response.status_code,
                        "error": response.text,
                    },
                )
                return None

        except Exception as e:
            self.log_step(
                "Step 3: Intelligence Service",
                "FAIL",
                {"endpoint": "/process/document", "error": str(e)},
            )
            return None

    def step4_check_memgraph_write(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Step 4: Check if data was written to Memgraph with the field."""
        try:
            driver = GraphDatabase.driver("bolt://localhost:7687")

            with driver.session() as session:
                # Wait a bit for async write
                time.sleep(2)

                result = session.run(
                    """
                    MATCH (f:FILE {file_path: $file_path})
                    RETURN f
                """,
                    file_path=file_path,
                )

                record = result.single()

                if record:
                    node = record["f"]
                    node_props = dict(node)

                    field_present = self.field in node_props and node_props[self.field]
                    status = "PASS" if field_present else "FAIL"

                    self.log_step(
                        "Step 4: Memgraph Storage",
                        status,
                        {
                            "file_path": file_path,
                            "node_found": True,
                            f"{self.field}_present": field_present,
                            f"{self.field}_value": node_props.get(
                                self.field, "(missing)"
                            ),
                            "all_properties": list(node_props.keys()),
                        },
                    )

                    driver.close()
                    return node_props
                else:
                    self.log_step(
                        "Step 4: Memgraph Storage",
                        "FAIL",
                        {
                            "file_path": file_path,
                            "node_found": False,
                            "error": "No FILE node found with this path",
                        },
                    )

                    driver.close()
                    return None

        except Exception as e:
            self.log_step(
                "Step 4: Memgraph Storage",
                "FAIL",
                {"file_path": file_path, "error": str(e)},
            )
            return None

    def step5_check_qdrant_vectors(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Step 5: Check if vectors were created in Qdrant."""
        try:
            # Search for vectors by file_path metadata
            response = requests.post(
                "http://localhost:6333/collections/archon-intelligence/points/scroll",
                json={
                    "filter": {
                        "must": [{"key": "file_path", "match": {"value": file_path}}]
                    },
                    "limit": 10,
                    "with_payload": True,
                },
                timeout=10,
            )

            if response.status_code == 200:
                result = response.json()
                points = result.get("result", {}).get("points", [])

                if points:
                    # Check first point's metadata
                    first_point = points[0]
                    payload = first_point.get("payload", {})

                    field_present = self.field in payload and payload[self.field]
                    status = "PASS" if field_present else "WARN"

                    self.log_step(
                        "Step 5: Qdrant Vectors",
                        status,
                        {
                            "file_path": file_path,
                            "vectors_found": len(points),
                            f"{self.field}_present": field_present,
                            f"{self.field}_value": payload.get(self.field, "(missing)"),
                            "payload_keys": list(payload.keys()),
                        },
                    )

                    return payload
                else:
                    self.log_step(
                        "Step 5: Qdrant Vectors",
                        "WARN",
                        {
                            "file_path": file_path,
                            "vectors_found": 0,
                            "note": "Vectors may not be created yet (async processing)",
                        },
                    )
                    return None
            else:
                self.log_step(
                    "Step 5: Qdrant Vectors",
                    "FAIL",
                    {
                        "file_path": file_path,
                        "status_code": response.status_code,
                        "error": response.text,
                    },
                )
                return None

        except Exception as e:
            self.log_step(
                "Step 5: Qdrant Vectors",
                "FAIL",
                {"file_path": file_path, "error": str(e)},
            )
            return None

    def analyze_results(self) -> None:
        """Analyze trace results and provide diagnosis."""
        print("\n" + "=" * 80)
        print(colored("DIAGNOSTIC SUMMARY", Colors.CYAN, bold=True))
        print("=" * 80)

        # Count passes and fails
        passes = sum(1 for r in self.trace_results if r["status"] == "PASS")
        fails = sum(1 for r in self.trace_results if r["status"] == "FAIL")
        warns = sum(1 for r in self.trace_results if r["status"] == "WARN")

        print(
            f"\nResults: {colored(f'{passes} PASS', Colors.GREEN)} | "
            f"{colored(f'{fails} FAIL', Colors.RED)} | "
            f"{colored(f'{warns} WARN', Colors.YELLOW)}"
        )

        # Identify where field was lost
        field_lost_at = None
        last_seen = None

        for result in self.trace_results:
            details = result["details"]
            field_key = f"{self.field}_present"

            if field_key in details:
                if details[field_key]:
                    last_seen = result["step"]
                elif last_seen:
                    field_lost_at = result["step"]
                    break

        print(f"\n{colored('Field Tracking:', Colors.BLUE, bold=True)}")
        print(f"  Field: {self.field}")

        if last_seen:
            print(f"  Last seen: {colored(last_seen, Colors.GREEN)}")
        else:
            print(f"  Last seen: {colored('Never detected', Colors.RED)}")

        if field_lost_at:
            print(f"  Lost at: {colored(field_lost_at, Colors.RED)}")
        elif not last_seen:
            print(f"  Lost at: {colored('Step 1 (never extracted)', Colors.RED)}")

        # Recommendations
        print(f"\n{colored('RECOMMENDATIONS:', Colors.YELLOW, bold=True)}")

        if not last_seen:
            print(f"  1. Field '{self.field}' was never extracted from the file")
            print(f"  2. Check metadata extraction logic in Step 2")
            print(f"  3. Verify file extension and language detection")

        elif field_lost_at == "Step 3: Intelligence Service":
            print(f"  1. Field '{self.field}' lost at intelligence service")
            print(f"  2. Check /process/document endpoint implementation")
            print(f"  3. Verify intelligence service passes metadata through")
            print(
                f"  4. Review: services/intelligence/src/api/endpoints/extraction_router.py"
            )

        elif field_lost_at == "Step 4: Memgraph Storage":
            print(f"  1. Field '{self.field}' lost when writing to Memgraph")
            print(f"  2. Check Memgraph write operations in bridge service")
            print(f"  3. Verify FILE node creation includes all metadata")
            print(
                f"  4. Review: services/intelligence/src/integrations/tree_stamping_bridge.py"
            )

        elif field_lost_at == "Step 5: Qdrant Vectors":
            print(f"  1. Field '{self.field}' lost when creating Qdrant vectors")
            print(f"  2. Check vector payload creation")
            print(f"  3. Verify metadata is included in vector metadata")
            print(f"  4. Review vector indexing logic")

        else:
            print(f"  1. Field '{self.field}' appears to be flowing correctly!")
            print(f"  2. Issue may be with existing data (not new ingestion)")
            print(
                f"  3. Consider re-indexing: python3 scripts/bulk_ingest_repository.py"
            )

        print("=" * 80)

    def run(self) -> None:
        """Run complete diagnostic."""
        print("=" * 80)
        print(
            colored(
                f"PIPELINE DIAGNOSTIC: Tracing field '{self.field}'",
                Colors.CYAN,
                bold=True,
            )
        )
        print("=" * 80)
        print(f"Test file: {self.file_path}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Step 1: Read file
        content = self.step1_read_file()
        if not content:
            print(
                colored(
                    "\n❌ Cannot proceed without file content", Colors.RED, bold=True
                )
            )
            return

        # Step 2: Extract metadata
        metadata = self.step2_extract_metadata(content)

        # Step 3: Call intelligence service
        intelligence_result = self.step3_call_intelligence_service(content, metadata)

        # Step 4: Check Memgraph
        memgraph_result = self.step4_check_memgraph_write(self.file_path)

        # Step 5: Check Qdrant
        qdrant_result = self.step5_check_qdrant_vectors(self.file_path)

        # Analyze and provide recommendations
        self.analyze_results()


def main():
    parser = argparse.ArgumentParser(
        description="Diagnose pipeline issues by tracing document flow"
    )
    parser.add_argument(
        "--field", required=True, help="Field to trace (e.g., file_extension, language)"
    )
    parser.add_argument("--file-path", help="Path to test file (default: README.md)")

    args = parser.parse_args()

    # Run diagnostic
    diagnostic = PipelineDiagnostic(field_to_trace=args.field, file_path=args.file_path)

    try:
        diagnostic.run()
    except KeyboardInterrupt:
        print(
            colored("\n\n⚠️  Diagnostic interrupted by user", Colors.YELLOW, bold=True)
        )
        sys.exit(1)
    except Exception as e:
        print(colored(f"\n\n❌ Diagnostic failed: {str(e)}", Colors.RED, bold=True))
        sys.exit(2)


if __name__ == "__main__":
    main()
