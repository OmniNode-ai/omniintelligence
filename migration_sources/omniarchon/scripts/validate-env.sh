#!/bin/bash
# ==============================================================================
# OmniArchon Environment Variable Validation Script
# ==============================================================================
# Validates that all required environment variables are set correctly
# Usage: ./scripts/validate-env.sh [env-file]
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default env file
ENV_FILE="${1:-.env}"

# Check if file exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Error: Environment file not found: $ENV_FILE${NC}"
    echo "Usage: $0 [env-file]"
    echo ""
    echo "Available templates:"
    echo "  • .env.development - Development environment"
    echo "  • .env.staging     - Staging environment"
    echo "  • .env.production  - Production environment"
    echo ""
    echo "Quick start: cp .env.development .env"
    exit 1
fi

echo "=========================================================="
echo "OmniArchon Environment Validation"
echo "=========================================================="
echo "Validating: $ENV_FILE"
echo ""

# Required variables for all environments
REQUIRED_VARS=(
    "ENVIRONMENT"
    "LOG_LEVEL"
    # Databases
    "POSTGRES_HOST"
    "POSTGRES_PORT"
    "POSTGRES_PASSWORD"
    "KAFKA_BOOTSTRAP_SERVERS"
    "QDRANT_URL"
    "MEMGRAPH_URI"
    "VALKEY_PASSWORD"
    # AI/ML
    "OLLAMA_BASE_URL"
)

# Variables that should NOT be placeholders
PLACEHOLDER_CHECKS=(
    "POSTGRES_PASSWORD:<set_password>:<CHANGE_ME>:<your_password>"
    "VALKEY_PASSWORD:<set_password>:<CHANGE_ME>:<your_password>"
    "OPENAI_API_KEY:<set_your_key>:<CHANGE_ME>"
)

# Load environment file
set +e
set -a
source "$ENV_FILE" 2>/dev/null
SOURCE_EXIT=$?
set +a
set -e

if [ $SOURCE_EXIT -ne 0 ]; then
    echo -e "${RED}❌ Error: Failed to source environment file${NC}"
    echo "   The file may contain syntax errors"
    exit 1
fi

# Check each required variable
MISSING_VARS=()
PLACEHOLDER_VARS=()
EMPTY_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    value="${!var}"

    if [ -z "$value" ]; then
        EMPTY_VARS+=("$var")
    else
        # Check for placeholder values
        for check in "${PLACEHOLDER_CHECKS[@]}"; do
            var_name="${check%%:*}"
            placeholders="${check#*:}"

            if [ "$var" == "$var_name" ]; then
                IFS=':' read -ra PLACEHOLDERS <<< "$placeholders"
                for placeholder in "${PLACEHOLDERS[@]}"; do
                    if [[ "$value" == *"$placeholder"* ]]; then
                        PLACEHOLDER_VARS+=("$var (contains: $placeholder)")
                        break
                    fi
                done
            fi
        done
    fi
done

# Additional validation checks
echo "Running validation checks..."
echo ""

# Check 1: Environment value
case "$ENVIRONMENT" in
    development|staging|production)
        echo -e "${GREEN}✅ Environment: $ENVIRONMENT${NC}"
        ;;
    *)
        echo -e "${RED}❌ Invalid ENVIRONMENT value: $ENVIRONMENT${NC}"
        echo "   Must be: development, staging, or production"
        MISSING_VARS+=("ENVIRONMENT (invalid value)")
        ;;
esac

# Check 2: Kafka configuration
if [[ "$KAFKA_BOOTSTRAP_SERVERS" == *"<"*">"* ]] || [[ "$KAFKA_BOOTSTRAP_SERVERS" == *"CHANGE_ME"* ]]; then
    echo -e "${RED}❌ Kafka bootstrap servers not configured${NC}"
    PLACEHOLDER_VARS+=("KAFKA_BOOTSTRAP_SERVERS")
elif [[ ! "$KAFKA_BOOTSTRAP_SERVERS" == *":"* ]]; then
    echo -e "${RED}❌ Kafka bootstrap servers missing port: $KAFKA_BOOTSTRAP_SERVERS${NC}"
    echo "   Expected format: host:port (e.g., omninode-bridge-redpanda:9092)"
    PLACEHOLDER_VARS+=("KAFKA_BOOTSTRAP_SERVERS (invalid format)")
else
    echo -e "${GREEN}✅ Kafka: $KAFKA_BOOTSTRAP_SERVERS${NC}"
fi

# Check 3: PostgreSQL configuration
if [[ "$POSTGRES_HOST" == *"<"*">"* ]] || [[ "$POSTGRES_HOST" == *"CHANGE_ME"* ]]; then
    echo -e "${RED}❌ PostgreSQL host not configured${NC}"
    PLACEHOLDER_VARS+=("POSTGRES_HOST")
