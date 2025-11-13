# Container Name Validation - Security Documentation

**Purpose**: Prevent command injection attacks via container names in Docker operations.

## Overview

The Container Health Monitor now validates all container names before using them in subprocess commands. This prevents attackers from injecting malicious commands through crafted container names.

## Security Rules

### Allowed Characters
- **Alphanumeric**: `a-z`, `A-Z`, `0-9`
- **Special Characters**: `_` (underscore), `-` (hyphen), `.` (dot)
- **Pattern**: `^[a-zA-Z0-9_.-]+$`

### Constraints
- **Maximum Length**: 255 characters
- **Minimum Length**: 1 character (cannot be empty)
- **No Whitespace**: Spaces, tabs, newlines are rejected

## Implementation

### Validation Function

```python
def validate_container_name(name: str) -> str:
    """
    Validate container name to prevent command injection.

    Raises:
        InvalidContainerNameError: If name is invalid
    """
    if not name:
        raise InvalidContainerNameError("Container name cannot be empty")

    if len(name) > MAX_CONTAINER_NAME_LENGTH:
        raise InvalidContainerNameError(f"Container name too long...")

    if not CONTAINER_NAME_PATTERN.match(name):
        logger.warning(f"Rejected invalid container name: {name!r}")
        raise InvalidContainerNameError(f"Invalid container name: {name!r}...")

    return name
```

### Where Validation is Applied

1. **`get_container_health(container_name)`**
   - Validates before `docker inspect` command
   - Validates before `docker logs` command

2. **`get_container_logs(container_name)`**
   - Validates before `docker logs` command

3. **`get_all_containers_health()`**
   - Validates each container name from `docker ps` output
   - Skips invalid names with warning log
   - Continues processing valid containers

## Attack Prevention

### Command Injection Attempts Blocked

All the following malicious container names are **rejected**:

```python
# Shell metacharacters
"evil; rm -rf /"          # Semicolon command separator
"container && echo hack"  # AND operator
"test | cat /etc/passwd"  # Pipe operator
"name $(whoami)"          # Command substitution
"container`id`"           # Backtick substitution

# Path traversal
"../../../etc/passwd"     # Directory traversal
"test/slash"              # Forward slash

# Special characters
"container@service"       # At symbol
"test#hash"               # Hash/comment
"service$var"             # Dollar/variable expansion
"container%percent"       # Percent
"test&ampersand"          # Ampersand (background)

# Whitespace/control characters
"container space"         # Space
"test\ttab"               # Tab
"test\nmalicious"         # Newline
"container\x00null"       # Null byte

# Quotes (SQL/shell injection)
"name'DROP TABLE users"   # Single quote
"test\"injection"         # Double quote
```

### Valid Container Names Allowed

These legitimate container names are **accepted**:

```python
"archon-mcp"              # Hyphen separator
"archon_server"           # Underscore separator
"archon.service"          # Dot notation
"archon-service_1.0"      # Mixed allowed chars
"container123"            # Alphanumeric
"ABC123"                  # Uppercase
"test_container-v1.2.3"   # Version numbers
```

## Logging and Monitoring

### Warning Logs

Invalid container names trigger warning logs:

```python
logger.warning(
    f"Rejected invalid container name: {name!r} "
    "(contains invalid characters)"
)
```

### Error Handling

When validation fails:
- `InvalidContainerNameError` exception is raised
- Invalid names are logged with `logger.warning()`
- In `get_all_containers_health()`, invalid names are skipped gracefully

## Testing

### Test Coverage

20 comprehensive tests verify:

1. **Valid Names** (9 tests)
   - Standard Docker container names
   - Edge cases (single char, max length, consecutive special chars)
   - Mixed case and numeric-only names

2. **Invalid Names** (6 tests)
   - Command injection attempts (10 patterns)
   - Special characters (14 patterns)
   - Unicode characters (6 patterns)
   - Empty/whitespace names
   - Exceeding max length

3. **Integration** (3 tests)
   - `get_container_health()` validation
   - `get_container_logs()` validation
   - `get_all_containers_health()` skipping invalid names

4. **Documentation** (2 tests)
   - Security documentation presence
   - Error message clarity

### Running Tests

```bash
# Run all container health monitor tests
pytest tests/test_container_health_monitor.py -v

# Run only validation tests
pytest tests/test_container_health_monitor.py::TestContainerNameValidation -v

# Run with coverage
pytest tests/test_container_health_monitor.py --cov=src.server.services.container_health_monitor
```

## Security Best Practices

### Defense in Depth

1. **Input Validation** (this implementation)
   - Whitelist approach: only allow known-safe characters
   - Fail fast: reject invalid input before processing
   - Logging: track rejected attempts for security monitoring

2. **Subprocess Safety**
   - Always use list form of `subprocess.run()`: `["docker", "inspect", name]`
   - Never use shell=True with user input
   - Validate before passing to subprocess

3. **Error Handling**
   - Don't expose full error details to users
   - Log full errors server-side for debugging
   - Provide clear, actionable error messages

### Rationale for Allowed Characters

- **Alphanumeric**: Standard for all container names
- **Hyphen (`-`)**: Docker's preferred separator
- **Underscore (`_`)**: Common in container orchestration (Compose, Swarm)
- **Dot (`.`)**: Used for versioning and hierarchical names

All other characters are rejected to prevent:
- Command injection via shell metacharacters
- Path traversal via slashes
- Variable expansion via `$`, backticks
- Control character injection

## Performance Impact

- **Validation Time**: < 1ms per name (regex match)
- **Overhead**: Negligible compared to Docker subprocess calls (50-100ms)
- **Security Benefit**: Complete prevention of command injection attacks

## Compliance

This implementation follows security best practices:
- **OWASP**: Input validation, command injection prevention
- **CWE-78**: OS Command Injection mitigation
- **Docker Security**: Container name restrictions
- **Principle of Least Privilege**: Only allow necessary characters

## Maintenance

### Future Considerations

1. **Monitoring**: Track rejected container names in metrics
2. **Alerting**: Alert on repeated validation failures (potential attack)
3. **Audit**: Log all validation events for security audit trail
4. **Updates**: Review Docker's container naming rules for changes

### Contact

For security concerns or questions:
- File issue in project repository
- Tag with `security` label
- Include reproduction steps for suspected vulnerabilities

---

**Last Updated**: 2025-10-20
**Version**: 1.0
**Status**: Production
