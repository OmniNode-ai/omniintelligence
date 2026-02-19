# SPDX-License-Identifier: Apache-2.0
"""EnumContractErrorType - error type enum for contract validation."""

from __future__ import annotations

from enum import StrEnum


class EnumContractErrorType(StrEnum):
    """
    Enumeration of contract validation error types.

    Values are string-based for easy serialization and integration with
    error handling pipelines.
    """

    MISSING_FIELD = "missing_field"
    INVALID_VALUE = "invalid_value"
    INVALID_TYPE = "invalid_type"
    INVALID_ENUM = "invalid_enum"
    VALIDATION_ERROR = "validation_error"
    FILE_NOT_FOUND = "file_not_found"
    NOT_A_FILE = "not_a_file"
    FILE_READ_ERROR = "file_read_error"
    FILE_TOO_LARGE = "file_too_large"
    EMPTY_FILE = "empty_file"
    YAML_PARSE_ERROR = "yaml_parse_error"
    UNKNOWN_CONTRACT_TYPE = "unknown_contract_type"
    UNEXPECTED_ERROR = "unexpected_error"
    RESERVED_IDENTIFIER = "reserved_identifier"
