#!/bin/bash
set -e

echo "========================================"
echo "Pattern Sync Init Container"
echo "========================================"
echo "Starting pattern sync from PostgreSQL to Qdrant..."
echo ""

# Wait for dependencies
echo "Waiting for PostgreSQL..."
until pg_isready -h 192.168.86.200 -p 5436 -U postgres > /dev/null 2>&1; do
    echo "  PostgreSQL not ready, waiting 2 seconds..."
    sleep 2
done
echo "✅ PostgreSQL is ready"

echo "Waiting for Qdrant..."
until curl -s http://qdrant:6333/health > /dev/null 2>&1; do
    echo "  Qdrant not ready, waiting 2 seconds..."
    sleep 2
done
echo "✅ Qdrant is ready"

echo ""
echo "Starting pattern sync..."
echo ""

# Run sync script
python3 /app/scripts/sync_patterns_to_qdrant.py

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "✅ Pattern sync completed successfully"
    echo "========================================"
else
    echo ""
    echo "========================================"
    echo "❌ Pattern sync failed (exit code: $exit_code)"
    echo "========================================"
fi

exit $exit_code
