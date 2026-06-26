#!/usr/bin/env python3
"""
load_graph.py
=============
Loads the biomaterials graph into a running TuringDB instance (or emits a static
Cypher script). It loads the curated seed (data/retrorules_slice +
data/property_graph) and, when present, the real RetroRules/MetaNetX expansion
(data/retrorules_expanded, produced by data/expand_from_retrorules.py).

Merging duplicates on inchikey
------------------------------
The seed monomers and the expanded RetroRules compounds describe the *same*
molecules, so they must collapse to one node. TuringDB's Cypher subset has **no
MERGE** (only CREATE and MATCH...SET — see the SDK docs / turingdb skill), so we
cannot dedup at query time. Instead we dedup in Python here: compounds are keyed
on ``inchikey`` (falling back to ``id`` when a compound has no structure, e.g.
CoA thioesters), one canonical node is created per key, and every edge endpoint
is rewritten to the canonical id. The expanded anchors already carry the seed's
id + inchikey, so a seed monomer and its RetroRules twin merge cleanly.

TuringDB API used here (see the turingdb skill / https://docs.turingdb.ai):
    from turingdb import TuringDB
    client = TuringDB(host="http://localhost:6666")   # full URL
    client.create_graph("biomaterials"); client.set_graph("biomaterials")
    change = client.new_change(); client.checkout(change=change)  # writes need a change
    client.query("CREATE ..."); client.query("COMMIT")            # before edges
    client.query("CHANGE SUBMIT"); client.checkout()              # merge to main

Usage:
    # start TuringDB first:  turingdb start -demon   (default port 6666)
    python load/load_graph.py --host localhost --port 6666 --graph biomaterials
    python load/load_graph.py --seed-only                 # skip the expansion
    python load/load_graph.py --emit-cypher load/cypher/seed.cypher   # no server
"""

import argparse
import csv
import os

csv.field_size_limit(10_000_000)  # expanded reactions carry long SMARTS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
RR = os.path.join(ROOT, "data", "retrorules_slice")
PG = os.path.join(ROOT, "data", "property_graph")
EXP = os.path.join(ROOT, "data", "retrorules_expanded")


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def q(v):
    """Quote a value as a Cypher literal: strings escaped, numbers/bools bare."""
    if v is None or v == "":
        return "null"
    if v in ("true", "false"):
        return v
    try:
        float(v)
        return v
    except (ValueError, TypeError):
        return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def props(d, keys):
    # TuringDB's CREATE rejects `null` property literals — to leave a property
    # unset you simply omit it. So skip any key whose value is empty/None rather
    # than emitting `key: null`.
    parts = []
    for k in keys:
        v = d.get(k)
        if v is None or v == "":
            continue
        parts.append(f"{k}: {q(v)}")
    return "{" + ", ".join(parts) + "}"


# --------------------------------------------------------------------------
# Gather + dedup nodes across the seed and (optional) expanded folders.
# --------------------------------------------------------------------------
COMPOUND_KEYS = ["id", "name", "smiles", "inchikey", "kegg", "chebi", "role",
                 "is_monomer", "is_currency", "formula", "charge", "mass"]
REACTION_KEYS = ["id", "name", "ec", "source", "smarts", "ec_list", "score",
                 "datasets", "radius", "is_balanced"]
ENZYME_KEYS = ["id", "name", "ec", "gene", "organism", "uniprot"]


def gather_compounds(dirs):
    """Return (unique_rows, canonical_id) — dedup on inchikey, else id.

    Seed rows win over expanded rows for a key (they carry curated role/kegg/chebi).
    canonical_id maps every source compound id to the id of its surviving node.
    """
    by_key = {}            # dedup key -> chosen row (with a private _seed flag)
    canonical_id = {}      # any compound id -> canonical id
    pending = []           # (id, key) to resolve after all rows seen
    for is_seed, d in dirs:
        for c in read_csv(os.path.join(d, "compounds.csv")):
            key = c["inchikey"] if c.get("inchikey") else "id:" + c["id"]
            prev = by_key.get(key)
            if prev is None or (is_seed and not prev.get("_seed")):
                row = dict(c)
                row["_seed"] = is_seed
                by_key[key] = row
            pending.append((c["id"], key))
    for cid, key in pending:
        canonical_id[cid] = by_key[key]["id"]
    rows = [{k: r.get(k, "") for k in COMPOUND_KEYS} for r in by_key.values()]
    return rows, canonical_id


