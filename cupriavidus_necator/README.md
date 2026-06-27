# Cupriavidus necator H16 — organism graph

A self-contained TuringDB graph for the bacterium **_Cupriavidus necator_ H16**
(formerly _Ralstonia eutropha_ / _Alcaligenes eutrophus_) — the model
**chemolithoautotroph** behind microbial **PHB/PHA bioplastics**.

_C. necator_ is the textbook host for the PHB story this repo centres on
(see the top-level `examples/` — PhaA/PhaB/PhaC make the PHB monomer). This
directory adds the **whole organism** as its own graph: a curated genome-scale
metabolic reconstruction with every reaction, metabolite, gene and subsystem,
so you can ask organism-level questions (what can this host make? from CO₂? which
gene runs this step?) instead of just the four-enzyme PHB slice.

Everything here is **self-contained** — build script, data, loader, and example
queries — and independent of the biomaterials graph in the repo root.

## Why this organism

| Trait | In the graph |
|-------|--------------|
| **PHB / PHA bioplastic** accumulation (up to ~90% cell dry weight) | `PHAMetabolism` subsystem; PhaA/PhaB/PhaC reactions |
| **CO₂ fixation** (Calvin–Benson–Bassham cycle) | `Calvin cycle/Pentose phosphate pathway`; RuBisCO (genes `H16_B1394/B1395`, megaplasmid pHG1 `PHG426/427`) + phosphoribulokinase |
| **H₂ oxidation** (Knallgas / lithoautotrophy) | `Hydrogen production` — Bidirectional [NiFe] hydrogenase |
| Grows on CO₂ + H₂ as sole carbon/energy source | full autotrophic + heterotrophic central metabolism |

## Source

- **BioModels:** [`MODEL2502270001`](https://www.ebi.ac.uk/biomodels/MODEL2502270001)
  — "Ascencio2025 - GEM Cupriavidus necator iCNH2025A" (curated, Feb 2025).
- **Model:** iCNH2025A — 2,737 reactions, 1,803 metabolites, 1,059 genes;
  mass/charge-balanced, thermodynamically curated, with expanded PHA (PHB + PHBV)
  routes.
- **Strain:** H16 (DSM 428 / ATCC 17699), NCBI taxonomy `381666`, genome
  assembly `GCF_004798725.1`.
- The COMBINE archive (`data/iCNH2025A_Cnecator_GEM.omex`) holds the SBML L3
  (FBC v2 + groups) the graph is parsed from.

## Graph schema

| Node label    | Count | Key properties |
|---------------|------:|----------------|
| `Species`     |     1 | `displayName, strain, taxId, assembly, lineage, sourceDb` |
| `Compartment` |     3 | cytosol `c`, periplasm `p`, extracellular `e` |
| `Pathway`     |   209 | `displayName, numReactions` — metabolic subsystems |
| `Reaction`    | 2,737 | `biggId, reversible, lowerFluxBound, upperFluxBound, ecNumber, gpr, reactomeHsa` |
| `Metabolite`  | 1,803 | `formula, charge, chebi, keggCompound, metanetx, biocyc, hmdb` |
| `GeneProduct` | 1,059 | `locusTag, uniprot, ncbiGene` (enzymes) |

| Edge type     | Count | Meaning |
|---------------|------:|---------|
| `output`      | 5,883 | `Reaction → Metabolite` (product), `stoichiometry` prop |
| `input`       | 5,606 | `Reaction → Metabolite` (substrate), `stoichiometry` prop |
| `catalyzedBy` | 3,590 | `Reaction → GeneProduct` (gene-protein-reaction) |
| `species`     | 2,946 | `Reaction/Pathway → Species` |
| `hasEvent`    | 2,726 | `Pathway → Reaction` (subsystem membership) |
| `compartment` | 1,803 | `Metabolite → Compartment` |

`Reaction.reactomeHsa` carries human Reactome `R-HSA-…` stable-id cross-references
(33 reactions) — a ready bridge if you also load the Reactome graph.

The schema mirrors [Reactome](https://reactome.org)'s
organism → pathway → reaction → entity shape, adapted to a constraint-based
metabolic model (flux bounds, gene-protein-reaction rules, stoichiometry).

## Build & load

```bash
# 1. start a TuringDB server over this repo (data dir = repo root)
turingdb start -turing-dir . -demon

# 2. (optional) regenerate nodes.parquet / edges.parquet from the SBML
python cupriavidus_necator/build_graph.py

# 3. import the graph into the running server
python cupriavidus_necator/load_graph.py --turing-dir . --host localhost --port 6666
```

`nodes.parquet` / `edges.parquet` are committed, so step 2 is optional — step 3
loads the graph directly via the `turing-parquet` bulk importer (turingdb ≥ 1.32).

## Example queries

Full set in [`examples.cypher`](examples.cypher). TuringDB's Cypher subset has no
`OPTIONAL MATCH` / `UNWIND` / `MERGE` / `IN`-lists; multi-hop uses explicit
repeated hops.

```python
from turingdb import TuringDB
c = TuringDB(host="http://localhost:6666"); c.set_graph("cupriavidus_necator")

# CO2 fixation: Calvin–Benson–Bassham cycle enzymes, by gene
c.query("""MATCH (p:Pathway)-[:hasEvent]->(r:Reaction)-[:catalyzedBy]->(g:GeneProduct)
           WHERE p.displayName = 'Calvin cycle/Pentose phosphate pathway'
           RETURN r.displayName, g.locusTag""")

# PHB/PHA bioplastic biosynthesis reactions
c.query("""MATCH (p:Pathway)-[:hasEvent]->(r:Reaction)
           WHERE p.displayName = 'PHAMetabolism'
           RETURN r.displayName, r.gpr""")

# RuBisCO products with stoichiometry
c.query("""MATCH (r:Reaction {displayName:'Ribulose bisphosphate carboxylase'})-[e:output]->(m:Metabolite)
           RETURN m.displayName, m.formula, e.stoichiometry""")
```

## Files

```
cupriavidus_necator/
├── README.md                      ← you are here
├── build_graph.py                 ← SBML (.omex) → nodes.parquet / edges.parquet
├── load_graph.py                  ← bulk-import the parquet into a running TuringDB
├── examples.cypher                ← runnable example queries
├── nodes.parquet / edges.parquet  ← the graph (5,812 nodes / 22,554 edges)
└── data/
    ├── iCNH2025A_Cnecator_GEM.omex ← BioModels source (COMBINE archive)
    ├── model_meta.json             ← BioModels metadata
    └── model.xml                   ← extracted SBML (regenerated by build_graph.py; git-ignored)
```

## Attribution

Derived from BioModels entry `MODEL2502270001` (iCNH2025A), Ascencio-Galván et al.,
2025. BioModels content is distributed under
[CC0](https://www.ebi.ac.uk/biomodels/help#license). Organism classification and
identifiers from NCBI Taxonomy (`381666`) and NCBI Assembly (`GCF_004798725.1`).
