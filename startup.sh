#!/usr/bin/env bash
set -euo pipefail
PORT="${PORT:-${WEBSITES_PORT:-8000}}"
exec python -m streamlit run asgi_app.py \
  --server.port "$PORT" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --browser.gatherUsageStats false