def gather_enzymes(dirs):
    """Dedup enzymes on EC (seed wins, keeping gene/organism/uniprot)."""
    by_ec = {}
    extra = []             # enzymes without an EC (kept as-is, keyed by id)
    for is_seed, d in dirs:
        for e in read_csv(os.path.join(d, "enzymes.csv")):
            ec = e.get("ec")
            if not ec:
                extra.append(e)
                continue
            prev = by_ec.get(ec)
            if prev is None or (is_seed and not prev.get("_seed")):
                row = dict(e)
                row["_seed"] = is_seed
                by_ec[ec] = row
    rows = [{k: r.get(k, "") for k in ENZYME_KEYS} for r in list(by_ec.values()) + extra]
    enzyme_ecs = set(by_ec)
    return rows, enzyme_ecs


def gather_reactions(dirs):
    seen, rows = set(), []
    for _, d in dirs:
        for r in read_csv(os.path.join(d, "reactions.csv")):
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            rows.append(r)
    return rows


# --------------------------------------------------------------------------
def build_statements(dirs):
    """Return (node_stmts, edge_stmts). Nodes are CREATEd, edges MATCH...CREATE.

    The split lets the live loader COMMIT between the two (TuringDB needs the
    nodes persisted before edges can MATCH them).
    """
    node_stmts, edge_stmts = [], []

    compounds, canonical_id = gather_compounds(dirs)
    enzymes, enzyme_ecs = gather_enzymes(dirs)
    reactions = gather_reactions(dirs)
    polymers = read_csv(os.path.join(PG, "polymers.csv"))
    properties = read_csv(os.path.join(PG, "properties.csv"))

    # ---- nodes ----
    for c in compounds:
        node_stmts.append(f"CREATE (:Compound {props(c, COMPOUND_KEYS)})")
    for e in enzymes:
        node_stmts.append(f"CREATE (:Enzyme {props(e, ENZYME_KEYS)})")
    for r in reactions:
        node_stmts.append(f"CREATE (:Reaction {props(r, REACTION_KEYS)})")
    pol_keys = ["id", "name", "abbrev", "psmiles", "tg_c", "tm_c", "tensile_mpa",
                "youngs_gpa", "elongation_pct", "crystallinity_pct", "density",
                "biodegradable", "bio_based"]
    for pol in polymers:
        node_stmts.append(f"CREATE (:Polymer {props(pol, pol_keys)})")
    for pr in properties:
        node_stmts.append(f"CREATE (:Property {props(pr, ['id', 'name', 'kind', 'description'])})")

    # ---- reaction participants ----
    # Currency metabolites (water, ATP, NAD(P)(H), CoA, ...) are routed onto a
    # separate USES_COFACTOR edge so that variable-length SUBSTRATE_OF|PRODUCES
    # backbone traversals follow real carbon chemistry instead of teleporting
    # through ubiquitous cofactor hubs. The decision uses the (deduped) compound
    # role, so seed cofactors (role=cofactor) are handled the same way.
    role_of = {c["id"]: c.get("role", "") for c in compounds}
    for _, d in dirs:
        for row in read_csv(os.path.join(d, "reaction_participants.csv")):
            cid = canonical_id.get(row["compound_id"], row["compound_id"])
            rid = row["reaction_id"]
            if role_of.get(cid) == "cofactor":
                edge_stmts.append(
                    f'MATCH (r:Reaction {{id: {q(rid)}}}), (c:Compound {{id: {q(cid)}}}) '
                    f'CREATE (r)-[:USES_COFACTOR]->(c)')
            elif row["role"] == "substrate":
                edge_stmts.append(
                    f'MATCH (c:Compound {{id: {q(cid)}}}), (r:Reaction {{id: {q(rid)}}}) '
                    f'CREATE (c)-[:SUBSTRATE_OF]->(r)')
            else:
                edge_stmts.append(
                    f'MATCH (r:Reaction {{id: {q(rid)}}}), (c:Compound {{id: {q(cid)}}}) '
                    f'CREATE (r)-[:PRODUCES]->(c)')

    # ---- Enzyme -> Reaction (CATALYZES) by EC ----
    # Seed reactions link by their single ec; expanded reactions link every full
    # EC in ec_list that has an Enzyme node. Dedup (ec, reaction) pairs.
    seen_cat = set()
    for r in reactions:
        ecs = []
        if r.get("ec"):
            ecs.append(r["ec"])
        if r.get("ec_list"):
            ecs.extend(x for x in r["ec_list"].split(";") if x)
        for ec in ecs:
            if ec not in enzyme_ecs:
                continue
            pair = (ec, r["id"])
            if pair in seen_cat:
                continue
            seen_cat.add(pair)
            edge_stmts.append(
                f'MATCH (e:Enzyme {{ec: {q(ec)}}}), (r:Reaction {{id: {q(r["id"])}}}) '
                f'CREATE (e)-[:CATALYZES]->(r)')

    # ---- Monomer -> Polymer (POLYMERIZES_TO) ----
    for pol in polymers:
        if pol.get("monomer_id"):
            cid = canonical_id.get(pol["monomer_id"], pol["monomer_id"])
            edge_stmts.append(
                f'MATCH (c:Compound {{id: {q(cid)}}}), (p:Polymer {{id: {q(pol["id"])}}}) '
                f'CREATE (c)-[:POLYMERIZES_TO]->(p)')

    # ---- Polymer -> Property (HAS_PROPERTY) ----
    for row in read_csv(os.path.join(PG, "polymer_properties.csv")):
        edge_stmts.append(
            f'MATCH (p:Polymer {{id: {q(row["polymer_id"])}}}), '
            f'(pr:Property {{id: {q(row["property_id"])}}}) '
            f'CREATE (p)-[:HAS_PROPERTY]->(pr)')

    return node_stmts, edge_stmts


