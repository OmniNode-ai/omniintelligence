#!/usr/bin/env bash
# ============================================================================
# Docker Compose Configuration Validator
# ============================================================================
# Purpose: Validate docker-compose files for syntax, security, and best practices
# Usage: ./scripts/validate-docker-compose.sh [--verbose]
# Exit codes:
#   0 - All validations passed
#   1 - One or more validations failed
# ============================================================================

# Errors are handled explicitly by tracking FAILED_CHECKS
# set -e would cause premature exit

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOYMENT_DIR="${PROJECT_ROOT}/deployment"
ENV_EXAMPLE="${PROJECT_ROOT}/.env.example"

# Validation state
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_COUNT=0
VERBOSE=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
    esac
done

# ============================================================================
# Output Functions
# ============================================================================

print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_section() {
    echo ""
    echo -e "${BLUE}▶ $1${NC}"
}

print_pass() {
    echo -e "  ${GREEN}✓${NC} $1"
    ((PASSED_CHECKS++))
    ((TOTAL_CHECKS++))
}

print_fail() {
    echo -e "  ${RED}✗${NC} $1"
    ((FAILED_CHECKS++))
    ((TOTAL_CHECKS++))
}

print_warn() {
    echo -e "  ${YELLOW}⚠${NC} $1"
    ((WARNING_COUNT++))
}

print_info() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "    ${NC}$1${NC}"
    fi
}

# ============================================================================
# Validation Functions
# ============================================================================

check_docker_compose_version() {
    print_section "Checking Docker Compose Version"

    if ! command -v docker &> /dev/null; then
        print_fail "Docker is not installed or not in PATH"
        return 1
    fi

    if ! docker compose version &> /dev/null; then
        print_fail "Docker Compose v2 is not available (use 'docker compose' not 'docker-compose')"
        return 1
    fi

    local version=$(docker compose version --short 2>/dev/null || echo "unknown")
    print_pass "Docker Compose v2 available (version: $version)"
    print_info "Using modern 'docker compose' syntax"
}

check_yaml_syntax() {
    local file="$1"
    local basename=$(basename "$file")

    print_section "Validating YAML Syntax: $basename"

    # Check if file exists
    if [[ ! -f "$file" ]]; then
        print_fail "File not found: $file"
        return 1
    fi

    # Basic YAML syntax check using docker compose config
    # Note: This validates the file can be parsed by Docker Compose
    local syntax_output
    syntax_output=$(docker compose -f "$file" config 2>&1)
    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        print_pass "YAML syntax is valid"
    else
        # Check if the failure is due to missing service dependencies (expected for multi-file setups)
        if echo "$syntax_output" | grep -q "depends on undefined service"; then
            print_pass "YAML syntax is valid (has external service dependencies)"
            print_info "Dependencies on services in other compose files detected"
        else
            print_fail "YAML syntax is invalid or file cannot be parsed"
            if [[ "$VERBOSE" == "true" ]]; then
                echo "$syntax_output" | head -20
            fi
            return 1
        fi
    fi
}

