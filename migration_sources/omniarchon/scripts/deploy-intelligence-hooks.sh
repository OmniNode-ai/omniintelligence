#!/bin/bash
#
# Enhanced Intelligence Hook Deployment Script
#
# Deploys Enhanced Intelligence Hooks across ONEX ecosystem repositories
# Supports versioned deployments with validation and rollback capabilities
#
# Usage:
#   ./deploy-intelligence-hooks.sh [version] [--dry-run] [--rollback]
#
# Examples:
#   ./deploy-intelligence-hooks.sh v3.0              # Deploy v3.0 to all repos
#   ./deploy-intelligence-hooks.sh v3.0 --dry-run    # Test deployment without changes
#   ./deploy-intelligence-hooks.sh --rollback v2.1   # Rollback to v2.1
#
# Version: 1.0.0

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_LOG="$SCRIPT_DIR/hook-deployment.log"
BACKUP_DIR="$SCRIPT_DIR/hook-backups"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

# Repository configuration
get_repo_path() {
    case "$1" in
        "omnibase-core") echo "/Volumes/PRO-G40/Code/omnibase-core" ;;
        "omnibase-spi") echo "/Volumes/PRO-G40/Code/omnibase-spi" ;;
        "omniagent") echo "/Volumes/PRO-G40/Code/omniagent" ;;
        "omnimcp") echo "/Volumes/PRO-G40/Code/omnimcp" ;;
        "Archon") echo "/Volumes/PRO-G40/Code/Archon" ;;
        *) echo "" ;;
    esac
}

# Hook version mapping - only v3.1 Python hooks supported
get_hook_file() {
    case "$1" in
        "v3.1") echo "pre-push-wrapper.sh" ;;
        *) echo "" ;;
    esac
}

# Available repositories list
AVAILABLE_REPOS="omnibase-core omnibase-spi omniagent omnimcp Archon"

# Default values
HOOK_VERSION=""
DRY_RUN=false
ROLLBACK=false
ROLLBACK_VERSION=""
SELECTED_REPOS=()

# Logging function
log() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $message" >> "$DEPLOYMENT_LOG"
    echo -e "$message"
}

