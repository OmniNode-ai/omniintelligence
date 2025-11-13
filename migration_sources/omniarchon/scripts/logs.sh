#!/bin/bash
# Quick log viewing commands

case "$1" in
    all)
        python3 scripts/view_pipeline_logs.py --tail 200
        ;;
    errors)
        python3 scripts/view_pipeline_logs.py --level ERROR
        ;;
    warnings)
        python3 scripts/view_pipeline_logs.py --level WARNING
        ;;
    trace)
        if [ -z "$2" ]; then
            echo "Usage: ./scripts/logs.sh trace <correlation-id>"
            exit 1
        fi
        python3 scripts/view_pipeline_logs.py --correlation-id "$2"
        ;;
    follow)
        python3 scripts/view_pipeline_logs.py --follow
        ;;
    intelligence)
        python3 scripts/view_pipeline_logs.py --service intelligence
        ;;
    bridge)
        python3 scripts/view_pipeline_logs.py --service bridge
        ;;
    consumer)
        python3 scripts/view_pipeline_logs.py --service consumer
        ;;
    search)
        python3 scripts/view_pipeline_logs.py --service search
        ;;
    *)
        echo "Usage: ./scripts/logs.sh {all|errors|warnings|trace|follow|intelligence|bridge|consumer|search}"
        echo ""
        echo "Examples:"
        echo "  ./scripts/logs.sh all              # View all recent logs"
        echo "  ./scripts/logs.sh errors           # Show only errors"
        echo "  ./scripts/logs.sh warnings         # Show only warnings"
        echo "  ./scripts/logs.sh trace abc-123    # Trace correlation ID"
        echo "  ./scripts/logs.sh follow           # Real-time tail"
        echo "  ./scripts/logs.sh intelligence     # Intelligence service logs"
        echo "  ./scripts/logs.sh bridge           # Bridge service logs"
        echo "  ./scripts/logs.sh consumer         # Kafka consumer logs"
        echo "  ./scripts/logs.sh search           # Search service logs"
        ;;
esac
