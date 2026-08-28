#!/usr/bin/env bash
# Real end-to-end run: real Open-Meteo fetch, real chart rendering, real
# litellm-proxy call to local-devstral-small2, real HTML + PDF output.
#
# Prerequisites:
#   - .venv set up and requirements installed (see README.md)
#   - .env populated with LITELLM_API_BASE / LITELLM_API_KEY (see .env.example)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  echo "error: .venv not found -- run: python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi
# shellcheck disable=SC1091
. .venv/bin/activate

python3 -m src.generate_report --out docs/sample-report --pdf

echo
echo "Running offline test suite..."
pytest -m "not live"

echo
echo "Verifying committed artifact against the acceptance bar..."
python3 scripts/verify_sample.py docs/sample-report
