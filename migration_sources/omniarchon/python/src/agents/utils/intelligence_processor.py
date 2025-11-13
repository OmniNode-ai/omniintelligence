#!/usr/bin/env python3
"""
Intelligence Processing Utilities

Handles file processing with intelligence service integration for code analysis,
document extraction, and quality assessment.

Version: 1.0.0
Author: Archon Intelligence Services
"""

import asyncio
from datetime import UTC, datetime
from typing import Any, Optional

import httpx


class IntelligenceProcessor:
    """
    Intelligence service integration processor.

    Coordinates file processing with Archon intelligence services including
    code analysis, document extraction, and quality assessment.
    """

    def __init__(
        self,
        intelligence_service_url: str = "http://localhost:8053",
        timeout: float = 20.0,
        concurrent_limit: int = 3,
    ):
        """
        Initialize intelligence processor.

        Args:
            intelligence_service_url: Base URL for intelligence service
            timeout: Request timeout in seconds
            concurrent_limit: Maximum concurrent requests
        """
        self.intelligence_service_url = intelligence_service_url
        self.timeout = timeout
        self.concurrent_limit = concurrent_limit
        self.verbose = False

    async def process_files_with_intelligence(
        self,
        files: list[dict[str, Any]],
        config: dict[str, Any],
        stats: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Process files with intelligence service integration.

        Args:
            files: List of file info dictionaries to process
            config: Processing configuration
            stats: Statistics dictionary to update

        Returns:
            List of processed file dictionaries with intelligence analysis
        """
        processed_files = []

        # Process files concurrently with limit
        semaphore = asyncio.Semaphore(self.concurrent_limit)

        async def process_single_file(
            file_info: dict[str, Any],
        ) -> Optional[dict[str, Any]]:
            async with semaphore:
                return await self.process_file_with_intelligence(file_info, config)

        # Create tasks for concurrent processing
        tasks = [process_single_file(file_info) for file_info in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect successful results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                stats["errors"] += 1
                if self.verbose:
                    print(f"⚠️ Error processing {files[i]['name']}: {result}")
            elif result:
                processed_files.append(result)
                stats["files_processed"] += 1

        return processed_files

    async def process_file_with_intelligence(
        self, file_info: dict[str, Any], config: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """
        Process a single file with intelligence service integration.

        Args:
            file_info: File metadata dictionary
            config: Processing configuration

        Returns:
            Processed file dictionary with intelligence analysis, or None if processing fails
        """
        try:
            # Read file content
            content = file_info["path"].read_text(encoding="utf-8", errors="ignore")

            # Truncate content if too long
            max_content_length = 8000  # Reasonable for API calls
            if len(content) > max_content_length:
                content = (
                    content[:max_content_length]
                    + "\n... [content truncated for processing]"
                )

            processed_file = {
                "file_info": file_info,
                "content": content,
                "content_length": len(content),
                "intelligence_analysis": None,
                "processing_timestamp": datetime.now(UTC).isoformat(),
            }

            # Apply intelligence analysis based on file type and configuration
            if config.get("include_intelligence", True) and not config.get(
                "dry_run", False
            ):
                intelligence_result = await self.apply_intelligence_analysis(
                    processed_file, config
                )
                if intelligence_result:
                    processed_file["intelligence_analysis"] = intelligence_result
            elif config.get("dry_run", False):
                # Mock analysis for dry run
                processed_file["intelligence_analysis"] = {
                    "type": "mock_analysis",
                    "mock": True,
                    "file_type": file_info["file_type"],
                    "language": file_info["language"],
                    "quality_score": 0.8,
                }

            return processed_file

        except Exception as e:
            if self.verbose:
                print(f"⚠️ Failed to process {file_info['name']}: {e}")
            return None

    async def apply_intelligence_analysis(
        self, processed_file: dict[str, Any], config: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """
        Apply intelligence service analysis to processed file.

        Args:
            processed_file: Processed file dictionary with content
            config: Processing configuration

        Returns:
            Intelligence analysis result dictionary, or None if analysis fails
        """
        file_info = processed_file["file_info"]

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if file_info["file_type"] == "code":
                    # Code intelligence analysis
                    payload = {
                        "content": processed_file["content"],
                        "source_path": file_info["relative_path"],
                        "language": file_info["language"],
                    }

                    if self.verbose:
                        print(f"🔍 Analyzing code: {file_info['name']}")

                    response = await client.post(
                        f"{self.intelligence_service_url}/extract/code", json=payload
                    )

                elif file_info["file_type"] == "documentation":
                    # Document intelligence analysis
                    payload = {
                        "content": processed_file["content"],
                        "source_path": file_info["relative_path"],
                        "metadata": {
                            "file_type": file_info["file_type"],
                            "language": file_info["language"],
                        },
                        "store_entities": False,  # Don't store during crawling
                        "trigger_freshness_analysis": False,
                    }

                    if self.verbose:
                        print(f"📄 Analyzing document: {file_info['name']}")

                    response = await client.post(
                        f"{self.intelligence_service_url}/extract/document",
                        json=payload,
                    )

                else:
                    # Generic analysis for other file types
                    return {
                        "type": "generic_analysis",
                        "file_type": file_info["file_type"],
                        "language": file_info["language"],
                        "content_stats": {
                            "lines": processed_file["content"].count("\n") + 1,
                            "characters": len(processed_file["content"]),
                        },
                    }

                # Process response
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "type": f"{file_info['file_type']}_analysis",
                        "service_result": result,
                        "analysis_timestamp": datetime.now(UTC).isoformat(),
                        "service_used": "intelligence_service",
                    }
                else:
                    if self.verbose:
                        print(
                            f"⚠️ Intelligence service returned {response.status_code} for {file_info['name']}"
                        )
                    return None

        except httpx.RequestError as e:
            if self.verbose:
                print(
                    f"⚠️ Intelligence service request failed for {file_info['name']}: {e}"
                )
            return None
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Intelligence analysis failed for {file_info['name']}: {e}")
            return None
