# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ModelIOAuditViolation - single I/O audit violation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from omniintelligence.audit.enum_io_audit_rule import EnumIOAuditRule

# Actionable guidance for each rule violation type.
REMEDIATION_HINTS: dict[EnumIOAuditRule, str] = {
    EnumIOAuditRule.NET_CLIENT: (
        "Move to an Effect node or inject client via dependency injection."
    ),
    EnumIOAuditRule.ENV_ACCESS: (
        "Pass configuration via constructor parameters instead of reading env vars."
    ),
    EnumIOAuditRule.FILE_IO: (
        "Move file I/O to an Effect node or pass file content as input parameter."
    ),
}

# Regex for extracting environment variable names from violation messages
_ENV_VAR_PATTERN = re.compile(r'["\']([A-Z_][A-Z0-9_]*)["\']')


def _generate_net_client_suggestion(message: str) -> str:
    """Generate suggestion for network/DB client violations."""
    msg_lower = message.lower()
    if "confluent_kafka" in msg_lower:
        return (
            "Create a separate Effect node for Kafka operations:\n"
            "  # node_kafka_publisher_effect.py\n"
            "  class NodeKafkaPublisherEffect:\n"
            "      def __init__(self, producer: Producer) -> None:\n"
            "          self._producer = producer  # Injected dependency"
        )
    elif "qdrant_client" in msg_lower:
        return (
            "Create a separate Effect node for Qdrant operations:\n"
            "  # node_vector_store_effect.py\n"
            "  class NodeVectorStoreEffect:\n"
            "      def __init__(self, client: QdrantClient) -> None:\n"
            "          self._client = client  # Injected dependency"
        )
    elif "httpx" in msg_lower:
        return (
            "Create a separate Effect node for HTTP operations:\n"
            "  # node_http_client_effect.py\n"
            "  class NodeHttpClientEffect:\n"
            "      def __init__(self, client: httpx.AsyncClient) -> None:\n"
            "          self._client = client  # Injected dependency"
        )
    elif "asyncpg" in msg_lower or "neo4j" in msg_lower:
        db_name = "PostgreSQL" if "asyncpg" in msg_lower else "Neo4j"
        return (
            f"Create a separate Effect node for {db_name} operations:\n"
            "  # node_database_effect.py\n"
            "  class NodeDatabaseEffect:\n"
            "      def __init__(self, connection: Connection) -> None:\n"
            "          self._conn = connection  # Injected dependency"
        )
    elif "aiofiles" in msg_lower:
        return (
            "Create a separate Effect node for async file operations:\n"
            "  # node_file_reader_effect.py\n"
            "  class NodeFileReaderEffect:\n"
            "      async def read_file(self, path: str) -> str:\n"
            "          async with aiofiles.open(path) as f:\n"
            "              return await f.read()"
        )
    return (
        "Create a separate Effect node and inject the client:\n"
        "  class NodeYourEffect:\n"
        "      def __init__(self, client: YourClient) -> None:\n"
        "          self._client = client  # Injected via DI"
    )


def _generate_env_access_suggestion(message: str) -> str:
    """Generate suggestion for environment variable access violations."""
    msg_lower = message.lower()
    env_var_match = _ENV_VAR_PATTERN.search(message)
    if "getenv" in msg_lower or "environ" in msg_lower:
        if env_var_match:
            env_var = env_var_match.group(1)
            config_name = "".join(
                word.capitalize() for word in env_var.lower().split("_")
            )
            return (
                f"Inject configuration via constructor instead of reading {env_var}:\n"
                f"  from pydantic_settings import BaseSettings\n"
                f"\n"
                f"  class {config_name}Config(BaseSettings):\n"
                f"      {env_var.lower()}: str\n"
                f"\n"
                f"  class NodeYourCompute:\n"
                f"      def __init__(self, config: {config_name}Config) -> None:\n"
                f"          self._config = config  # Injected, not read from env"
            )
        return (
            "Inject configuration via constructor:\n"
            "  from pydantic_settings import BaseSettings\n"
            "\n"
            "  class YourConfig(BaseSettings):\n"
            "      your_setting: str\n"
            "\n"
            "  class NodeYourCompute:\n"
            "      def __init__(self, config: YourConfig) -> None:\n"
            "          self._config = config  # Injected, not read from env"
        )
    return "Pass configuration via constructor parameters instead of reading env vars."