else
    echo -e "${GREEN}✅ PostgreSQL: $POSTGRES_HOST:$POSTGRES_PORT${NC}"

    # Validate PostgreSQL port
    case "$POSTGRES_PORT" in
        5432|5436)
            if [ "$POSTGRES_PORT" == "5432" ]; then
                echo -e "${BLUE}   ℹ️  Using internal Docker port (5432)${NC}"
            else
                echo -e "${BLUE}   ℹ️  Using external port (5436)${NC}"
            fi
            ;;
        *)
            echo -e "${YELLOW}   ⚠️  Unusual PostgreSQL port: $POSTGRES_PORT${NC}"
            echo "   Expected: 5432 (internal) or 5436 (external)"
            ;;
    esac
fi

# Check 4: Qdrant configuration
if [[ ! "$QDRANT_URL" == http* ]]; then
    echo -e "${RED}❌ Invalid Qdrant URL: $QDRANT_URL${NC}"
    echo "   Expected format: http://host:port (e.g., http://archon-qdrant:6333)"
    PLACEHOLDER_VARS+=("QDRANT_URL (invalid format)")
else
    echo -e "${GREEN}✅ Qdrant: $QDRANT_URL${NC}"
fi

# Check 5: Memgraph configuration
if [[ ! "$MEMGRAPH_URI" == bolt://* ]]; then
    echo -e "${RED}❌ Invalid Memgraph URI: $MEMGRAPH_URI${NC}"
    echo "   Expected format: bolt://host:port (e.g., bolt://archon-memgraph:7687)"
    PLACEHOLDER_VARS+=("MEMGRAPH_URI (invalid format)")
else
    echo -e "${GREEN}✅ Memgraph: $MEMGRAPH_URI${NC}"
fi

# Check 6: Ollama configuration
if [[ ! "$OLLAMA_BASE_URL" == http* ]]; then
    echo -e "${RED}❌ Invalid Ollama URL: $OLLAMA_BASE_URL${NC}"
    echo "   Expected format: http://host:port (e.g., http://192.168.86.200:11434)"
    PLACEHOLDER_VARS+=("OLLAMA_BASE_URL (invalid format)")
else
    echo -e "${GREEN}✅ Ollama: $OLLAMA_BASE_URL${NC}"
fi

# Check 7: Password strength (minimum 8 characters)
if [ ${#POSTGRES_PASSWORD} -lt 8 ]; then
    echo -e "${YELLOW}⚠️  Warning: POSTGRES_PASSWORD should be at least 8 characters${NC}"
fi

if [ ${#VALKEY_PASSWORD} -lt 8 ]; then
    echo -e "${YELLOW}⚠️  Warning: VALKEY_PASSWORD should be at least 8 characters${NC}"
fi

# Check 8: Embedding configuration validation
echo ""
echo "Embedding Configuration Validation:"

# Function to get expected dimensions for a model
# Using case statement instead of associative array to avoid bash 3.x issues with special characters
get_expected_dimensions() {
    local model="$1"
    # Strip any tag suffix (e.g., :latest, :v1)
    local model_base="${model%%:*}"

    case "$model_base" in
        "nomic-embed-text")
            echo "768"
            ;;
        "mxbai-embed-large")
            echo "1024"
            ;;
        "rjmalagon/gte-qwen2-1.5b-instruct-embed-f16")
            echo "1536"
            ;;
        "text-embedding-3-small")
            echo "1536"
            ;;
        "text-embedding-3-large")
            echo "3072"
            ;;
        "text-embedding-ada-002")
            echo "1536"
            ;;
        "text-embedding-004")
            echo "768"
            ;;
        *)
            echo ""
            ;;
    esac
}

if [ -z "$EMBEDDING_MODEL" ]; then
    echo -e "${RED}❌ EMBEDDING_MODEL not set${NC}"
    echo "   Vector operations will fail without embedding model configuration"
    EMPTY_VARS+=("EMBEDDING_MODEL")
elif [ -z "$EMBEDDING_DIMENSIONS" ]; then
    echo -e "${RED}❌ EMBEDDING_DIMENSIONS not set${NC}"
    echo "   Vector operations will fail without embedding dimensions configuration"
    EMPTY_VARS+=("EMBEDDING_DIMENSIONS")
