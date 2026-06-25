# Graph schema

The whole repo is **one connected graph in two layers** that meet at the
monomer compounds. That junction is the point of the demo: you ask questions
that cross from biosynthetic chemistry into material properties in a single
query.

```
   METABOLIC / RETROSYNTHESIS LAYER                 PROPERTY / FUNCTION LAYER
   (RetroRules-style)                               (curated)

   (Enzyme)                                          (Property)
      | CATALYZES                                       ^ HAS_PROPERTY
      v                                                 |
   (Reaction) --PRODUCES--> (Compound) --POLYMERIZES_TO--> (Polymer)
      ^                         ^   ^                         |
      | SUBSTRATE_OF            |   '--------- monomer --------'
   (Compound) -----------------'
   feedstock / intermediate              the monomer Compound is the bridge
```

## Nodes

| Label      | Key            | Key properties |
|------------|----------------|----------------|
| `Compound` | `inchikey` *   | `name, smiles, inchikey, kegg, chebi, role, is_monomer, is_currency, formula, charge, mass` |
| `Enzyme`   | `ec`           | `name, ec, gene, organism, uniprot` |
| `Reaction` | `id`           | `name, ec, ec_list, source, smarts, score, datasets, radius, is_balanced` |
| `Polymer`  | `id`           | `name, abbrev, psmiles, tg_c, tm_c, tensile_mpa, youngs_gpa, elongation_pct, crystallinity_pct, density, biodegradable, bio_based` |
| `Property` | `id`           | `name, kind (thermal\|mechanical\|functional), description` |

The real-data layers (`expand_from_retrorules.py`) add provenance to `Compound`
(`is_currency`, `formula`, `charge`, `mass`) and `Reaction` (`smarts` template,
`ec_list`, RetroRules `score`, `datasets`, `radius`, `is_balanced`).

\* `Compound.inchikey` is the universal join key. Every chemical source
(RetroRules, MNXref, ChEBI, PubChem, polymer monomer tables) exposes an
InChIKey, so it is what lets a metabolite from RetroRules and a monomer from the
property table resolve to the *same node*. The seed computes it from SMILES with
RDKit (see `data/build_seed_data.py`); the RetroRules loader merges on it.

`role` on a Compound is one of `feedstock | intermediate | cofactor | monomer`.

## Edges

| Type             | From → To              | Meaning |
|------------------|------------------------|---------|
| `SUBSTRATE_OF`   | `Compound → Reaction`  | **carbon-backbone** substrate consumed by the reaction |
| `PRODUCES`       | `Reaction → Compound`  | **carbon-backbone** product of the reaction |
| `USES_COFACTOR`  | `Reaction → Compound`  | reaction uses a currency metabolite / cofactor (water, ATP, NAD(P)(H), CoA, quinones, ferredoxin, …) or a structureless participant |
| `CATALYZES`      | `Enzyme → Reaction`    | enzyme runs the reaction (linked by EC) |
| `POLYMERIZES_TO` | `Compound → Polymer`   | monomer polymerises into the material |
| `HAS_PROPERTY`   | `Polymer → Property`   | material exhibits a function/property |

### Why `USES_COFACTOR` exists (the multi-hop "make sense" rule)

A handful of molecules (water, H⁺, CO₂, ATP, NAD(P)(H), CoA, quinones, ferredoxin,
…) participate in a huge fraction of reactions. If they sit on the main
`SUBSTRATE_OF`/`PRODUCES` tracks, traversal "teleports" through them and produces
nonsense routes. So those participants — plus any structureless/placeholder
participant (a protein carrier, a generic chemical class) — are routed onto
`USES_COFACTOR` instead. The rule: **a backbone hop only ever connects two
concretely-structured molecules.**

A biosynthetic route is therefore an alternating
`(:Compound)-[:SUBSTRATE_OF]->(:Reaction)-[:PRODUCES]->(:Compound)...` walk over
the backbone only; chaining those fixed hops traces meaningful pathways of any
depth (TuringDB's dialect uses explicit repeated hops, not `*1..n`). Cofactor
context for any reaction is still available via its `USES_COFACTOR` edges.

## Why these two layers connect

The monomer `Compound` sits in both worlds: it is the *product* of a
biosynthetic route (metabolic layer) and the *input* to a polymer (property
layer). That single shared node is what turns "which enzymes make this
molecule" and "which material has this property" into one question:

> *biodegradable, heat-resistant materials whose monomer I can make from sugar* —
> see `examples/queries.cypher`, Use Case 3.

## Extending the schema

Natural next nodes, all joining on identifiers already present:

- `Paper` → `MENTIONS` → any node (the GraphRAG layer, deferred for now), keyed on DOI/PMID.
- `Organism` / `Strain` → `EXPRESSES` → `Enzyme`, for host selection.
- molecular graphs sampled from `Compound`/`Polymer` for GNN training, keyed on InChIKey / p-SMILES.
