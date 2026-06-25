#!/usr/bin/env python3
"""
load_full_jsonl.py
==================
Load the FULL million-node graph (produced by
`python data/expand_from_retrorules.py --full`) into TuringDB via the native
`LOAD JSONL` bulk path — the only sane way to ingest ~1.5M nodes (per-statement
CREATE would be ~1.5M queries).

What it does:
  1. copies data/retrorules_full/graph.jsonl into TuringDB's data dir
     (~/.turing/data by default — `LOAD JSONL` resolves paths relative to it),
  2. runs `LOAD JSONL '<file>' AS <graph>` (loads straight into memory),
  3. prints node/edge counts as a sanity check.

Prereqs:
  pip install turingdb           # SDK
  turingdb start -demon          # server on :6666

Note on memory: the full graph is ~1.5M compounds. The expand script keeps heavy
properties (SMILES/formula/mass) only on the ~120k-node connected metabolic core;
the ~1.2M isolated catalogue compounds carry light identity fields so the whole
graph fits in a few GB. On a tight (8GB) box, close other apps before loading.

Usage:
  python load/load_full_jsonl.py
  python load/load_full_jsonl.py --graph biomat_full --host localhost --port 6666
"""

import argparse
import os
import shutil
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DEFAULT_JSONL = os.path.join(ROOT, "data", "retrorules_full", "graph.jsonl")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", default=DEFAULT_JSONL)
    ap.add_argument("--graph", default="biomat_full")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=6666)
    ap.add_argument("--turing-data-dir",
                    default=os.path.expanduser("~/.turing/data"))
    args = ap.parse_args()

    if not os.path.exists(args.jsonl):
        raise SystemExit(f"missing {args.jsonl} — run "
                         "`python data/expand_from_retrorules.py --full` first")

    from turingdb import TuringDB, TuringDBException

    fname = f"{args.graph}.jsonl"
    dst = os.path.join(args.turing_data_dir, fname)
    os.makedirs(args.turing_data_dir, exist_ok=True)
    if os.path.abspath(dst) != os.path.abspath(args.jsonl):
        print(f"copying {args.jsonl} -> {dst} ...")
        shutil.copyfile(args.jsonl, dst)

    client = TuringDB(host=f"http://{args.host}:{args.port}")
    print(f"LOAD JSONL '{fname}' AS {args.graph} ...")
    t = time.time()
    try:
        client.query(f"LOAD JSONL '{fname}' AS {args.graph}")
    except TuringDBException as e:
        # already imported? fall through to load_graph
        print("  LOAD JSONL:", str(e)[:120])
    if args.graph not in client.list_loaded_graphs():
        client.load_graph(args.graph)
    client.set_graph(args.graph)
    print(f"loaded in {time.time() - t:.1f}s")

    for label in ("Compound", "Reaction", "Enzyme", "Polymer", "Property"):
        n = int(client.query(f"MATCH (n:{label}) RETURN count(n) AS n").iloc[0, 0])
        print(f"  {label:9s}: {n:,}")
    print("edge types:")
    print(client.query("CALL db.edgeTypes()").to_string(index=False))


if __name__ == "__main__":
    main()
