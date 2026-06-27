"""Ensure the cupriavidus_necator graph is loaded in a running TuringDB server.
Stdlib only (no turingdb SDK needed). Exit codes:
  0 graph ready · 1 server unreachable · 2 graph not on server
"""
import json
import os
import sys
import urllib.request

PORT = os.environ.get("TURING_API_PORT", "6666")
GRAPH = "cupriavidus_necator"
BASE = f"http://localhost:{PORT}"


def post(path: str):
    req = urllib.request.Request(BASE + path, data=b"", method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode())


try:
    post("/list_loaded_graphs")
except Exception as e:  # noqa: BLE001
    print(f"TuringDB not reachable on :{PORT} ({e})")
    sys.exit(1)

try:
    post(f"/load_graph?graph={GRAPH}")  # no-op if already loaded
except Exception:  # noqa: BLE001
    pass

try:
    avail = post("/list_avail_graphs").get("data", [])
except Exception:  # noqa: BLE001
    avail = []

if GRAPH not in avail:
    print(f"graph '{GRAPH}' not found on the server")
    sys.exit(2)

print(f"'{GRAPH}' ready")
