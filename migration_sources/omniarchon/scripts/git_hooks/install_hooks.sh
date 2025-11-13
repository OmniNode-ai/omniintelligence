#!/usr/bin/env bash
#
# Git Hook Installation Script
#
# Installs pre-commit hooks for incremental tree stamping.
# Uses pre-commit framework for easy management and updates.
#
# Usage:
#   ./scripts/git_hooks/install_hooks.sh [--uninstall]
#
# Requirements:
#   - Python 3.12+
#   - pre-commit (pip install pre-commit)
#   - aiokafka (pip install aiokafka)
#   - PyYAML (pip install pyyaml)
#
# Created: 2025-10-27

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${GREEN}=== Git Hook Installation ===${NC}"
echo "Project: $PROJECT_ROOT"
echo ""

# ==============================================================================
# Check Requirements
# ==============================================================================

check_requirements() {
    echo "Checking requirements..."

    # Check Python version
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 not found${NC}"
        echo "Please install Python 3.12+ to use incremental tree stamping"
        exit 1
    fi

    python_version=$(python3 --version | cut -d' ' -f2)
    echo "✅ Python: $python_version"

    # Check pre-commit
    if ! command -v pre-commit &> /dev/null; then
        echo -e "${YELLOW}⚠️  pre-commit not found${NC}"
        echo "Installing pre-commit..."
        pip3 install pre-commit
    fi

    pre_commit_version=$(pre-commit --version | cut -d' ' -f2)
    echo "✅ pre-commit: $pre_commit_version"

    # Check aiokafka (optional - will warn but not fail)
    if python3 -c "import aiokafka" 2>/dev/null; then
        echo "✅ aiokafka: installed"
    else
        echo -e "${YELLOW}⚠️  aiokafka not found${NC}"
        echo "   Kafka event publishing will not work"
        echo "   Install with: pip install aiokafka"
    fi

    # Check PyYAML (optional - will use defaults)
    if python3 -c "import yaml" 2>/dev/null; then
        echo "✅ PyYAML: installed"
    else
        echo -e "${YELLOW}⚠️  PyYAML not found${NC}"
        echo "   Config file will not be loaded (using defaults)"
        echo "   Install with: pip install pyyaml"
    fi

    echo ""
}

# ==============================================================================
# Install Hooks
# ==============================================================================

install_hooks() {
    echo "Installing pre-commit hooks..."

    cd "$PROJECT_ROOT"

    # Install pre-commit hooks
    pre-commit install --install-hooks

    echo -e "${GREEN}✅ Pre-commit hooks installed${NC}"
    echo ""

    # Make hook script executable
    chmod +x "$SCRIPT_DIR/incremental_stamp.py"
    echo "✅ Hook script is executable"
    echo ""

    # Show configuration
    if [ -f "$SCRIPT_DIR/config.yaml" ]; then
        echo "Configuration file: $SCRIPT_DIR/config.yaml"
        echo ""
        echo "Key settings:"
        echo "  - enabled: $(grep '^enabled:' "$SCRIPT_DIR/config.yaml" | awk '{print $2}')"
        echo "  - async_mode: $(grep '^async_mode:' "$SCRIPT_DIR/config.yaml" | awk '{print $2}')"
        echo "  - kafka_enabled: $(grep '^kafka_enabled:' "$SCRIPT_DIR/config.yaml" | awk '{print $2}')"
        echo ""
    else
        echo -e "${YELLOW}⚠️  Configuration file not found${NC}"
        echo "   Using default configuration"
        echo "   Create $SCRIPT_DIR/config.yaml to customize"
        echo ""
    fi

    # Test dry run
    echo "Testing hook (dry run)..."
    if python3 "$SCRIPT_DIR/incremental_stamp.py" --dry-run --verbose 2>&1 | head -20; then
        echo ""
        echo -e "${GREEN}✅ Hook test passed${NC}"
    else
        echo ""
        echo -e "${YELLOW}⚠️  Hook test showed warnings (this is normal if no staged files)${NC}"
    fi
    echo ""

    # Success message
    echo -e "${GREEN}=== Installation Complete ===${NC}"
    echo ""
    echo "The incremental tree stamping hook is now active."
    echo ""
    echo "What happens now:"
    echo "  1. When you commit changes, the hook runs automatically"
    echo "  2. Changed files are detected and filtered"
    echo "  3. An event is published to Kafka for async stamping"
    echo "  4. The commit proceeds without waiting (<2s overhead)"
    echo ""
    echo "Configuration:"
    echo "  - Enable/disable: Edit $SCRIPT_DIR/config.yaml"
    echo "  - Bypass temporarily: git commit --no-verify"
    echo "  - Uninstall: ./scripts/git_hooks/install_hooks.sh --uninstall"
    echo ""
}

# ==============================================================================
# Uninstall Hooks
# ==============================================================================

uninstall_hooks() {
    echo "Uninstalling pre-commit hooks..."

    cd "$PROJECT_ROOT"

    # Uninstall pre-commit hooks
    pre-commit uninstall

    echo -e "${GREEN}✅ Pre-commit hooks uninstalled${NC}"
    echo ""
    echo "Note: The hook configuration remains in .pre-commit-config.yaml"
    echo "      You can reinstall at any time with: ./scripts/git_hooks/install_hooks.sh"
    echo ""
}

# ==============================================================================
# Main
# ==============================================================================

main() {
    # Check for uninstall flag
    if [ "$1" == "--uninstall" ]; then
        uninstall_hooks
        exit 0
    fi

    # Check requirements
    check_requirements

    # Install hooks
    install_hooks
}

# Run main function
main "$@"
