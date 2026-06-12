#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Use the unified adapter for ASAGUS integration
exec ../../asagus-scraper-v3/backend/.venv/bin/python asagus_adapter.py "$@"
