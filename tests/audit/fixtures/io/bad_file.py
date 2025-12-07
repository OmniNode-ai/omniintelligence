"""A node with file I/O violations.

This fixture demonstrates forbidden patterns:
- open() builtin
- pathlib.Path I/O methods
- io.open()
- logging.FileHandler

NOTE: This file intentionally contains violations for testing.
"""

# ruff: noqa: UP020

import io
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def read_config_file(path: str) -> str:
    """BAD: Reads file directly using open()."""
    # VIOLATION: open() builtin
    with open(path) as f:
        return f.read()


def write_output_file(path: str, content: str) -> None:
    """BAD: Writes file directly using open()."""
    # VIOLATION: open() builtin with write mode
    with open(path, "w") as f:
        f.write(content)


def read_with_pathlib(path: Path) -> str:
    """BAD: Reads file using pathlib."""
    # VIOLATION: Path.read_text()
    return path.read_text()


def write_with_pathlib(path: Path, content: str) -> None:
    """BAD: Writes file using pathlib."""
    # VIOLATION: Path.write_text()
    path.write_text(content)


def read_bytes_with_pathlib(path: Path) -> bytes:
    """BAD: Reads bytes using pathlib."""
    # VIOLATION: Path.read_bytes()
    return path.read_bytes()


def write_bytes_with_pathlib(path: Path, content: bytes) -> None:
    """BAD: Writes bytes using pathlib."""
    # VIOLATION: Path.write_bytes()
    path.write_bytes(content)


def open_with_pathlib(path: Path) -> str:
    """BAD: Opens file using pathlib."""
    # VIOLATION: Path.open()
    with path.open() as f:
        return f.read()


def read_with_io_open(path: str) -> str:
    """BAD: Reads file using io.open()."""
    # VIOLATION: io.open()
    with io.open(path) as f:
        return f.read()


def setup_file_logging() -> logging.Logger:
    """BAD: Sets up file-based logging in a node."""
    logger = logging.getLogger("node_logger")

    # VIOLATION: logging.FileHandler
    handler = logging.FileHandler("node.log")
    logger.addHandler(handler)

    return logger


def setup_rotating_file_logging() -> logging.Logger:
    """BAD: Sets up rotating file logging in a node."""
    logger = logging.getLogger("rotating_logger")

    # VIOLATION: RotatingFileHandler
    handler = RotatingFileHandler("node.log", maxBytes=1024, backupCount=3)
    logger.addHandler(handler)

    return logger
