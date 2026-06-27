#!/usr/bin/env python3
"""
load_graph.py
=============
Load the Cupriavidus necator H16 graph into a running TuringDB server.

The graph ships as two parquet files (nodes.parquet / edges.parquet) and is
imported with the `turing-parquet` bulk loader (bundled with turingdb >= 1.32).

Because a running server holds an exclusive lock on its data directory,
`turing-parquet` cannot write into it directly. So this script:
  1. builds the graph into a scratch directory,
  2. copies the built graph into the server's `graphs/` folder,
  3. asks the running server to load it.

Usage:
    # start TuringDB first, e.g.:  turingdb start -turing-dir . -demon
    python cupriavidus_necator/load_graph.py --turing-dir . --host localhost --port 6666

If nodes.parquet / edges.parquet are missing, run `python build_graph.py` first
(it regenerates them from the BioModels SBML in data/).
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GRAPH = "cupriavidus_necator"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--turing-dir", default=".",
                    help="server's root data dir (contains graphs/); default: cwd")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=6666)
    args = ap.parse_args()

    nodes = os.path.join(HERE, "nodes.parquet")
    edges = os.path.join(HERE, "edges.parquet")
    for f in (nodes, edges):
        if not os.path.exists(f):
            sys.exit(f"missing {f} — run `python {os.path.join(HERE, 'build_graph.py')}` first")

    graphs_dir = os.path.join(os.path.abspath(args.turing_dir), "graphs")
    if not os.path.isdir(graphs_dir):
        sys.exit(f"no graphs/ under --turing-dir {args.turing_dir!r}; "
                 f"point it at the server's data directory")

    with tempfile.TemporaryDirectory() as scratch:
        print(f"building graph '{GRAPH}' with turing-parquet ...")
        subprocess.run(
            ["turing-parquet", "-nodes", nodes, "-edges", edges,
             "-props", "properties", "-edgetype", "relation",
             "-out", scratch, "-graph", GRAPH],
            check=True,
        )
        src = os.path.join(scratch, "graphs", GRAPH)
        dst = os.path.join(graphs_dir, GRAPH)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f"copied built graph into {dst}")

    from turingdb import TuringDB, TuringDBException
    client = TuringDB(host=f"http://{args.host}:{args.port}")
    try:
        client.load_graph(GRAPH)
    except TuringDBException as e:
        print(f"(load_graph: {e})")  # already loaded -> fine
    client.set_graph(GRAPH)

    print(f"\nloaded '{GRAPH}':")
    for label in ("Species", "Compartment", "Pathway", "Reaction", "Metabolite", "GeneProduct"):
        n = client.query(f"MATCH (n:{label}) RETURN n").shape[0]
        print(f"  {label:12s}: {n}")


if __name__ == "__main__":
    main()
