#!/usr/bin/env bash
# Wrapper script for running Download tools with proper environment coordination
set -euo pipefail

TOOL_ID="$1"
JOB_ID="${ASAGUS_JOB_ID:-manual}"
DOWNLOAD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_VENV_PYTHON="${DOWNLOAD_DIR}/../asagus-scraper-v3/backend/.venv/bin/python"

# Export coordinator path for tools to use
export ASAGUS_DOWNLOAD_ROOT="$DOWNLOAD_DIR"
export ASAGUS_COORDINATOR_AVAILABLE="1"

# Find the tool directory
TOOL_DIR=""
for dir in "$DOWNLOAD_DIR"/*/ ; do
    if [ -f "$dir/.asagus/config.json" ]; then
        TOOL_ID_IN_CONFIG=$(grep -oP '"tool_id"\s*:\s*"\K[^"]+' "$dir/.asagus/config.json" || echo "")
        if [ "$TOOL_ID_IN_CONFIG" = "$TOOL_ID" ]; then
            TOOL_DIR="$dir"
            break
        fi
    fi
done

if [ -z "$TOOL_DIR" ]; then
    echo "{\"tool_id\":\"$TOOL_ID\",\"status\":\"not_found\",\"message\":\"Tool directory not found\"}"
    exit 1
fi

# Check if run-asagus.sh exists
RUN_SCRIPT="$TOOL_DIR/run-asagus.sh"
if [ ! -f "$RUN_SCRIPT" ]; then
    echo "{\"tool_id\":\"$TOOL_ID\",\"status\":\"no_run_script\",\"message\":\"run-asagus.sh not found\"}"
    exit 1
fi

# Make sure it's executable
chmod +x "$RUN_SCRIPT"

# Set resource limits for browser tools
if [[ "$TOOL_ID" == "maps-scraper" || "$TOOL_ID" == "outreach-scraper" || "$TOOL_ID" == "maxun" ]]; then
    # Limit memory and CPU for browser tools
    ulimit -v 4194304 2>/dev/null || true  # 4GB virtual memory limit
fi

# Run the tool
cd "$TOOL_DIR"
exec bash "$RUN_SCRIPT" "$@"