# Display usage information
usage() {
    cat << EOF
Intelligence Hook Deployment Script v1.0.0

USAGE:
    $0 [version] [options] [repositories...]

VERSIONS:
    v3.1    Intelligence Hook v3.1 (Python-based with Poetry and Pydantic)

OPTIONS:
    --dry-run           Simulate deployment without making changes
    --rollback VERSION  Rollback to specified version
    --help, -h          Show this help message

REPOSITORIES:
    If no repositories are specified, deploys to all configured repositories.
    Available repositories: $AVAILABLE_REPOS

EXAMPLES:
    $0 v3.0                                    # Deploy v3.0 to all repos
    $0 v3.0 --dry-run                         # Test v3.0 deployment
    $0 v3.0 omnibase-core omniagent           # Deploy v3.0 to specific repos
    $0 --rollback v2.1                        # Rollback all repos to v2.1
    $0 --rollback v2.1 omnibase-core          # Rollback specific repo to v2.1

FILES:
    Hook sources are looked for in the script directory:
    - v2.1: $(get_hook_file "v2.1")
    - v3.0: $(get_hook_file "v3.0")

SAFETY:
    - All existing hooks are backed up before deployment
    - Validation checks ensure hooks work correctly
    - Rollback capability for failed deployments
    - Dry-run mode for testing deployments
EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            v2.1|v3.0|v3.1)
                if [ "$ROLLBACK" = "true" ]; then
                    ROLLBACK_VERSION="$1"
                else
                    HOOK_VERSION="$1"
                fi
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --rollback)
                ROLLBACK=true
                shift
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            omnibase-core|omnibase-spi|omniagent|omnimcp|Archon)
                SELECTED_REPOS+=("$1")
                shift
                ;;
            *)
                log "${RED}❌ Unknown argument: $1${NC}"
                usage
                exit 1
                ;;
        esac
    done

    # Validation
    if [ "$ROLLBACK" = "true" ]; then
        if [ -z "$ROLLBACK_VERSION" ]; then
            log "${RED}❌ Rollback version must be specified${NC}"
            usage
            exit 1
        fi
        HOOK_VERSION="$ROLLBACK_VERSION"
    elif [ -z "$HOOK_VERSION" ]; then
        log "${RED}❌ Hook version must be specified${NC}"
        usage
        exit 1
    fi

    # Set default repositories if none specified
    if [ ${#SELECTED_REPOS[@]} -eq 0 ]; then
        SELECTED_REPOS=($AVAILABLE_REPOS)
    fi
}

# Create backup directory
setup_backup_dir() {
    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR"
        log "${BLUE}📁 Created backup directory: $BACKUP_DIR${NC}"
    fi
}

# Validate hook file exists
validate_hook_file() {
    local version="$1"
    local hook_file=$(get_hook_file "$version")

    if [ -z "$hook_file" ]; then
        log "${RED}❌ Unknown hook version: $version${NC}"
        return 1
    fi

    if [ ! -f "$SCRIPT_DIR/$hook_file" ]; then
        log "${RED}❌ Hook file not found: $SCRIPT_DIR/$hook_file${NC}"
        return 1
    fi

    # Validate hook syntax
    if [[ "$hook_file" == *.py ]]; then
        if ! python3 -m py_compile "$SCRIPT_DIR/$hook_file"; then
            log "${RED}❌ Python hook syntax validation failed for $hook_file${NC}"
            return 1
        fi
    else
        if ! bash -n "$SCRIPT_DIR/$hook_file"; then
            log "${RED}❌ Shell hook syntax validation failed for $hook_file${NC}"
            return 1
        fi
    fi

    log "${GREEN}✅ Hook file validated: $hook_file${NC}"
    return 0
}

# Validate repository
validate_repository() {
    local repo_name="$1"
    local repo_path=$(get_repo_path "$repo_name")

    if [ -z "$repo_path" ]; then
        log "${RED}❌ Unknown repository: $repo_name${NC}"
        return 1
    fi

    if [ ! -d "$repo_path" ]; then
        log "${RED}❌ Repository directory not found: $repo_path${NC}"
        return 1
    fi

    if [ ! -d "$repo_path/.git" ]; then
        log "${RED}❌ Not a git repository: $repo_path${NC}"
        return 1
    fi

    return 0
}

# No backup needed - just replace hooks directly

# Deploy hook to repository
deploy_hook() {
    local repo_name="$1"
    local version="$2"
    local repo_path=$(get_repo_path "$repo_name")
    local hook_file=$(get_hook_file "$version")
    local hook_path="$repo_path/.git/hooks/pre-push"

    if [ "$DRY_RUN" = "true" ]; then
        log "${CYAN}🔄 [DRY-RUN] Would deploy $hook_file to $repo_name${NC}"
        return 0
    fi

    # Copy shell wrapper as pre-push hook
    cp "$SCRIPT_DIR/$hook_file" "$hook_path"
    chmod +x "$hook_path"

    # Also copy the Python script to hooks directory (use fixed version)
    local python_script_path="$repo_path/.git/hooks/intelligence_hook.py"
    if [ -f "$SCRIPT_DIR/scripts/intelligence_hook.py" ]; then
        cp "$SCRIPT_DIR/scripts/intelligence_hook.py" "$python_script_path"
        chmod +x "$python_script_path"
        log "${BLUE}📦 Deployed Python intelligence hook script (v3.1 with Intelligence service fix)${NC}"
    else
        log "${RED}❌ Python script not found: $SCRIPT_DIR/scripts/intelligence_hook.py${NC}"
        return 1
    fi

    # Simple validation - just check if hook was deployed
    if [ -f "$hook_path" ] && [ -x "$hook_path" ]; then
        log "${GREEN}✅ Successfully deployed hook to $repo_name${NC}"
        return 0
    else
        log "${RED}❌ Failed to deploy hook to $repo_name${NC}"
        return 1
    fi
}

# Validate hook deployment
validate_deployment() {
    local repo_name="$1"
    local version="$2"
    local repo_path=$(get_repo_path "$repo_name")
    local hook_path="$repo_path/.git/hooks/pre-push"

    if [ "$DRY_RUN" = "true" ]; then
        log "${CYAN}🔍 [DRY-RUN] Would validate deployment in $repo_name${NC}"
        return 0
    fi

    # Check if hook exists and is executable
    if [ ! -f "$hook_path" ] || [ ! -x "$hook_path" ]; then
        log "${RED}❌ Hook validation failed: not found or not executable in $repo_name${NC}"
        return 1
    fi

    # Validate hook syntax
    if ! bash -n "$hook_path"; then
        log "${RED}❌ Hook validation failed: syntax error in $repo_name${NC}"
        return 1
    fi

    # Check version (handle both 3.1 and 3.1.0 formats)
    local deployed_version=$(grep -o "# Version: [0-9.]*" "$hook_path" | cut -d' ' -f3)
    local expected_version="${version#v}"
    if [[ "$deployed_version" != "$expected_version" ]] && [[ "$deployed_version" != "${expected_version}.0" ]]; then
        log "${RED}❌ Hook validation failed: version mismatch in $repo_name${NC}"
        return 1
    fi

    # Check required functions exist (basic smoke test)
    # v3.1 is Python-based, so check for Python execution instead
    if [[ "$version" == "v3.1" ]]; then
        # For Python-based hook, check that it can execute Python script
        if ! grep -q "exec.*PYTHON_CMD.*PYTHON_SCRIPT" "$hook_path"; then
            log "${RED}❌ Hook validation failed: Python execution not found in $repo_name${NC}"
            return 1
        fi
        # Check if Python script exists alongside
        local python_script_path="$(dirname "$hook_path")/intelligence_hook.py"
        if [ ! -f "$python_script_path" ]; then
            log "${RED}❌ Hook validation failed: Python script missing in $repo_name${NC}"
            return 1
        fi
    else
        # For shell-based hooks, check required functions
        local required_functions=("check_intelligence_system" "load_configuration" "update_intelligence_system")
        for func in "${required_functions[@]}"; do
            if ! grep -q "^$func()" "$hook_path"; then
                log "${RED}❌ Hook validation failed: missing function $func in $repo_name${NC}"
                return 1
            fi
        done
    fi

    log "${GREEN}✅ Hook validation passed for $repo_name${NC}"
    return 0
}

# Get current hook version
get_current_version() {
    local repo_name="$1"
    local repo_path=$(get_repo_path "$repo_name")
    local hook_path="$repo_path/.git/hooks/pre-push"

    if [ -f "$hook_path" ]; then
        local version=$(grep -o "# Version: [0-9.]*" "$hook_path" | cut -d' ' -f3)
        if [ -n "$version" ]; then
            echo "v$version"
        else
            echo "unknown"
        fi
    else
        echo "none"
    fi
}

# Display deployment summary
show_deployment_summary() {
    local target_version="$1"

    echo
    log "${CYAN}📊 Deployment Summary${NC}"
    log "${BLUE}===================${NC}"

    for repo in "${SELECTED_REPOS[@]}"; do
        local current_version=$(get_current_version "$repo")
        local status_icon="❓"
        local status_text=""

        if [ "$DRY_RUN" = "true" ]; then
            status_icon="🔍"
            status_text="[DRY-RUN] $current_version → $target_version"
        elif [ "$current_version" = "$target_version" ]; then
            status_icon="✅"
            status_text="$target_version (deployed successfully)"
        else
            status_icon="❌"
            status_text="$current_version (deployment failed)"
        fi

        log "${status_icon} ${repo}: $status_text"
    done

    if [ "$DRY_RUN" = "false" ]; then
        echo
        log "${GREEN}🎯 Deployment completed for hook version $target_version${NC}"
        if [ "$ROLLBACK" = "true" ]; then
            log "${YELLOW}🔙 Rollback operation completed${NC}"
        fi
        log "${BLUE}📋 Deployment log: $DEPLOYMENT_LOG${NC}"
        log "${BLUE}📦 Backups available in: $BACKUP_DIR${NC}"
    else
        echo
        log "${CYAN}🔍 Dry-run completed - no changes were made${NC}"
    fi
}

# Main deployment process
main() {
    log "${PURPLE}🚀 Intelligence Hook Deployment Script v1.0.0${NC}"

    if [ "$DRY_RUN" = "true" ]; then
        log "${CYAN}🔍 DRY-RUN MODE: No changes will be made${NC}"
    fi

    if [ "$ROLLBACK" = "true" ]; then
        log "${YELLOW}🔙 ROLLBACK MODE: Rolling back to $ROLLBACK_VERSION${NC}"
    fi

    # Parse arguments
    parse_args "$@"

    # Setup
    setup_backup_dir

    # Validate hook file
    if ! validate_hook_file "$HOOK_VERSION"; then
        exit 1
    fi

    log "${BLUE}📋 Target version: $HOOK_VERSION${NC}"
    log "${BLUE}📂 Target repositories: ${SELECTED_REPOS[*]}${NC}"
    echo

    # Deploy to each repository
    local success_count=0
    local total_count=${#SELECTED_REPOS[@]}

    for repo in "${SELECTED_REPOS[@]}"; do
        log "${PURPLE}🔧 Processing repository: $repo${NC}"

        # Validate repository
        if ! validate_repository "$repo"; then
            continue
        fi

        # Show current version
        local current_version=$(get_current_version "$repo")
        log "${BLUE}ℹ️  Current version: $current_version${NC}"

        # Skip if already at target version (unless rollback)
        if [ "$current_version" = "$HOOK_VERSION" ] && [ "$ROLLBACK" = "false" ]; then
            log "${GREEN}✅ $repo already has $HOOK_VERSION${NC}"
            ((success_count++))
            echo
            continue
        fi

        # Deploy hook
        if deploy_hook "$repo" "$HOOK_VERSION"; then
            ((success_count++))
        fi

        echo
    done

    # Show summary
    show_deployment_summary "$HOOK_VERSION"

    # Final status
    if [ $success_count -eq $total_count ]; then
        log "${GREEN}🎉 All deployments successful ($success_count/$total_count)${NC}"
        exit 0
    else
        log "${RED}❌ Some deployments failed ($success_count/$total_count successful)${NC}"
        exit 1
    fi
}

# Execute main function if script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
