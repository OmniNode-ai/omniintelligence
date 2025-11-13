#!/bin/bash
# Sync Intelligence Hook System to Claude hooks directory
# Copies files from Archon repo to ~/.claude/hooks
#
# Usage:
#   ./sync-hooks.sh              # Normal sync with confirmation
#   ./sync-hooks.sh --dry-run    # Show what would be copied
#   ./sync-hooks.sh --force      # Skip confirmation
#   ./sync-hooks.sh --rollback   # Restore from backup

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

SOURCE_DIR="/Volumes/PRO-G40/Code/Archon/services/intelligence/src/hooks"
TARGET_DIR="/Users/jonah/.claude/hooks"
BACKUP_DIR="$TARGET_DIR/.backups"
BACKUP_MARKER="$TARGET_DIR/.originals-backed-up"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Operation flags
DRY_RUN=false
FORCE=false
ROLLBACK=false
VERBOSE=false

# Validation results
VALIDATION_PASSED=true
VALIDATION_ERRORS=()

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

# Print formatted messages
print_header() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     Intelligence Hook System Sync - Archon → Claude         ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC}  $1"
}

print_info() {
    echo -e "${CYAN}→${NC} $1"
}

print_section() {
    echo ""
    echo -e "${BLUE}$1${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

validate_python_syntax() {
    local file="$1"
    if ! python3 -m py_compile "$file" 2>/dev/null; then
        VALIDATION_PASSED=false
        VALIDATION_ERRORS+=("Python syntax error in: $file")
        return 1
    fi
    return 0
}

validate_bash_syntax() {
    local file="$1"
    if ! bash -n "$file" 2>/dev/null; then
        VALIDATION_PASSED=false
        VALIDATION_ERRORS+=("Bash syntax error in: $file")
        return 1
    fi
    return 0
}

validate_imports() {
    local file="$1"
    local temp_dir=$(mktemp -d)

    # Copy file to temp location to test imports without affecting system
    cp "$file" "$temp_dir/"

    # Try to import the module
    if ! python3 -c "import sys; sys.path.insert(0, '$temp_dir'); import $(basename ${file%.py})" 2>/dev/null; then
        print_warning "Import validation failed for: $file (may need dependencies)"
    fi

    rm -rf "$temp_dir"
    return 0
}

check_source_exists() {
    if [[ ! -d "$SOURCE_DIR" ]]; then
        print_error "Source directory not found: $SOURCE_DIR"
        echo ""
        print_info "The Intelligence Hook System source directory doesn't exist yet."
        print_info "This directory will be created when the Intelligence Hook System"
        print_info "is integrated into the Archon Intelligence Service."
        echo ""
        print_info "Expected structure:"
        print_info "  $SOURCE_DIR/"
        print_info "  ├── lib/"
        print_info "  │   └── tracing/"
        print_info "  │       ├── __init__.py"
        print_info "  │       ├── tracer.py"
        print_info "  │       └── models.py"
        print_info "  ├── pre-tool-use-quality.sh"
        print_info "  └── lib/quality_enforcer.py"
        echo ""
        return 1
    fi
    return 0
}

validate_source_files() {
    print_section "Validating Source Files"

    local validation_count=0
    local error_count=0

    # Find all Python files
    while IFS= read -r file; do
        ((validation_count++))
        print_info "Validating: $(basename "$file")"

        if validate_python_syntax "$file"; then
            print_success "  Syntax OK"
        else
            ((error_count++))
            print_error "  Syntax FAILED"
        fi

        if [[ "$VERBOSE" == true ]]; then
            validate_imports "$file"
        fi
    done < <(find "$SOURCE_DIR" -type f -name "*.py" 2>/dev/null || true)

    # Find all bash scripts
    while IFS= read -r file; do
        ((validation_count++))
        print_info "Validating: $(basename "$file")"

        if validate_bash_syntax "$file"; then
            print_success "  Syntax OK"
        else
            ((error_count++))
            print_error "  Syntax FAILED"
        fi
    done < <(find "$SOURCE_DIR" -type f -name "*.sh" 2>/dev/null || true)

    echo ""
    if [[ $error_count -eq 0 ]]; then
        print_success "All $validation_count files validated successfully"
    else
        print_error "$error_count of $validation_count files failed validation"
        return 1
    fi

    return 0
}

# =============================================================================
# BACKUP & ROLLBACK FUNCTIONS
# =============================================================================

create_backup() {
    print_section "Creating Backup"

    if [[ -f "$BACKUP_MARKER" ]] && [[ "$FORCE" != true ]]; then
        print_info "Backup already exists (use --force to overwrite)"
        return 0
    fi

    mkdir -p "$BACKUP_DIR"

    local backup_count=0

    # Backup pre-tool-use-quality.sh
    if [[ -f "$TARGET_DIR/pre-tool-use-quality.sh" ]]; then
        if [[ "$DRY_RUN" == false ]]; then
            cp "$TARGET_DIR/pre-tool-use-quality.sh" "$BACKUP_DIR/"
        fi
        ((backup_count++))
        print_info "Backed up: pre-tool-use-quality.sh"
    fi

    # Backup quality_enforcer.py
    if [[ -f "$TARGET_DIR/lib/quality_enforcer.py" ]]; then
        if [[ "$DRY_RUN" == false ]]; then
            mkdir -p "$BACKUP_DIR/lib"
            cp "$TARGET_DIR/lib/quality_enforcer.py" "$BACKUP_DIR/lib/"
        fi
        ((backup_count++))
        print_info "Backed up: lib/quality_enforcer.py"
    fi

    # Backup tracing library
    if [[ -d "$TARGET_DIR/lib/tracing" ]]; then
        if [[ "$DRY_RUN" == false ]]; then
            mkdir -p "$BACKUP_DIR/lib"
            cp -r "$TARGET_DIR/lib/tracing" "$BACKUP_DIR/lib/"
        fi
        ((backup_count++))
        print_info "Backed up: lib/tracing/"
    fi

    if [[ "$DRY_RUN" == false ]]; then
        touch "$BACKUP_MARKER"
        echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" > "$BACKUP_MARKER"
    fi

    print_success "Backup complete ($backup_count items)"
}

rollback_from_backup() {
    print_section "Rolling Back from Backup"

    if [[ ! -f "$BACKUP_MARKER" ]]; then
        print_error "No backup found. Cannot rollback."
        return 1
    fi

    local rollback_count=0

    # Restore pre-tool-use-quality.sh
    if [[ -f "$BACKUP_DIR/pre-tool-use-quality.sh" ]]; then
        cp "$BACKUP_DIR/pre-tool-use-quality.sh" "$TARGET_DIR/"
        ((rollback_count++))
        print_info "Restored: pre-tool-use-quality.sh"
    fi

    # Restore quality_enforcer.py
    if [[ -f "$BACKUP_DIR/lib/quality_enforcer.py" ]]; then
        cp "$BACKUP_DIR/lib/quality_enforcer.py" "$TARGET_DIR/lib/"
        ((rollback_count++))
        print_info "Restored: lib/quality_enforcer.py"
    fi

    # Restore tracing library
    if [[ -d "$BACKUP_DIR/lib/tracing" ]]; then
        rm -rf "$TARGET_DIR/lib/tracing"
        cp -r "$BACKUP_DIR/lib/tracing" "$TARGET_DIR/lib/"
        ((rollback_count++))
        print_info "Restored: lib/tracing/"
    fi

    print_success "Rollback complete ($rollback_count items restored)"

    echo ""
    print_warning "Original backup preserved at: $BACKUP_DIR"
    print_info "To clean up backup, run: rm -rf $BACKUP_DIR"
}

# =============================================================================
# SYNC FUNCTIONS
# =============================================================================

sync_files() {
    print_section "Syncing Files"

    local sync_count=0

    # 1. Sync tracing library
    if [[ -d "$SOURCE_DIR/lib/tracing" ]]; then
        print_info "Syncing tracing library..."

        if [[ "$DRY_RUN" == false ]]; then
            mkdir -p "$TARGET_DIR/lib/tracing"
            cp -v "$SOURCE_DIR/lib/tracing/"*.py "$TARGET_DIR/lib/tracing/" 2>&1 | while read line; do
                if [[ "$VERBOSE" == true ]]; then
                    print_info "  $line"
                fi
            done
        else
            find "$SOURCE_DIR/lib/tracing" -name "*.py" | while read file; do
                print_info "  Would copy: $(basename "$file")"
            done
        fi
        ((sync_count++))
    else
        print_warning "Tracing library not found in source"
    fi

    # 2. Sync hook scripts
    if [[ -f "$SOURCE_DIR/pre-tool-use-quality.sh" ]]; then
        print_info "Syncing hook script..."

        if [[ "$DRY_RUN" == false ]]; then
            cp -v "$SOURCE_DIR/pre-tool-use-quality.sh" "$TARGET_DIR/"
        else
            print_info "  Would copy: pre-tool-use-quality.sh"
        fi
        ((sync_count++))
    else
        print_warning "pre-tool-use-quality.sh not found in source"
    fi

    # 3. Sync quality enforcer
    if [[ -f "$SOURCE_DIR/lib/quality_enforcer.py" ]]; then
        print_info "Syncing quality enforcer..."

        if [[ "$DRY_RUN" == false ]]; then
            mkdir -p "$TARGET_DIR/lib"
            cp -v "$SOURCE_DIR/lib/quality_enforcer.py" "$TARGET_DIR/lib/"
        else
            print_info "  Would copy: lib/quality_enforcer.py"
        fi
        ((sync_count++))
    else
        print_warning "quality_enforcer.py not found in source"
    fi

    # 4. Make scripts executable
    if [[ "$DRY_RUN" == false ]]; then
        if [[ -f "$TARGET_DIR/pre-tool-use-quality.sh" ]]; then
            chmod +x "$TARGET_DIR/pre-tool-use-quality.sh"
            print_info "Made executable: pre-tool-use-quality.sh"
        fi
    fi

    echo ""
    print_success "Sync complete ($sync_count items)"
}

# =============================================================================
# VERIFICATION FUNCTIONS
# =============================================================================

verify_installation() {
    print_section "Verifying Installation"

    local verified=true

    # Check files exist
    if [[ -f "$TARGET_DIR/pre-tool-use-quality.sh" ]]; then
        print_success "Hook script installed"
    else
        print_error "Hook script missing"
        verified=false
    fi

    if [[ -f "$TARGET_DIR/lib/quality_enforcer.py" ]]; then
        print_success "Quality enforcer installed"
    else
        print_error "Quality enforcer missing"
        verified=false
    fi

    if [[ -d "$TARGET_DIR/lib/tracing" ]]; then
        local tracing_files=$(find "$TARGET_DIR/lib/tracing" -name "*.py" | wc -l | tr -d ' ')
        print_success "Tracing library installed ($tracing_files files)"
    else
        print_warning "Tracing library not installed (optional)"
    fi

    # Test Python import
    if command -v python3 &> /dev/null; then
        if python3 -c "import sys; sys.path.insert(0, '$TARGET_DIR/lib'); from quality_enforcer import QualityEnforcer" 2>/dev/null; then
            print_success "Quality enforcer imports successfully"
        else
            print_warning "Quality enforcer import test failed (may need dependencies)"
        fi
    fi

    if [[ "$verified" == true ]]; then
        echo ""
        print_success "Installation verified successfully"
        return 0
    else
        echo ""
        print_error "Installation verification failed"
        return 1
    fi
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

show_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Sync Intelligence Hook System from Archon to Claude hooks directory

OPTIONS:
    --dry-run       Show what would be done without making changes
    --force         Skip confirmations and overwrite existing backups
    --rollback      Restore files from backup
    --verbose       Show detailed output
    -h, --help      Show this help message

EXAMPLES:
    $(basename "$0")                    # Normal sync with confirmation
    $(basename "$0") --dry-run          # Preview changes
    $(basename "$0") --force            # Sync without confirmation
    $(basename "$0") --rollback         # Restore from backup

DIRECTORIES:
    Source:  $SOURCE_DIR
    Target:  $TARGET_DIR
    Backup:  $BACKUP_DIR

EOF
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --rollback)
                ROLLBACK=true
                shift
                ;;
            --verbose|-v)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo ""
                show_usage
                exit 1
                ;;
        esac
    done
}

