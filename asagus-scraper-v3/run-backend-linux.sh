#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
fi

cd backend

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ "${ASAGUS_RELOAD:-0}" = "1" ]; then
python -m uvicorn asagus.main:app --reload --host 127.0.0.1 --port 8000
fi

python -m uvicorn asagus.main:app --host 127.0.0.1 --port 8000
