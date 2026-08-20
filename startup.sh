#!/usr/bin/env bash
set -euo pipefail

# App Service Linux: site files live in wwwroot. Fall back to this script's directory.
if [[ -d /home/web_sierra/wwwroot && -f /home/web_sierra/wwwroot/app.py ]]; then
  cd /home/web_sierra/wwwroot
else
  cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

PORT="${PORT:-${WEBSITES_PORT:-8000}}"

echo "[startup] launching refresh_scheduler.py in background" >&2
# nohup so exec streamlit does not SIGHUP the sibling ingest process.
nohup python refresh_scheduler.py &

echo "[startup] exec streamlit on 0.0.0.0:${PORT}" >&2
# asgi_app.py wraps app.py and serves /health plus /robots.txt.
exec python -m streamlit run asgi_app.py \
  --server.port "$PORT" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --browser.gatherUsageStats false
