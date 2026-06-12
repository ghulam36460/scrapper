#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec ../../asagus-scraper-v3/backend/.venv/bin/python asagus_adapter.py "$@"
