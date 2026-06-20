#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Use the production Agent-Reach adapter that MAX mode also calls.
exec ../../asagus-scraper-v3/backend/.venv/bin/python asagus_adapter.py "$@"
