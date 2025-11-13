"""
Structured Data Extractor - Advanced Implementation

This module provides structured data extraction capabilities
for the LangExtract service with support for tables, forms, JSON, YAML, and metadata.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel


class StructuredDataResult(BaseModel):
    """Result model for structured data extraction"""

    data: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    extraction_type: str = "structured"
    tables: List[Dict[str, Any]] = []
    forms: List[Dict[str, Any]] = []
    schema_data: Dict[str, Any] = {}
    confidence_score: float = 0.0


class StructuredDataExtractor:
    """
    Advanced structured data extractor for processing documents and extracting
    structured information such as tables, forms, JSON/YAML data, and schemas.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the structured data extractor"""
        self.config = config or {}
        self.initialized = False

        # Statistics tracking
        self.stats = {
            "total_extractions": 0,
            "successful_extractions": 0,
            "failed_extractions": 0,
            "total_tables_extracted": 0,
            "total_forms_extracted": 0,
            "total_json_objects_extracted": 0,
            "total_yaml_objects_extracted": 0,
            "average_extraction_time_ms": 0.0,
        }

        # Extraction patterns
        self.patterns = {
            "table_patterns": [
                r"\|([^|\n]+\|[^|\n]*\|[^|\n]*)\|",  # Markdown table
                r"<table[^>]*>(.*?)</table>",  # HTML table
                r"(\w+\s+\w+\s+\w+(?:\s+\w+)*)\n([\-\s]+)\n((?:\w+\s+\w+\s+\w+(?:\s+\w+)*\n?)+)",  # Simple text table
            ],
            "form_patterns": [
                r"<form[^>]*>(.*?)</form>",  # HTML form
                r'<input[^>]*type=["\']([^"\']+)["\'][^>]*name=["\']([^"\']+)["\'][^>]*>',  # Input field
                r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>',  # Select field
            ],
            "json_pattern": r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}",
            "yaml_pattern": r"^(\s*[\w\-]+:\s*(?:\||\>)?[^\n]*\n(?:\s+[^\n]*\n)*)",
            "key_value_pattern": r"^(\s*)([a-zA-Z_][\w\-\.]*)\s*[:=]\s*([^\n]+)$",
        }

    async def initialize(self):
        """Initialize the extractor"""
        self.initialized = True

    async def extract_structured_data(
        self,
        content: str,
        document_path: str,
        schema_hints: Optional[Dict[str, Any]] = None,
    ) -> StructuredDataResult:
        """
        Extract structured data from content

        Args:
            content: The content to extract from
            document_path: Path to the source document
            schema_hints: Optional hints about expected schema

        Returns:
            StructuredDataResult with extracted structured data
        """
        start_time = datetime.utcnow()

        try:
            if not self.initialized:
                await self.initialize()

            self.stats["total_extractions"] += 1

            # Determine content type from file extension
            content_type = self._determine_content_type(document_path)

            # Extract different types of structured data
            tables = await self.extract_tables(content, content_type)
            forms = await self.extract_forms(content, content_type)
            json_data = await self._extract_json_data(content)
            yaml_data = await self._extract_yaml_data(content)
            key_value_data = await self._extract_key_value_pairs(content)
            metadata = await self.extract_metadata(content, document_path)

            # Build schema data
            schema_data = await self._build_schema_data(
                tables, forms, json_data, yaml_data, key_value_data, schema_hints
            )

            # Calculate confidence score
            confidence = self._calculate_confidence_score(
                tables, forms, json_data, yaml_data, key_value_data, content
            )

            # Create comprehensive result
            extraction_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            result = StructuredDataResult(
                data={
                    "json_objects": json_data,
                    "yaml_objects": yaml_data,
                    "key_value_pairs": key_value_data,
                    "total_structured_elements": len(tables)
                    + len(forms)
                    + len(json_data)
                    + len(yaml_data)
                    + len(key_value_data),
                },
                metadata={
                    **metadata,
                    "content_length": len(content),
                    "content_type": content_type,
                    "document_path": document_path,
                    "extraction_time_ms": extraction_time_ms,
                    "schema_hints_applied": bool(schema_hints),
                },
                extraction_type="structured",
                tables=tables,
                forms=forms,
                schema_data=schema_data,
                confidence_score=confidence,
            )

            # Update statistics
            self.stats["successful_extractions"] += 1
            self.stats["total_tables_extracted"] += len(tables)
            self.stats["total_forms_extracted"] += len(forms)
            self.stats["total_json_objects_extracted"] += len(json_data)
            self.stats["total_yaml_objects_extracted"] += len(yaml_data)
            self._update_average_time(extraction_time_ms)

            return result

        except Exception as e:
            self.stats["failed_extractions"] += 1

            # Return empty result with error info on failure
            return StructuredDataResult(
                data={"error": str(e)},
                metadata={
                    "content_length": len(content),
                    "document_path": document_path,
                    "extraction_failed": True,
                    "error_message": str(e),
                },
                confidence_score=0.0,
            )

    async def extract_tables(
        self, content: str, content_type: str = "text"
    ) -> List[Dict[str, Any]]:
        """Extract table data from content"""
        tables = []

        try:
            if content_type == "markdown" or ".md" in content_type:
                tables.extend(await self._extract_markdown_tables(content))
            elif content_type == "html":
                tables.extend(await self._extract_html_tables(content))
            else:
                tables.extend(await self._extract_text_tables(content))

        except Exception:
            # Log error but don't fail the extraction
            pass

        return tables

    async def extract_forms(
        self, content: str, content_type: str = "text"
    ) -> List[Dict[str, Any]]:
        """Extract form data from content"""
        forms = []

        try:
            if content_type == "html":
                forms.extend(await self._extract_html_forms(content))
            else:
                # Try to extract form-like structures from text
                forms.extend(await self._extract_text_forms(content))

        except Exception:
            # Log error but don't fail the extraction
            pass

        return forms

    async def extract_metadata(
        self, content: str, document_path: str = ""
    ) -> Dict[str, Any]:
        """Extract metadata from content"""
        metadata = {
            "document_type": self._determine_content_type(document_path),
            "line_count": len(content.split("\n")),
            "word_count": len(content.split()),
            "character_count": len(content),
            "has_structured_data": False,
            "structure_types": [],
        }

        try:
            # Check for various structured data indicators
            if re.search(self.patterns["json_pattern"], content):
                metadata["has_structured_data"] = True
                metadata["structure_types"].append("json")

            if re.search(self.patterns["yaml_pattern"], content, re.MULTILINE):
                metadata["has_structured_data"] = True
                metadata["structure_types"].append("yaml")

            if any(
                re.search(pattern, content, re.DOTALL)
                for pattern in self.patterns["table_patterns"]
            ):
                metadata["has_structured_data"] = True
                metadata["structure_types"].append("table")

            if any(
                re.search(pattern, content, re.DOTALL)
                for pattern in self.patterns["form_patterns"]
            ):
                metadata["has_structured_data"] = True
                metadata["structure_types"].append("form")

            # Extract frontmatter metadata if present
            frontmatter = self._extract_frontmatter(content)
            if frontmatter:
                metadata["frontmatter"] = frontmatter
                metadata["has_structured_data"] = True
                metadata["structure_types"].append("frontmatter")

        except Exception:
            pass

        return metadata

    async def _extract_json_data(self, content: str) -> List[Dict[str, Any]]:
        """Extract JSON objects from content"""
        json_objects = []

        try:
            # Find JSON-like patterns
            json_matches = re.finditer(
                self.patterns["json_pattern"], content, re.DOTALL
            )

            for match in json_matches:
                json_text = match.group(0)
                try:
                    # Try to parse as JSON
                    parsed_json = json.loads(json_text)
                    json_objects.append(
                        {
                            "data": parsed_json,
                            "source_text": json_text,
                            "start_position": match.start(),
                            "end_position": match.end(),
                            "confidence": 0.9,
                        }
                    )
                except json.JSONDecodeError:
                    # If not valid JSON, try to extract key-value pairs
                    kvp = self._extract_json_like_pairs(json_text)
                    if kvp:
                        json_objects.append(
                            {
                                "data": kvp,
                                "source_text": json_text,
                                "start_position": match.start(),
                                "end_position": match.end(),
                                "confidence": 0.6,
                            }
                        )

        except Exception:
            pass

        return json_objects

    async def _extract_yaml_data(self, content: str) -> List[Dict[str, Any]]:
        """Extract YAML data from content"""
        yaml_objects = []

        try:
            # Try to parse entire content as YAML first
            try:
                parsed_yaml = yaml.safe_load(content)
                if parsed_yaml and isinstance(parsed_yaml, (dict, list)):
                    yaml_objects.append(
                        {
                            "data": parsed_yaml,
                            "source_text": content,
                            "start_position": 0,
                            "end_position": len(content),
                            "confidence": 0.9,
                        }
                    )
                    return yaml_objects
            except yaml.YAMLError:
                pass

            # Find YAML-like sections
            yaml_matches = re.finditer(
                self.patterns["yaml_pattern"], content, re.MULTILINE
            )

            for match in yaml_matches:
                yaml_text = match.group(0)
                try:
                    parsed_yaml = yaml.safe_load(yaml_text)
                    if parsed_yaml:
                        yaml_objects.append(
                            {
                                "data": parsed_yaml,
                                "source_text": yaml_text,
                                "start_position": match.start(),
                                "end_position": match.end(),
                                "confidence": 0.8,
                            }
                        )
                except yaml.YAMLError:
                    pass

        except Exception:
            pass

        return yaml_objects

    async def _extract_key_value_pairs(self, content: str) -> List[Dict[str, Any]]:
        """Extract key-value pairs from content"""
        pairs = []

        try:
            lines = content.split("\n")

            for line_num, line in enumerate(lines):
                match = re.match(self.patterns["key_value_pattern"], line)
                if match:
                    indent = match.group(1)
                    key = match.group(2)
                    value = match.group(3).strip()

                    # Try to infer value type
                    parsed_value = self._parse_value(value)

                    pairs.append(
                        {
                            "key": key,
                            "value": parsed_value,
                            "original_value": value,
                            "line_number": line_num + 1,
                            "indentation": len(indent),
                            "confidence": 0.7,
                        }
                    )

        except Exception:
            pass

        return pairs

    async def _extract_markdown_tables(self, content: str) -> List[Dict[str, Any]]:
        """Extract tables from markdown content"""
        tables = []

        try:
            # Pattern for markdown tables
            table_pattern = r"\|([^|\n]+(?:\|[^|\n]*)+)\|\s*\n\|[\s\-\|:]+\|\s*\n((?:\|[^|\n]+(?:\|[^|\n]*)*\|\s*\n?)+)"

            matches = re.finditer(table_pattern, content)

            for match in matches:
                header_row = match.group(1)
                data_rows = match.group(2)

                # Parse header
                headers = [h.strip() for h in header_row.split("|") if h.strip()]

                # Parse rows
                rows = []
                for row_line in data_rows.strip().split("\n"):
                    if row_line.strip().startswith("|"):
                        row_data = [
                            cell.strip() for cell in row_line.split("|") if cell.strip()
                        ]
                        if row_data:
                            rows.append(row_data)

                if headers and rows:
                    tables.append(
                        {
                            "type": "markdown_table",
                            "headers": headers,
                            "rows": rows,
                            "row_count": len(rows),
                            "column_count": len(headers),
                            "source_text": match.group(0),
                            "confidence": 0.9,
                        }
                    )

        except Exception:
            pass

        return tables

    async def _extract_html_tables(self, content: str) -> List[Dict[str, Any]]:
        """Extract tables from HTML content"""
        tables = []

        try:
            re.finditer(
                self.patterns["table_patterns"][1], content, re.DOTALL | re.IGNORECASE
            )

            for match in matches:
                table_content = match.group(1)

                # Extract headers (th elements)
                header_pattern = r"<th[^>]*>(.*?)</th>"
                headers = re.findall(header_pattern, table_content, re.IGNORECASE)

                # Extract rows (tr elements)
                row_pattern = r"<tr[^>]*>(.*?)</tr>"
                row_matches = re.findall(
                    row_pattern, table_content, re.DOTALL | re.IGNORECASE
                )

                rows = []
                for row_html in row_matches:
                    cell_pattern = r"<td[^>]*>(.*?)</td>"
                    cells = re.findall(cell_pattern, row_html, re.IGNORECASE)
                    if cells:
                        # Clean HTML from cells
                        cleaned_cells = [
                            re.sub(r"<[^>]+>", "", cell).strip() for cell in cells
                        ]
                        rows.append(cleaned_cells)

                if rows:
                    tables.append(
                        {
                            "type": "html_table",
                            "headers": headers if headers else [],
                            "rows": rows,
                            "row_count": len(rows),
                            "column_count": len(rows[0]) if rows else 0,
                            "source_text": match.group(0),
                            "confidence": 0.8,
                        }
                    )

        except Exception:
            pass

        return tables

    async def _extract_text_tables(self, content: str) -> List[Dict[str, Any]]:
        """Extract table-like structures from plain text"""
        tables = []

        try:
            lines = content.split("\n")

            for i, line in enumerate(lines):
                # Look for separator lines (dashes, equals, etc.)
                if re.match(r"^[\s\-=+|]+$", line.strip()):
                    # Check if previous line could be headers
                    if i > 0 and lines[i - 1].strip():
                        header_line = lines[i - 1].strip()

                        # Check if next lines contain data
                        data_lines = []
                        for j in range(i + 1, min(i + 10, len(lines))):
                            if lines[j].strip() and not re.match(
                                r"^[\s\-=+|]+$", lines[j].strip()
                            ):
                                data_lines.append(lines[j].strip())
                            else:
                                break

                        if data_lines and len(data_lines) >= 2:
                            # Try to parse as table
                            headers = self._split_text_columns(header_line)
                            rows = [
                                self._split_text_columns(line) for line in data_lines
                            ]

                            # Validate consistency
                            if all(len(row) == len(headers) for row in rows):
                                tables.append(
                                    {
                                        "type": "text_table",
                                        "headers": headers,
                                        "rows": rows,
                                        "row_count": len(rows),
                                        "column_count": len(headers),
                                        "source_text": "\n".join(
                                            [header_line, line] + data_lines
                                        ),
                                        "confidence": 0.6,
                                    }
                                )

        except Exception:
            pass

        return tables

    async def _extract_html_forms(self, content: str) -> List[Dict[str, Any]]:
        """Extract forms from HTML content"""
        forms = []

        try:
            form_matches = re.finditer(
                self.patterns["form_patterns"][0], content, re.DOTALL | re.IGNORECASE
            )

            for match in form_matches:
                form_content = match.group(1)

                # Extract input fields
                inputs = []
                input_matches = re.finditer(
                    self.patterns["form_patterns"][1], form_content, re.IGNORECASE
                )
                for input_match in input_matches:
                    input_type = input_match.group(1)
                    input_name = input_match.group(2)
                    inputs.append(
                        {
                            "type": input_type,
                            "name": input_name,
                            "element": "input",
                        }
                    )

                # Extract select fields
                select_matches = re.finditer(
                    self.patterns["form_patterns"][2],
                    form_content,
                    re.DOTALL | re.IGNORECASE,
                )
                for select_match in select_matches:
                    select_name = select_match.group(1)
                    select_content = select_match.group(2)

                    # Extract options
                    option_pattern = (
                        r'<option[^>]*value=["\']([^"\']+)["\'][^>]*>(.*?)</option>'
                    )
                    options = re.findall(option_pattern, select_content, re.IGNORECASE)

                    inputs.append(
                        {
                            "type": "select",
                            "name": select_name,
                            "element": "select",
                            "options": options,
                        }
                    )

                if inputs:
                    forms.append(
                        {
                            "type": "html_form",
                            "fields": inputs,
                            "field_count": len(inputs),
                            "source_text": match.group(0),
                            "confidence": 0.8,
                        }
                    )

        except Exception:
            pass

        return forms

    async def _extract_text_forms(self, content: str) -> List[Dict[str, Any]]:
        """Extract form-like structures from text"""
        forms = []

        try:
            # Look for patterns like "Field: ____" or "Field: [    ]"
            field_pattern = r"^[\s]*([A-Za-z\s]+?):\s*(?:_+|\[[\s_]*\]|\.+)\s*$"

            lines = content.split("\n")
            current_form_fields = []

            for line in lines:
                match = re.match(field_pattern, line)
                if match:
                    field_name = match.group(1).strip()
                    current_form_fields.append(
                        {
                            "name": field_name,
                            "type": "text",
                            "element": "text_field",
                        }
                    )
                else:
                    # If we have accumulated fields and hit a non-matching line, save the form
                    if (
                        len(current_form_fields) >= 3
                    ):  # Minimum 3 fields to consider it a form
                        forms.append(
                            {
                                "type": "text_form",
                                "fields": current_form_fields.copy(),
                                "field_count": len(current_form_fields),
                                "confidence": 0.5,
                            }
                        )
                    current_form_fields = []

            # Check for remaining fields at end
            if len(current_form_fields) >= 3:
                forms.append(
                    {
                        "type": "text_form",
                        "fields": current_form_fields,
                        "field_count": len(current_form_fields),
                        "confidence": 0.5,
                    }
                )

        except Exception:
            pass

        return forms

    async def _build_schema_data(
        self,
        tables: List[Dict[str, Any]],
        forms: List[Dict[str, Any]],
        json_data: List[Dict[str, Any]],
        yaml_data: List[Dict[str, Any]],
        key_value_data: List[Dict[str, Any]],
        schema_hints: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build inferred schema data from extracted structures"""
        schema = {
            "inferred_types": {},
            "structure_summary": {
                "table_count": len(tables),
                "form_count": len(forms),
                "json_object_count": len(json_data),
                "yaml_object_count": len(yaml_data),
                "key_value_pair_count": len(key_value_data),
            },
            "field_types": {},
            "relationships": [],
        }

        try:
            # Analyze field types from tables
            for table in tables:
                if table.get("headers") and table.get("rows"):
                    for i, header in enumerate(table["headers"]):
                        column_values = [
                            row[i] for row in table["rows"] if len(row) > i
                        ]
                        inferred_type = self._infer_column_type(column_values)
                        schema["field_types"][header] = inferred_type

            # Analyze field types from forms
            for form in forms:
                for field in form.get("fields", []):
                    field_name = field.get("name", "")
                    field_type = field.get("type", "text")
                    schema["field_types"][field_name] = field_type

            # Apply schema hints if provided
            if schema_hints:
                schema["hints_applied"] = schema_hints
                if "expected_fields" in schema_hints:
                    for field_name, field_type in schema_hints[
                        "expected_fields"
                    ].items():
                        schema["field_types"][field_name] = field_type

        except Exception:
            pass

        return schema

    def _determine_content_type(self, document_path: str) -> str:
        """Determine content type from document path"""
        if not document_path:
            return "text"

        extension = Path(document_path).suffix.lower()

        type_mapping = {
            ".md": "markdown",
            ".html": "html",
            ".htm": "html",
            ".json": "json",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".xml": "xml",
            ".csv": "csv",
            ".tsv": "tsv",
        }

        return type_mapping.get(extension, "text")

    def _extract_frontmatter(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract YAML frontmatter from content"""
        try:
            # Look for YAML frontmatter pattern (--- at start, --- to close)
            frontmatter_pattern = r"^---\n(.*?)\n---"
            match = re.match(frontmatter_pattern, content, re.DOTALL)

            if match:
                frontmatter_text = match.group(1)
                return yaml.safe_load(frontmatter_text)

        except Exception:
            pass

        return None

    def _extract_json_like_pairs(self, json_text: str) -> Dict[str, Any]:
        """Extract key-value pairs from JSON-like text"""
        pairs = {}

        try:
            # Look for key: value patterns
            kv_pattern = r'["\']?(\w+)["\']?\s*:\s*["\']?([^,}\n]+)["\']?'
            matches = re.findall(kv_pattern, json_text)

            for key, value in matches:
                pairs[key] = self._parse_value(value.strip(" \"'"))

        except Exception:
            pass

        return pairs

    def _parse_value(self, value_str: str) -> Any:
        """Parse a string value to appropriate Python type"""
        value_str = value_str.strip()

        # Boolean values
        if value_str.lower() in ["true", "yes", "on"]:
            return True
        if value_str.lower() in ["false", "no", "off"]:
            return False

        # None/null values
        if value_str.lower() in ["null", "none", "nil"]:
            return None

        # Numeric values
        try:
            if "." in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            pass

        # Return as string
        return value_str

    def _split_text_columns(self, line: str) -> List[str]:
        """Split a text line into columns"""
        # Try multiple delimiters
        for delimiter in ["\t", "  ", " | ", "|"]:
            parts = [part.strip() for part in line.split(delimiter) if part.strip()]
            if len(parts) > 1:
                return parts

        # Fallback: split on multiple spaces
        parts = re.split(r"\s{2,}", line.strip())
        return [part.strip() for part in parts if part.strip()]

    def _infer_column_type(self, values: List[str]) -> str:
        """Infer the data type of a column from its values"""
        if not values:
            return "unknown"

        # Count type occurrences
        type_counts = {"int": 0, "float": 0, "bool": 0, "date": 0, "string": 0}

        for value in values:
            value_str = str(value).strip()

            if not value_str:
                continue

            # Try to determine type
            if value_str.lower() in ["true", "false", "yes", "no"]:
                type_counts["bool"] += 1
            elif re.match(r"^\d+$", value_str):
                type_counts["int"] += 1
            elif re.match(r"^\d+\.\d+$", value_str):
                type_counts["float"] += 1
            elif re.match(r"^\d{4}-\d{2}-\d{2}", value_str):
                type_counts["date"] += 1
            else:
                type_counts["string"] += 1

        # Return the most common type
        return max(type_counts, key=type_counts.get)

    def _calculate_confidence_score(
        self,
        tables: List[Dict[str, Any]],
        forms: List[Dict[str, Any]],
        json_data: List[Dict[str, Any]],
        yaml_data: List[Dict[str, Any]],
        key_value_data: List[Dict[str, Any]],
        content: str,
    ) -> float:
        """Calculate overall confidence score for extraction"""
        if not any([tables, forms, json_data, yaml_data, key_value_data]):
            return 0.0

        # Calculate weighted confidence based on extraction quality
        total_score = 0.0
        total_weight = 0.0

        # Weight different extraction types
        extraction_weights = {
            "tables": 0.3,
            "forms": 0.2,
            "json": 0.25,
            "yaml": 0.15,
            "key_value": 0.1,
        }

        for extraction_type, items in {
            "tables": tables,
            "forms": forms,
            "json": json_data,
            "yaml": yaml_data,
            "key_value": key_value_data,
        }.items():
            if items:
                # Average confidence of items
                item_confidence = sum(
                    item.get("confidence", 0.5) for item in items
                ) / len(items)
                weight = extraction_weights[extraction_type]

                total_score += item_confidence * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0

        return total_score / total_weight

    def _update_average_time(self, extraction_time: float):
        """Update the average extraction time"""
        if self.stats["successful_extractions"] == 1:
            self.stats["average_extraction_time_ms"] = extraction_time
        else:
            # Calculate rolling average
            old_avg = self.stats["average_extraction_time_ms"]
            count = self.stats["successful_extractions"]
            new_avg = ((old_avg * (count - 1)) + extraction_time) / count
            self.stats["average_extraction_time_ms"] = new_avg

    async def get_statistics(self) -> Dict[str, Any]:
        """Get extractor statistics"""
        success_rate = 0.0
        if self.stats["total_extractions"] > 0:
            success_rate = (
                self.stats["successful_extractions"] / self.stats["total_extractions"]
            )

        return {
            "extractor_type": "structured_data",
            "total_extractions": self.stats["total_extractions"],
            "successful_extractions": self.stats["successful_extractions"],
            "failed_extractions": self.stats["failed_extractions"],
            "success_rate": success_rate,
            "total_tables_extracted": self.stats["total_tables_extracted"],
            "total_forms_extracted": self.stats["total_forms_extracted"],
            "total_json_objects_extracted": self.stats["total_json_objects_extracted"],
            "total_yaml_objects_extracted": self.stats["total_yaml_objects_extracted"],
            "average_extraction_time_ms": self.stats["average_extraction_time_ms"],
            "supported_formats": ["markdown", "html", "json", "yaml", "text", "csv"],
            "extraction_capabilities": [
                "markdown_tables",
                "html_tables",
                "text_tables",
                "html_forms",
                "text_forms",
                "json_objects",
                "yaml_data",
                "key_value_pairs",
                "frontmatter",
                "schema_inference",
            ],
        }
