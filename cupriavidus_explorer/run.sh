#!/usr/bin/env bash
# Launch the Cupriavidus necator graph explorer.
#   1. checks a TuringDB server (:6666) has the cupriavidus_necator graph loaded
#      (loading it from ../cupriavidus_necator if needed)
#   2. starts the visualizer (Vite), proxying /api -> TuringDB
#
# Env: TURING_API_PORT (default 6666), TURING_FRONTEND_PORT (default 8080)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"   # materialhack repo root (holds graphs/)
APP="$HERE/app"
export TURING_API_PORT="${TURING_API_PORT:-6666}"
export TURING_FRONTEND_PORT="${TURING_FRONTEND_PORT:-8080}"

if [ ! -d "$APP/node_modules" ]; then
  echo "App not set up yet — run ./setup.sh first." >&2
  exit 1
fi

echo "→ Checking TuringDB (:$TURING_API_PORT) for cupriavidus_necator…"
if ! python3 "$HERE/ensure_graph.py"; then
  echo "→ Graph not available; attempting to load it from ../cupriavidus_necator…"
  if [ -f "$REPO/cupriavidus_necator/load_graph.py" ]; then
    python3 "$REPO/cupriavidus_necator/load_graph.py" --turing-dir "$REPO" --port "$TURING_API_PORT" || {
      cat >&2 <<EOF
Could not load the graph automatically. Make sure TuringDB is running, then:
    turingdb start -turing-dir "$REPO" -demon          # if not already up
    python cupriavidus_necator/load_graph.py --turing-dir "$REPO"
EOF
      exit 1
    }
  else
    echo "cupriavidus_necator/ not found in the repo — build that graph first." >&2
    exit 1
  fi
fi

echo "→ Building the explorer…"
cd "$APP"
npm run build
echo "→ Explorer at http://localhost:$TURING_FRONTEND_PORT  (API :$TURING_API_PORT, read-only gate on /api)"
exec node server.js   # gated production server (overlay/server.js). For local hacking use: npm run dev
