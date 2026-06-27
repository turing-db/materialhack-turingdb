#!/usr/bin/env bash
# Container entrypoint: run TuringDB + the gated UI in one container.
#
# TuringDB is started in the FOREGROUND and supervised as a background child
# (NOT `-demon`): demon-mode double-forks and detaches, which leaves the
# container's main process with nothing to watch (so the platform thinks it
# exited) and can leave a stale lock on restart. Both processes are children of
# this script; if either dies we exit so the platform restarts us.
#
# stdin is held open (< <(tail -f /dev/null)): the foreground launcher treats a
# closed stdin (the default for a detached/background process) as EOF and shuts
# the server down — keeping stdin open prevents that without daemonising.
set -uo pipefail
export PATH="/opt/venv/bin:${PATH}"
PORT="${PORT:-8080}"
APP="/app/cupriavidus_explorer/app"

echo "[start] launching TuringDB (foreground, supervised — no -demon)…"
turingdb start -turing-dir /app -load cupriavidus_necator < <(tail -f /dev/null) &
TDB=$!

echo "[start] waiting for TuringDB on :6666…"
for _ in $(seq 1 90); do
  if curl -sf -X POST http://localhost:6666/list_loaded_graphs >/dev/null 2>&1; then
    echo "[start] TuringDB ready"; break
  fi
  kill -0 "$TDB" 2>/dev/null || { echo "[start] TuringDB exited during startup"; exit 1; }
  sleep 1
done

echo "[start] launching gated UI on :$PORT (proxy /api -> :6666, read-only)…"
cd "$APP"
TURING_FRONTEND_PORT="$PORT" TURING_API_PORT=6666 READONLY_GRAPHS=cupriavidus_necator node server.js &
NODE=$!

# If either process exits, tear down so the platform restarts a clean container.
wait -n "$TDB" "$NODE"
echo "[start] a managed process exited — shutting down"
kill "$TDB" "$NODE" 2>/dev/null || true
exit 1
