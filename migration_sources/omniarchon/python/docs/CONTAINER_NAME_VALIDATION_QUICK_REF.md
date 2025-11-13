# Container Name Validation - Quick Reference

## TL;DR

**All container names are now validated to prevent command injection attacks.**

### Allowed Characters
```
a-z A-Z 0-9 _ - .
```

### Maximum Length
```
255 characters
```

---

## Valid Examples ✅

```python
"archon-mcp"              # Good: hyphens
"archon_server"           # Good: underscores
"archon.service"          # Good: dots
"container123"            # Good: numbers
"My-App_v1.2"             # Good: mixed allowed chars
```

---

## Invalid Examples ❌

```python
"evil; rm -rf /"          # Bad: semicolon (command separator)
"container && hack"       # Bad: shell operator
"test | pipe"             # Bad: pipe operator
"name $(cmd)"             # Bad: command substitution
"../etc/passwd"           # Bad: path traversal
"container space"         # Bad: space character
```

---

## Usage

### Import
```python
from src.server.services.container_health_monitor import (
    validate_container_name,
    InvalidContainerNameError
)
```

### Basic Validation
```python
try:
    validated = validate_container_name(user_input)
    # Safe to use in Docker commands
except InvalidContainerNameError as e:
    logger.error(f"Invalid container name: {e}")
    # Handle error
```

### In Methods
```python
def my_docker_operation(container_name: str):
    # Validate first
    validate_container_name(container_name)

    # Now safe to use
    subprocess.run(["docker", "inspect", container_name])
```

---

## What Gets Logged?

### Invalid Names
```
WARNING - Rejected invalid container name: 'evil; rm -rf /' (contains invalid characters)
```

### Exceptions
```python
InvalidContainerNameError: Invalid container name: 'evil; rm -rf /'.
Only alphanumeric, underscore, hyphen, and dot allowed.
```

---

## Testing

### Run Tests
```bash
# All validation tests
pytest tests/test_container_health_monitor.py -v

# Just validation
pytest tests/test_container_health_monitor.py::TestContainerNameValidation -v
```

### Quick Verification
```bash
# Test valid name
python -c "from src.server.services.container_health_monitor import validate_container_name; print(validate_container_name('archon-mcp'))"

# Test invalid name (should raise exception)
python -c "from src.server.services.container_health_monitor import validate_container_name; validate_container_name('evil; rm')"
```

---

## Security Rationale

**Why so strict?** Container names are used in subprocess commands. Without validation:

```python
# VULNERABLE CODE (before validation)
container_name = "evil; rm -rf /"
subprocess.run(["docker", "inspect", container_name])
# Could execute: docker inspect evil ; rm -rf /
```

```python
# SAFE CODE (with validation)
container_name = "evil; rm -rf /"
validate_container_name(container_name)  # ✅ Raises InvalidContainerNameError
# Attack prevented!
```

---

## Common Patterns

### Pattern 1: Validate Early
```python
def process_container(name: str):
    validate_container_name(name)  # First thing!
    # ... rest of logic
```

### Pattern 2: Graceful Handling
```python
containers = get_container_list()
for name in containers:
    try:
        validate_container_name(name)
        process_container(name)
    except InvalidContainerNameError:
        logger.warning(f"Skipping invalid: {name}")
        continue  # Skip, process others
```

### Pattern 3: User Feedback
```python
try:
    validate_container_name(user_input)
except InvalidContainerNameError as e:
    return {
        "error": "Invalid container name",
        "message": str(e),
        "allowed": "alphanumeric, _, -, ."
    }
```

---

## FAQ

### Q: Why not allow spaces?
**A**: Spaces can break command parsing and enable injection attacks.

### Q: Why only 255 chars?
**A**: Docker's limit for container names. Prevents buffer overflow attacks.

### Q: What if my container name is rejected?
**A**: Rename your container to use only allowed characters. All legitimate Docker names should pass.

### Q: Does this affect performance?
**A**: Negligible (<1ms). Regex validation is very fast.

### Q: What about existing containers?
**A**: They'll continue working. Only affects new validations.

---

## Need Help?

- **Full Docs**: See `CONTAINER_NAME_VALIDATION.md`
- **Tests**: See `tests/test_container_health_monitor.py`
- **Code**: See `src/server/services/container_health_monitor.py` (lines 39-140)

---

**Last Updated**: 2025-10-20