def _generate_file_io_suggestion(message: str) -> str:
    """Generate suggestion for file I/O violations."""
    msg_lower = message.lower()
    if "open()" in msg_lower or "io.open()" in msg_lower:
        return (
            "Pass file content as a parameter instead of reading directly:\n"
            "  # Before (violation):\n"
            "  def process(self, file_path: str) -> Result:\n"
            "      with open(file_path) as f:\n"
            "          content = f.read()\n"
            "\n"
            "  # After (pure compute):\n"
            "  def process(self, content: str) -> Result:\n"
            "      # Content passed in, no I/O in compute node"
        )
    elif "read_text" in msg_lower or "read_bytes" in msg_lower:
        method = "read_text" if "read_text" in msg_lower else "read_bytes"
        return_type = "str" if method == "read_text" else "bytes"
        return (
            f"Pass file content as a parameter instead of using Path.{method}():\n"
            f"  # Before (violation):\n"
            f"  def process(self, path: Path) -> Result:\n"
            f"      content = path.{method}()\n"
            f"\n"
            f"  # After (pure compute):\n"
            f"  def process(self, content: {return_type}) -> Result:\n"
            f"      # Content passed in, no I/O in compute node"
        )
    elif "write_text" in msg_lower or "write_bytes" in msg_lower:
        return (
            "Return data to be written instead of writing directly:\n"
            "  # Before (violation):\n"
            "  def process(self, path: Path, data: str) -> None:\n"
            "      path.write_text(data)\n"
            "\n"
            "  # After (pure compute):\n"
            "  def process(self, data: str) -> str:\n"
            "      return processed_data  # Effect node handles writing"
        )
    elif "filehandler" in msg_lower:
        return (
            "Use structured logging without file handlers in compute nodes:\n"
            "  # Configure logging in Effect node or entry point, not in compute\n"
            "  # Compute nodes should use standard logging without file handlers:\n"
            "  import logging\n"
            "  logger = logging.getLogger(__name__)\n"
            "  logger.info('Message')  # Handler configured externally"
        )
    return (
        "Move file I/O to an Effect node or pass content as input:\n"
        "  class NodeFileReaderEffect:\n"
        "      def read(self, path: Path) -> str:\n"
        "          return path.read_text()\n"
        "\n"
        "  class NodeYourCompute:\n"
        "      def process(self, content: str) -> Result:\n"
        "          # Pure computation, no I/O"
    )


def _generate_suggestion(rule: EnumIOAuditRule, message: str) -> str:
    """Generate a context-specific remediation suggestion based on the violation."""
    match rule:
        case EnumIOAuditRule.NET_CLIENT:
            return _generate_net_client_suggestion(message)
        case EnumIOAuditRule.ENV_ACCESS:
            return _generate_env_access_suggestion(message)
        case EnumIOAuditRule.FILE_IO:
            return _generate_file_io_suggestion(message)


@dataclass(frozen=True)
class ModelIOAuditViolation:
    """Represents a single I/O audit violation.

    Attributes:
        file: Path to the file containing the violation.
        line: Line number (1-indexed).
        column: Column number (0-indexed).
        rule: The rule that was violated.
        message: Human-readable description of the violation.
        suggestion: Context-specific remediation suggestion with code example.
    """

    file: Path
    line: int
    column: int
    rule: EnumIOAuditRule
    message: str
    suggestion: str = ""

    def __post_init__(self) -> None:
        """Generate suggestion if not provided."""
        if not self.suggestion:
            object.__setattr__(
                self, "suggestion", _generate_suggestion(self.rule, self.message)
            )

    def __str__(self) -> str:
        """Format as file:line: rule: message with remediation hint and suggestion."""
        base = f"{self.file}:{self.line}: {self.rule.value}: {self.message}"
        hint = REMEDIATION_HINTS.get(self.rule, "")
        lines = [base]
        if hint:
            lines.append(f"  -> Hint: {hint}")
        if self.suggestion:
            suggestion_lines = self.suggestion.split("\n")
            lines.append("  -> Suggestion:")
            for sline in suggestion_lines:
                lines.append(f"     {sline}")
        return "\n".join(lines)