else
    # Check if dimensions is a valid integer
    if ! [[ "$EMBEDDING_DIMENSIONS" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}❌ EMBEDDING_DIMENSIONS must be an integer: $EMBEDDING_DIMENSIONS${NC}"
        PLACEHOLDER_VARS+=("EMBEDDING_DIMENSIONS (invalid format)")
    elif [ "$EMBEDDING_DIMENSIONS" -le 0 ]; then
        echo -e "${RED}❌ EMBEDDING_DIMENSIONS must be positive: $EMBEDDING_DIMENSIONS${NC}"
        PLACEHOLDER_VARS+=("EMBEDDING_DIMENSIONS (invalid value)")
    else
        # Get expected dimensions for the model
        EXPECTED_DIMS=$(get_expected_dimensions "$EMBEDDING_MODEL")

        # Validate known model/dimension pairs
        if [ -n "$EXPECTED_DIMS" ]; then
            if [ "$EMBEDDING_DIMENSIONS" == "$EXPECTED_DIMS" ]; then
                echo -e "${GREEN}✅ Embedding config: $EMBEDDING_MODEL with $EMBEDDING_DIMENSIONS dimensions${NC}"
            else
                echo -e "${YELLOW}⚠️  Warning: $EMBEDDING_MODEL expects $EXPECTED_DIMS dimensions${NC}"
                echo "   but EMBEDDING_DIMENSIONS=$EMBEDDING_DIMENSIONS"
                echo "   This mismatch will cause vector search failures and indexing errors"
                echo "   Fix: Set EMBEDDING_DIMENSIONS=$EXPECTED_DIMS in $ENV_FILE"
            fi
        else
            echo -e "${YELLOW}⚠️  Warning: Unknown embedding model '$EMBEDDING_MODEL'${NC}"
            echo "   (using $EMBEDDING_DIMENSIONS dimensions)"
            echo "   Known models: nomic-embed-text, mxbai-embed-large, rjmalagon/gte-qwen2-1.5b-instruct-embed-f16,"
            echo "                 text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002, text-embedding-004"
            echo "   If this is a custom model, ensure EMBEDDING_DIMENSIONS matches model output"
        fi
    fi
fi

# Check 9: Production-specific validations
if [ "$ENVIRONMENT" == "production" ]; then
    echo ""
    echo "Production Environment Checks:"

    # Check for development passwords
    if [ "$POSTGRES_PASSWORD" == "omninode-bridge-postgres-dev-2024" ]; then
        echo -e "${RED}❌ Using development password in production!${NC}"
        PLACEHOLDER_VARS+=("POSTGRES_PASSWORD (development password)")
    fi

    if [ "$VALKEY_PASSWORD" == "archon_cache_2025" ]; then
        echo -e "${RED}❌ Using default Valkey password in production!${NC}"
        PLACEHOLDER_VARS+=("VALKEY_PASSWORD (default password)")
    fi

    # Check log level
    if [ "$LOG_LEVEL" == "debug" ]; then
        echo -e "${YELLOW}⚠️  Warning: Using debug logging in production${NC}"
        echo "   Recommended: LOG_LEVEL=warning or LOG_LEVEL=error"
    fi
fi

# Report results
echo ""
echo "=========================================================="
echo "Validation Results"
echo "=========================================================="

ERROR_COUNT=0

if [ ${#EMPTY_VARS[@]} -gt 0 ]; then
    echo -e "${RED}❌ Empty Variables (${#EMPTY_VARS[@]})${NC}"
    for var in "${EMPTY_VARS[@]}"; do
        echo "   - $var"
    done
    ERROR_COUNT=$((ERROR_COUNT + ${#EMPTY_VARS[@]}))
    echo ""
fi

if [ ${#PLACEHOLDER_VARS[@]} -gt 0 ]; then
    echo -e "${RED}❌ Placeholder/Invalid Values (${#PLACEHOLDER_VARS[@]})${NC}"
    for var in "${PLACEHOLDER_VARS[@]}"; do
        echo "   - $var"
    done
    ERROR_COUNT=$((ERROR_COUNT + ${#PLACEHOLDER_VARS[@]}))
    echo ""
fi

if [ $ERROR_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ All required variables are set and validated${NC}"
    echo ""
    echo "Configuration Summary:"
    echo "  • Environment:  $ENVIRONMENT"
    echo "  • Log Level:    $LOG_LEVEL"
    echo "  • Kafka:        $KAFKA_BOOTSTRAP_SERVERS"
    echo "  • PostgreSQL:   $POSTGRES_HOST:$POSTGRES_PORT"
    echo "  • Qdrant:       $QDRANT_URL"
    echo "  • Memgraph:     $MEMGRAPH_URI"
    echo "  • Ollama:       $OLLAMA_BASE_URL"
    echo ""
    echo -e "${GREEN}✅ Ready to deploy!${NC}"
    exit 0
else
    echo -e "${RED}❌ Validation failed with $ERROR_COUNT error(s)${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review missing/invalid variables above"
    echo "  2. Edit $ENV_FILE and set correct values"
    echo "  3. Re-run validation: $0 $ENV_FILE"
    echo ""
    echo "Quick fixes:"
    echo "  • Copy template: cp .env.development .env"
    echo "  • Set passwords: Edit POSTGRES_PASSWORD and VALKEY_PASSWORD"
    echo "  • Check CLAUDE.md for configuration details"
    echo ""
    exit 1
fi