def source_dirs(seed_only):
    dirs = [(True, RR)]
    if not seed_only and os.path.isdir(EXP) and os.path.exists(os.path.join(EXP, "compounds.csv")):
        dirs.append((False, EXP))
    return dirs


def emit_cypher(path, seed_only):
    node_stmts, edge_stmts = build_statements(source_dirs(seed_only))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        f.write("// Auto-generated biomaterials graph for TuringDB.\n")
        f.write(f"// Regenerate with: python load/load_graph.py --emit-cypher {path}\n")
        f.write("// Nodes first, then edges (load inside a change; COMMIT between the two).\n\n")
        for s in node_stmts:
            f.write(s + ";\n")
        f.write("\n")
        for s in edge_stmts:
            f.write(s + ";\n")
    print(f"Wrote {len(node_stmts)} node + {len(edge_stmts)} edge statements to {path}")


def load_live(host, port, graph, seed_only):
    from turingdb import TuringDB, TuringDBException  # lazy: --emit-cypher needs no SDK

    client = TuringDB(host=f"http://{host}:{port}")
    try:
        client.create_graph(graph)
    except TuringDBException:
        pass
    try:
        client.load_graph(graph)
    except TuringDBException:
        pass
    client.set_graph(graph)

    node_stmts, edge_stmts = build_statements(source_dirs(seed_only))

    change = client.new_change()
    client.checkout(change=change)
    for s in node_stmts:
        client.query(s)
    client.query("COMMIT")          # persist nodes so edges can MATCH them
    for s in edge_stmts:
        client.query(s)
    client.query("CHANGE SUBMIT")
    client.checkout()
    print(f"Loaded {len(node_stmts)} node + {len(edge_stmts)} edge statements "
          f"into graph '{graph}'.")

    for label in ("Compound", "Enzyme", "Reaction", "Polymer", "Property"):
        res = client.query(f"MATCH (n:{label}) RETURN count(n) AS n")
        print(f"  {label:10s}: {list(res['n'])[0]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=6666)
    ap.add_argument("--graph", default="biomaterials")
    ap.add_argument("--seed-only", action="store_true",
                    help="load only the curated seed, ignoring data/retrorules_expanded")
    ap.add_argument("--emit-cypher", metavar="PATH",
                    help="write a static .cypher file instead of loading to a server")
    args = ap.parse_args()

    if args.emit_cypher:
        emit_cypher(args.emit_cypher, args.seed_only)
    else:
        load_live(args.host, args.port, args.graph, args.seed_only)


if __name__ == "__main__":
    main()
