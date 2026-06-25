# TuringDB Biomaterials Starter

A small, runnable starter graph for biomanufacturing built on
[TuringDB](https://github.com/turing-db/turingdb) — an in-memory, columnar graph
engine with native Cypher and Git-style versioning.

It models bioplastic production as **one connected graph in two layers**:

1. **Metabolic / retrosynthesis layer** — compounds, reactions and enzymes that
   turn a sugar feedstock into biomaterial monomers (the
   [RetroRules](https://retrorules.org)-style question: *how do I biosynthesise
   this molecule?*).
2. **Property / function layer** — the polymers those monomers form, and the
   functions an engineer designs by (*biodegradable, heat resistant, flexible…*).

The two layers meet at the **monomer compound**, so you can ask questions that
cross both at once — e.g. *"biodegradable, heat-resistant materials whose monomer
I can make from sugar."* That cross-layer query is the point of the demo.

## Why this shape

The seed is deliberately tiny and fully open so it clones and runs in seconds.
Everything is generated from one script with correct, RDKit-computed InChIKeys
as the join key, so the metabolic and property layers resolve to the *same*
compound nodes. When you want depth, you load real data locally
(RetroRules, PoLyInfo) — those are gated/large and stay out of the repo.

## Repo map

```
turingdb-biomaterials/
├── README.md                      ← you are here
├── requirements.txt
├── schema/SCHEMA.md               ← node/edge model + the InChIKey join
├── data/
│   ├── build_seed_data.py         ← generates the curated seed CSVs + JSONL (run this)
│   ├── expand_from_retrorules.py  ← expand the seed with real RetroRules/MetaNetX chemistry
│   ├── retrorules_slice/          ← metabolic layer (compounds, reactions, enzymes)
│   │   └── README.md
│   ├── retrorules_expanded/       ← derived real-data slice (committed; produced by expand script)
│   ├── external/                  ← raw RetroRules/MetaNetX dumps (NOT committed — see NOTICE)
│   └── property_graph/            ← property layer (polymers, properties)
│       └── README.md
├── load/
│   ├── load_graph.py              ← load seed (+expanded) into TuringDB, or emit .cypher
│   ├── nodes.jsonl / edges.jsonl  ← native TuringDB import files
│   └── cypher/seed.cypher         ← static Cypher build script
├── NOTICE                          ← third-party data attribution (RetroRules, MNXref, …)
└── examples/
    ├── EXAMPLES.md                ← the three use cases explained
    ├── queries.cypher             ← runnable queries
    └── versioning_demo.py         ← Git-style branching demo
```

## Quickstart

```bash
# 1. install
pip install -r requirements.txt          # turingdb, rdkit, pandas

# 2. (re)generate the seed data — already committed, optional
python data/build_seed_data.py

# 3. start TuringDB (Docker shown; nixpkgs/binary also work — see turingdb docs)
docker run -it -p 6666:6666 turingdbai/turingdb:nightly turingdb

# 4. load the seed graph
python load/load_graph.py --host localhost --port 6666 --graph biomaterials

# 5. run the example queries (examples/queries.cypher) or the versioning demo
python examples/versioning_demo.py
```

### Going big — the million-node build

The committed slice is demo-sized. To build the **full metabolic graph** from the
MetaNetX/RetroRules dumps in `data/external/`:

```bash
# 1. emit the whole catalogue as an APOC LOAD JSONL file (~1.5M compounds,
#    ~72k reactions, ~360k edges) into data/retrorules_full/ (git-ignored, ~0.5GB)
python data/expand_from_retrorules.py --full

# 2. load it into TuringDB via the native bulk path (loads in ~15s)
turingdb start -demon
python load/load_full_jsonl.py --graph biomat_full
```

This yields **>1.5M nodes**. Most are an isolated *compound catalogue*; the
**connected, traversable core** is ~47k compounds + ~72k reactions. Multi-hop
traversal stays meaningful because currency metabolites and structureless
participants are kept off the `SUBSTRATE_OF`/`PRODUCES` backbone (see
`schema/SCHEMA.md` → `USES_COFACTOR`). The four monomers (`PHB`/`PHBV`, `PLA`,
`PGA`, `PBS`) are wired into the property layer so the cross-layer query still
works at full scale.

No TuringDB server handy? Generate a static Cypher script and inspect it:

```bash
python load/load_graph.py --emit-cypher load/cypher/seed.cypher
```

You can also import `load/nodes.jsonl` / `load/edges.jsonl` directly (JSONL is a
native TuringDB import path).

## Data sourcing & licensing

This repo commits **only** small, self-generated, openly-shareable data. The
real sources are loaded locally and must not be redistributed here:

- **RetroRules + MetaNetX/MNXref** — the open flat files (`retrorules_metanetx.csv`,
  `chem_prop.tsv`, `reac_prop.tsv`) go in `data/external/` (hundreds of MB, not
  committed). Expand the seed with `python data/expand_from_retrorules.py`; the
  small derived slice it writes to `data/retrorules_expanded/` *is* committed.
  See `NOTICE` for attribution (all CC-BY).
- **PoLyInfo** (NIMS) — rich experimental polymer properties, registration-gated
  and non-commercial. Use for real property values; do not commit.
- Open alternatives you *can* ship if you want scale: **PI1M** (~1M polymer
  SMILES, on GitHub), and more of **MetaNetX/MNXref**, **Rhea**, **ChEBI**,
  **UniProt** (all open).

See each dataset's README for details.

## Where this goes next

The two committed layers are the foundation. The same graph extends to the other
two ideas in the brief, each joining on identifiers already present:

- **GNN training** — sample molecular graphs from `Compound` / `Polymer`
  (keyed on InChIKey / p-SMILES) as the substrate for a property-prediction GNN.
  Standard labelled sets to start from: OGB (`ogbg-molhiv`, `ogbg-molpcba`),
  MoleculeNet, QM9.
- **GraphRAG assistant** — add `Paper` nodes linked by `MENTIONS` to the
  chemical nodes (keyed on DOI/PMID), grounding an LLM in the same graph. Sources:
  PMC Open Access, Europe PMC, OpenAlex.
