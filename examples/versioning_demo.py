#!/usr/bin/env python3
"""
versioning_demo.py  (USE CASE 3 — TuringDB's headline differentiator)
=====================================================================
A biomaterials engineer wants to test a *hypothetical* engineered pathway -- say
a novel enzyme variant that opens a shorter route to the PHB monomer -- without
disturbing the validated graph everyone else is querying.

With TuringDB's Git-style versioning you branch the graph, make the speculative
edits on the branch, query it, and main stays untouched and reproducible. No
copying the database, no separate environment.

API (https://docs.turingdb.ai/pythonsdk/get_started):
    change = client.new_change()    # open a new change (branch)
    client.checkout(change=change)  # work on it
    ... edits ...                   # only affect the branch
    client.checkout(change="main")  # main is unchanged

Run (needs a running TuringDB with the seed graph loaded):
    python examples/versioning_demo.py
"""

from turingdb import TuringDB


def count_routes(client, label):
    res = client.query(
        'MATCH route = (f:Compound {role: "feedstock"})'
        '-[:SUBSTRATE_OF|PRODUCES*1..14]->'
        '(m:Compound {name: "(R)-3-Hydroxybutanoic acid"}) '
        'RETURN count(route) AS n')
    n = list(res)[0]["n"]
    print(f"  [{label}] biosynthetic routes feedstock -> PHB monomer: {n}")
    return n


def main():
    client = TuringDB(host="localhost", port=6666)
    client.set_graph("biomaterials")

    print("On main (validated graph):")
    count_routes(client, "main")

    # --- branch off and test a speculative engineered shortcut ---
    print("\nOpening a branch to test a hypothetical engineered enzyme...")
    change = client.new_change()
    client.checkout(change=change)

    # Hypothesis: an engineered thiolase/reductase fusion converts acetyl-CoA
    # directly to the (R)-3-hydroxybutanoyl-CoA intermediate in one step.
    client.query(
        'CREATE (:Reaction {id: "rxn_engineered_fusion", '
        'name: "Engineered AccoA -> 3HB-CoA (hypothetical)", source: "design"})')
    client.query(
        'MATCH (s:Compound {id: "cpd_accoa"}), (r:Reaction {id: "rxn_engineered_fusion"}) '
        'CREATE (s)-[:SUBSTRATE_OF]->(r)')
    client.query(
        'MATCH (r:Reaction {id: "rxn_engineered_fusion"}), (p:Compound {id: "cpd_3hbcoa"}) '
        'CREATE (r)-[:PRODUCES]->(p)')

    print("On the branch (with the hypothetical shortcut):")
    count_routes(client, "branch")

    # --- back to main: untouched ---
    print("\nBack on main:")
    client.checkout(change="main")
    count_routes(client, "main")

    print("\nThe branch holds the speculative design; main stays reproducible. "
          "Merge it if the wet-lab validates, discard it if it doesn't.")


if __name__ == "__main__":
    main()