main() {
    parse_arguments "$@"

    print_header

    # Handle rollback mode
    if [[ "$ROLLBACK" == true ]]; then
        rollback_from_backup
        exit $?
    fi

    # Show mode
    if [[ "$DRY_RUN" == true ]]; then
        print_warning "Running in DRY-RUN mode (no changes will be made)"
        echo ""
    fi

    # Display paths
    print_info "Source: $SOURCE_DIR"
    print_info "Target: $TARGET_DIR"
    echo ""

    # Check source directory exists
    if ! check_source_exists; then
        exit 1
    fi

    # Validate source files
    if ! validate_source_files; then
        print_error "Validation failed. Cannot proceed with sync."
        echo ""
        print_info "Fix the validation errors and try again."
        exit 1
    fi

    # Create backup (first run only unless --force)
    if [[ "$DRY_RUN" == false ]]; then
        create_backup
    fi

    # Confirm before syncing (unless --force or --dry-run)
    if [[ "$FORCE" != true ]] && [[ "$DRY_RUN" != true ]]; then
        echo ""
        read -p "Proceed with sync? (y/N) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_warning "Sync cancelled"
            exit 0
        fi
    fi

    # Perform sync
    sync_files

    # Verify installation (unless dry-run)
    if [[ "$DRY_RUN" == false ]]; then
        verify_installation
    fi

    # Final message
    echo ""
    if [[ "$DRY_RUN" == true ]]; then
        print_info "DRY-RUN complete. Run without --dry-run to apply changes."
    else
        print_success "Intelligence Hook System sync complete!"
        echo ""
        print_info "Next steps:"
        print_info "  1. Test hooks in Claude Code"
        print_info "  2. Check logs: tail -f ~/.claude/hooks/logs/quality_enforcer.log"
        print_info "  3. To rollback: $0 --rollback"
    fi
}

# =============================================================================
# ENTRY POINT
# =============================================================================

main "$@"
