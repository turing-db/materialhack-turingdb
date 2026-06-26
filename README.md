![MaterialHack x TuringDB](banner.png)

# MaterialHack x TuringDB

A biomanufacturing **knowledge graph for [MaterialHack](https://www.materialhack.co.uk/)**,
built on [TuringDB](https://github.com/turing-db/turingdb). It models bioplastic
production as **one connected graph in two layers**:

1. **Metabolic / retrosynthesis layer** — compounds, reactions and enzymes that
   turn feedstocks into biomaterial monomers (the
   [RetroRules](https://retrorules.org)-style question: *how do I biosynthesise
   this molecule?*).
2. **Property / function layer** — the polymers those monomers form, and the
   functions an engineer designs by (*biodegradable, heat resistant, flexible…*).

The two layers meet at the **monomer compound** (joined on InChIKey), so you can
ask questions that cross both at once — e.g. *"biodegradable, heat-resistant
materials whose monomer I can make from a given feedstock."*

> [!IMPORTANT]
> **The examples and datasets here are guidance, not limits.** This repo is a
> starting point, not a fixed deliverable. TuringDB can ingest *any* graph — take
> any open-source dataset, turn it into a TuringDB graph (the scripts in `data/`
> and `load/` show the pattern, from CSV/Cypher to bulk `LOAD JSONL`), and build
> whatever project you like on top. The biomaterials graph is just one worked
> example to get you moving — bring your own data and ideas.

## What is TuringDB?

[TuringDB](https://docs.turingdb.ai/) is a high-performance, **in-memory
column-oriented graph database** for analytical, AI-driven and read-intensive
workloads. It speaks a subset of **OpenCypher**, loads and queries large graphs
in seconds, and has **Git-style version control** built in — branch the graph,
run "what-if" edits in isolation, and time-travel through commit history with
snapshot isolation. That versioning is what makes it a good fit for exploring
*adaptive* process design: you can fork a scenario, change it, and compare.

## What's in this repo?

A ready-to-load graph plus the scripts that generate it at two sizes, and
runnable examples.

```
materialhack-turingdb/
├── README.md                       ← you are here
├── requirements.txt                ← turingdb, rdkit, pandas
├── NOTICE                          ← third-party data attribution (all CC-BY)
├── schema/SCHEMA.md                ← node/edge model + the InChIKey join + the cofactor rule
├── data/
│   ├── build_seed_data.py          ← generates the curated seed (RDKit InChIKeys)
│   ├── expand_from_retrorules.py   ← builds the real-data graph (demo slice, or --full / --rich)
│   ├── retrorules_slice/           ← curated seed: metabolic layer (compounds, reactions, enzymes)
│   ├── property_graph/             ← curated seed: property layer (polymers, properties)
│   ├── retrorules_expanded/        ← committed real-data demo slice (~6k nodes)
│   ├── retrorules_full/            ← full ~1.5M-node build (git-ignored; see release)
│   └── external/                   ← raw RetroRules/MetaNetX dumps (git-ignored)
├── load/
│   ├── load_graph.py               ← load seed (+expanded) into TuringDB, or emit .cypher
│   ├── load_full_jsonl.py          ← bulk-load the full graph via LOAD JSONL
│   ├── nodes.jsonl / edges.jsonl   ← seed import files
│   └── cypher/seed.cypher          ← static Cypher build script
└── examples/
    ├── EXAMPLES.md                 ← the core use cases explained
    ├── queries.cypher              ← runnable queries
    └── versioning_demo.py          ← Git-style branching demo
```

**Why it's shaped this way.** The committed seed and demo slice are deliberately
small and fully open, so the repo clones and runs in seconds. Every compound's
join key is an **RDKit/MetaNetX InChIKey**, so the metabolic and property layers
resolve to the *same* node. Crucially, ubiquitous **cofactors** (water, ATP,
NAD(P)(H), CoA, quinones…) sit on a separate `USES_COFACTOR` edge, so multi-hop
traversal follows real carbon chemistry instead of teleporting through hubs
(details in `schema/SCHEMA.md`).

### Two graph sizes

Same schema, same join key, same cofactor-aware backbone — the small graph is
just the big one **zoomed in around the four monomers**.

| | **Small** (demo slice) | **Big** (full graph) |
|---|---|---|
| Size | ~17k nodes / ~49k edges | ~1.57M nodes / ~363k edges |
| Compounds | ~6,075 | ~1,495,668 (~47k in the connected core) |
| Reactions | ~8,083 (all RetroRules-templated → SMARTS+EC) | ~72,291 (all non-transport; templated where available) |
| Scope | ~1–2 reaction hops around the 4 monomers | the entire MetaNetX/RetroRules network |
| Where | committed in `data/retrorules_expanded/` | [v1.0 release](https://github.com/turing-db/materialhack-turingdb/releases/tag/v1.0) (git-ignored locally) |
| Load | `python load/load_graph.py …` (~70s, Cypher) | `LOAD JSONL` via `load/load_full_jsonl.py` (~15s) |
| Use it for | quick start, demos, understanding the shape | real coverage, deep multi-hop, scale |

Both carry the same 6 polymers (PHB/PHBV, PLA, PGA, PBS, PCL) and 6 property
nodes, wired to the monomers — so the cross-layer query works at either size.

## Example use cases and ideas

MaterialHack's **Blue-Sky Track** is about *adaptive manufacturing for waste
valorisation*: waste streams are varied and inconsistent, and the challenge is
designing processes that turn that messy input into reliable, high-value output.
A biosynthetic-route graph is a natural substrate for that — it's a map of *which
molecules can become which materials, and by what routes*.

- **Waste → value routing.** Match the molecules in a waste stream (by InChIKey)
  to `Compound` nodes, then traverse the `SUBSTRATE_OF`/`PRODUCES` backbone to see
  which valuable **monomers** (and therefore **polymers**) they can reach, and via
  which enzymes (`CATALYZES`, by EC number).
- **Design-by-property, backwards.** Start from a target — *"biodegradable +
  heat-resistant"* — find the polymers with those `Property` nodes, get their
  monomer, and ask what feedstocks/waste compounds can biosynthesise it. This is
  the headline cross-layer query, run in reverse.
- **Adaptivity / robustness.** Because many *alternative* reaction paths reach the
  same monomer, you can pick the route that uses the enzymes and inputs you
  actually have — and adapt when the waste composition shifts. Use TuringDB
  **branches/commits** to model "what if this feedstock or enzyme is unavailable?"
  and compare routes side by side.
- **Host / enzyme selection.** Reactions carry EC numbers and RetroRules
  templates (SMARTS) — a starting point for choosing enzymes or engineering a
  production strain.

Ideas to extend it: add `Paper` nodes (`MENTIONS`, keyed on DOI/PMID) for a
GraphRAG assistant grounded in the same graph; sample molecular graphs from
`Compound`/`Polymer` to train a property-prediction GNN; layer in real
experimental property values (e.g. PoLyInfo) keyed on the same InChIKey.

## Quickstart

```bash
# 1. install the engine, SDK and deps (a virtualenv is recommended)
pip install -r requirements.txt          # turingdb, rdkit, pandas

# 2. (optional) regenerate the seed data — already committed
python data/build_seed_data.py

# 3. start TuringDB — REST API on http://localhost:6666
turingdb -demon                          # background daemon (or `turingdb` for foreground)

# 4. load the committed demo graph (curated seed + real-data slice, ~6k nodes)
python load/load_graph.py --host localhost --port 6666 --graph biomaterials

# 5. run the example queries / versioning demo
python examples/versioning_demo.py       # see also examples/queries.cypher
```

Query it from Python:

```python
from turingdb import TuringDB

db = TuringDB(host="http://localhost:6666")
db.set_graph("biomaterials")

# biodegradable, heat-resistant materials and the monomer you'd biosynthesise
db.query("""
    MATCH (m:Compound)-[:POLYMERIZES_TO]->(p:Polymer)-[:HAS_PROPERTY]->(pr:Property)
    RETURN m.name, p.abbrev, pr.name
""")
```

No server handy? Emit a static Cypher script instead:
`python load/load_graph.py --emit-cypher load/cypher/seed.cypher`.

### Going big — the full ~1.5M-node graph

The full metabolic graph is too large to commit, so it's available two ways.

**A. Download the prebuilt graph** from the
[v1.0 release](https://github.com/turing-db/materialhack-turingdb/releases/tag/v1.0)
(no source download, no rebuild):

```bash
# slim (512MB, loads on 8GB RAM) — recommended:
curl -L -o graph.jsonl \
  https://github.com/turing-db/materialhack-turingdb/releases/download/v1.0/graph.jsonl
# or rich (829MB, SMILES on every compound, needs ~16GB+ RAM): graph_full_props.jsonl

cp graph.jsonl ~/.turing/data/
turingdb -demon
python load/load_full_jsonl.py --graph biomaterials   # runs LOAD JSONL via the SDK
```

**B. Build it yourself** from the MetaNetX/RetroRules dumps in `data/external/`:

```bash
python data/expand_from_retrorules.py --full          # add --rich for full SMILES
turingdb -demon
python load/load_full_jsonl.py --graph biomat_full
```

This yields **>1.5M nodes**: ~1.5M `Compound` + ~72k `Reaction` + ~5k `Enzyme`,
with ~360k edges. Most compounds are an isolated *catalogue*; the **connected,
traversable core** is ~47k compounds + ~72k reactions. Multi-hop stays meaningful
because currency metabolites and structureless participants are routed onto
`USES_COFACTOR`, not the carbon backbone. The four monomers (`PHB`/`PHBV`, `PLA`,
`PGA`, `PBS`) are wired into the property layer so the cross-layer query works at
full scale too.

## Data sourcing & licensing

This repo commits **only** small, openly-shareable derived data. The raw source
dumps are large and stay out of git (download them from the providers):

The open flat files (`retrorules_metanetx.csv`, `chem_prop.tsv`, `reac_prop.tsv`)
go in `data/external/`; `expand_from_retrorules.py` derives the committed slice in
`data/retrorules_expanded/` (and the full build).

**Dataset licenses (the two sources used here):**

- **RetroRules v3.0.0** (reaction templates) — [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
  RetroRules integrates upstream sources (MNXref, Rhea, ChEBI, UniProt, USPTO) that
  may carry their own terms — *check those before commercial redistribution.*
- **MetaNetX / MNXref v4.5** (compound & reaction properties) — [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
  © 2011 SystemsX / SIB Swiss Institute of Bioinformatics.

Rhea, ChEBI and UniProt (referenced via the above) are also CC-BY. If you
redistribute the derived data, keep the attribution — see `NOTICE` for the full
citations. Dataset and schema details are in each `data/*/README.md` and
`schema/SCHEMA.md`.