check_environment_variables() {
    local file="$1"
    local basename=$(basename "$file")

    print_section "Checking Environment Variables: $basename"

    # Extract all ${VAR:-default} and ${VAR} patterns
    local env_vars=$(grep -oE '\$\{[A-Z_][A-Z0-9_]*[:\-]?[^}]*\}' "$file" | sort -u || true)

    if [[ -z "$env_vars" ]]; then
        print_pass "No environment variable placeholders found"
        return 0
    fi

    local missing_vars=()
    local has_defaults=0
    local no_defaults=0

    # Source .env.example to check if variables are defined
    if [[ -f "$ENV_EXAMPLE" ]]; then
        # Extract variable names and check against .env.example
        while IFS= read -r var_pattern; do
            # Extract variable name (strip ${ and everything after : or })
            local var_name=$(echo "$var_pattern" | sed -E 's/\$\{([A-Z_][A-Z0-9_]*).*/\1/')

            # Check if it has a default value (contains :-)
            if echo "$var_pattern" | grep -q ':-'; then
                ((has_defaults++))
                print_info "Variable with default: $var_pattern"
            else
                ((no_defaults++))
                # Check if defined in .env.example
                if ! grep -q "^${var_name}=" "$ENV_EXAMPLE"; then
                    missing_vars+=("$var_name")
                fi
            fi
        done <<< "$env_vars"

        if [[ ${#missing_vars[@]} -gt 0 ]]; then
            print_warn "Variables not defined in .env.example: ${missing_vars[*]}"
            print_info "These variables must be set in runtime environment"
        fi

        print_pass "Found $has_defaults variables with defaults, $no_defaults without"
    else
        print_warn ".env.example not found, skipping variable validation"
    fi
}

check_hardcoded_secrets() {
    local file="$1"
    local basename=$(basename "$file")

    print_section "Checking for Hardcoded Secrets: $basename"

    local found_secrets=0

    # Look for environment variables with secret-like names that have hardcoded values
    # Pattern: Lines with PASSWORD/SECRET/TOKEN/API_KEY followed by : and a value (not ${...})
    # Exclude: Docker key names like "network_key:", "external_key:", etc.
    local secret_vars=(
        "PASSWORD[[:space:]]*:"
        "SECRET[[:space:]]*:"
        "TOKEN[[:space:]]*:"
        "API_KEY[[:space:]]*:"
        "_PASSWORD[[:space:]]*:"
        "_SECRET[[:space:]]*:"
        "_TOKEN[[:space:]]*:"
        "_API_KEY[[:space:]]*:"
    )

    for pattern in "${secret_vars[@]}"; do
        # Look for lines that match secret patterns but are NOT environment variable references
        # Exclude: lines with ${...}, comments, and Docker Compose field names
        local matches
        matches=$(grep -E "$pattern" "$file" | \
                  grep -v '\${' | \
                  grep -v '^[[:space:]]*#' | \
                  grep -v '^[[:space:]]*[a-z_]*_key[[:space:]]*:' | \
                  grep -v '^[[:space:]]*key[[:space:]]*:' || true)

        if [[ -n "$matches" ]]; then
            # Check if it's actually a hardcoded value (has a value after the colon that isn't a variable)
            local has_hardcoded
            has_hardcoded=$(echo "$matches" | grep -E ':[[:space:]]*["\047][^$]' || true)

            if [[ -n "$has_hardcoded" ]]; then
                ((found_secrets++))
                print_fail "Potential hardcoded secret found (pattern: $pattern)"
                if [[ "$VERBOSE" == "true" ]]; then
                    echo "$has_hardcoded" | head -3
                fi
            fi
        fi
    done

    # Special check for common insecure values
    if grep -qE '(PASSWORD|SECRET|TOKEN).*:[[:space:]]*["\047](password|admin|root|test|123)["\047]' "$file"; then
        print_fail "Insecure default password found (password/admin/root/test/123)"
        ((found_secrets++))
    fi

    if [[ $found_secrets -eq 0 ]]; then
        print_pass "No hardcoded secrets detected"
    else
        print_fail "Found $found_secrets potential hardcoded secrets"
        return 1
    fi
}

check_port_conflicts() {
    local file="$1"
    local basename=$(basename "$file")

    print_section "Checking Port Conflicts: $basename"

    # Extract all port mappings (host:container format)
    local ports
    ports=$(grep -E '^[[:space:]]*-[[:space:]]*["\047]?[0-9]+:[0-9]+' "$file" | \
            sed -E 's/.*"([0-9]+):[0-9]+".*/\1/' | \
            sed -E 's/.*-[[:space:]]*([0-9]+):[0-9]+.*/\1/' | \
            sort -n || true)

    if [[ -z "$ports" ]]; then
        print_warn "No port mappings found (services may be internal only)"
        return 0
    fi

    # Check for duplicates
    local duplicates=$(echo "$ports" | uniq -d)

    if [[ -n "$duplicates" ]]; then
        print_fail "Duplicate port mappings found: $duplicates"
        return 1
    else
        local port_count=$(echo "$ports" | wc -l | tr -d ' ')
        print_pass "No port conflicts detected ($port_count unique ports)"
    fi

    # List ports for reference
    if [[ "$VERBOSE" == "true" ]]; then
        echo "$ports" | while read -r port; do
            print_info "Port: $port"
        done
    fi
}

check_network_references() {
    local file="$1"
    local basename=$(basename "$file")

    print_section "Checking Network References: $basename"

    # Extract network references
    local networks=$(grep -A 5 '^[[:space:]]*networks:' "$file" | \
                    grep -E '^[[:space:]]*-[[:space:]]*[a-z]' | \
                    sed -E 's/.*-[[:space:]]*([a-z0-9_-]+).*/\1/' || true)

    if [[ -z "$networks" ]]; then
        print_warn "No network references found"
        return 0
    fi

    local external_networks=0
    local internal_networks=0

    while IFS= read -r network; do
        [[ -z "$network" ]] && continue

        # Check if network is marked as external
        if grep -q "name: $network" "$file" && grep -A 1 "name: $network" "$file" | grep -q "external: true"; then
            ((external_networks++))
            print_info "External network: $network"
        else
            ((internal_networks++))
            print_info "Internal network: $network"
        fi
    done <<< "$networks"

    print_pass "Found $internal_networks internal, $external_networks external networks"

    # Check for common external network patterns
    if echo "$networks" | grep -q "omninode-bridge"; then
        print_info "Uses OmniNode Bridge external networks (expected for remote connectivity)"
    fi
}

check_service_dependencies() {
    local file="$1"
    local basename=$(basename "$file")

    print_section "Checking Service Dependencies: $basename"

    # Extract service names
    local services=$(grep -E '^[[:space:]]{2}[a-z]' "$file" | \
                    grep -v '^[[:space:]]*#' | \
                    sed -E 's/^[[:space:]]*([a-z0-9_-]+):.*/\1/' | \
                    grep -v -E '^(version|services|networks|volumes|name)$' || true)

    if [[ -z "$services" ]]; then
        print_warn "No services found in file"
        return 0
    fi

    local service_count=$(echo "$services" | wc -l | tr -d ' ')
    print_pass "Found $service_count services"

    # Check for depends_on references to non-existent services
    local depends_errors=0
    while IFS= read -r service; do
        [[ -z "$service" ]] && continue

        # Extract depends_on for this service
        local depends=$(sed -n "/^[[:space:]]*${service}:/,/^[[:space:]]*[a-z]/p" "$file" | \
                       grep -A 10 "depends_on:" | \
                       grep -E '^[[:space:]]{4,}[a-z]' | \
                       sed -E 's/^[[:space:]]*([a-z0-9_-]+):.*/\1/' || true)

        if [[ -n "$depends" ]]; then
            while IFS= read -r dep; do
                [[ -z "$dep" ]] && continue

                # Check if dependency exists in services list
                if ! echo "$services" | grep -q "^${dep}$"; then
                    print_warn "Service '$service' depends on '$dep' which is not defined in this file"
                    print_info "This is OK if '$dep' is defined in another compose file or is external"
                fi
            done <<< "$depends"
        fi
    done <<< "$services"
}

check_healthchecks() {
    local file="$1"
    local basename=$(basename "$file")

    print_section "Checking Health Checks: $basename"

    # Count services with healthchecks
    local healthcheck_count=$(grep -c "healthcheck:" "$file" || echo "0")

    if [[ $healthcheck_count -eq 0 ]]; then
        print_warn "No health checks defined (recommended for production services)"
    else
        print_pass "Found $healthcheck_count health checks"
    fi

    # Check for common healthcheck issues
    if grep -q "test:.*curl.*localhost" "$file"; then
        print_info "Uses curl for health checks (ensure curl is in container)"
    fi

    if grep -q "test:.*wget" "$file"; then
        print_info "Uses wget for health checks (ensure wget is in container)"
    fi
}

check_resource_limits() {
    local file="$1"
    local basename=$(basename "$file")

    print_section "Checking Resource Limits: $basename"

    # Count services with resource limits
    local resource_count
    resource_count=$(grep -c "resources:" "$file" 2>/dev/null || echo "0")
    # Ensure we have a single number
    resource_count=$(echo "$resource_count" | head -1 | tr -d '[:space:]')

    if [[ $resource_count -eq 0 ]]; then
        print_warn "No resource limits defined (recommended for production)"
    else
        print_pass "Found $resource_count services with resource limits"
    fi
}

validate_compose_config() {
    local file="$1"
    local basename=$(basename "$file")

    print_section "Validating Compose Configuration: $basename"

    # Source .env.example for validation
    if [[ -f "$ENV_EXAMPLE" ]]; then
        print_info "Using .env.example for validation"
        local validation_output
        validation_output=$(docker compose --env-file "$ENV_EXAMPLE" -f "$file" config 2>&1)
        local exit_code=$?

        if [[ $exit_code -eq 0 ]]; then
            print_pass "Configuration validates successfully with .env.example"
        else
            # Check if the failure is due to missing service dependencies (expected for multi-file setups)
            if echo "$validation_output" | grep -q "depends on undefined service"; then
                print_warn "File has dependencies on services defined in other compose files"
                print_info "This is expected for multi-file compose setups"
            else
                print_fail "Configuration validation failed with .env.example"
                if [[ "$VERBOSE" == "true" ]]; then
                    echo "$validation_output" | head -20
                fi
                return 1
            fi
        fi
    else
        print_warn ".env.example not found, skipping full config validation"
    fi
}

# ============================================================================
# Main Validation Loop
# ============================================================================

main() {
    print_header "Docker Compose Configuration Validator"
    echo "Project: $(basename "$PROJECT_ROOT")"
    echo "Deployment Directory: $DEPLOYMENT_DIR"
    echo ""

    # Find all docker-compose files
    local compose_files=()

    if [[ -d "$DEPLOYMENT_DIR" ]]; then
        while IFS= read -r file; do
            compose_files+=("$file")
        done < <(find "$DEPLOYMENT_DIR" -name "docker-compose*.yml" -type f | sort)
    fi

    # Also check root directory
    while IFS= read -r file; do
        compose_files+=("$file")
    done < <(find "$PROJECT_ROOT" -maxdepth 1 -name "docker-compose*.yml" -type f | sort)

    if [[ ${#compose_files[@]} -eq 0 ]]; then
        echo -e "${RED}Error: No docker-compose files found${NC}"
        exit 1
    fi

    echo "Found ${#compose_files[@]} docker-compose files to validate"
    echo ""

    # Check Docker Compose version once
    check_docker_compose_version

    # Validate each file
    for file in "${compose_files[@]}"; do
        echo ""
        print_header "Validating: $(basename "$file")"

        # Run all validation checks
        check_yaml_syntax "$file" || true
        check_environment_variables "$file" || true
        check_hardcoded_secrets "$file" || true
        check_port_conflicts "$file" || true
        check_network_references "$file" || true
        check_service_dependencies "$file" || true
        check_healthchecks "$file" || true
        check_resource_limits "$file" || true
        validate_compose_config "$file" || true
    done

    # Print summary
    echo ""
    print_header "Validation Summary"
    echo ""
    echo -e "Total Checks:    ${TOTAL_CHECKS}"
    echo -e "${GREEN}Passed:${NC}          ${PASSED_CHECKS}"
    echo -e "${RED}Failed:${NC}          ${FAILED_CHECKS}"
    echo -e "${YELLOW}Warnings:${NC}        ${WARNING_COUNT}"
    echo ""

    if [[ $FAILED_CHECKS -eq 0 ]]; then
        echo -e "${GREEN}✓ All critical validations passed!${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}✗ $FAILED_CHECKS validation(s) failed${NC}"
        echo ""
        return 1
    fi
}

# Run main function
main "$@"
exit $?
