# Example use cases

Three worked examples on the seed graph. The Cypher is in
[`queries.cypher`](queries.cypher); the versioning demo is in
[`versioning_demo.py`](versioning_demo.py).

## 1. Retrosynthesis — "how do I biosynthesise this monomer?"

Trace a route from a feedstock to a target monomer, then read off the enzymes
you would need to express. This is the RetroRules-style question: given a target
molecule, enumerate biosynthetic routes back to available precursors.

On the seed graph, the PHB monomer (3-hydroxybutyrate) resolves to:
`glucose → pyruvate → acetyl-CoA → acetoacetyl-CoA → 3-hydroxybutanoyl-CoA →
3-hydroxybutyrate`, catalysed by PhaA / PhaB / PhaC.

Why TuringDB: deep multi-hop traversal is the whole game in retrosynthesis, and
it is exactly where most graph databases slow down. Variable-length path
queries over a large reaction network are the workload TuringDB is built for.

## 2. Property / function graph — "design by requirement"

Start from the functions you need (biodegradable + heat resistant) and walk
*backwards* to candidate materials and the monomers that make them. Or rank
materials by a numeric requirement (Tm, tensile strength) while constraining on
a function. This is the "function/property → biomolecule combinations" graph
from the brief.

Why TuringDB: rich, unlimited properties on nodes and edges mean the material
attributes and the function tags live on the same graph as the chemistry — no
join to an external store.

## 3. The payoff — one graph, asked across both layers

The reason to put both layers in *one* TuringDB graph rather than two CSVs:

> **"Biodegradable, heat-resistant materials whose monomer I can make from sugar."**

That single query crosses from material function (property layer) through the
monomer (the bridge) into biosynthetic reachability (metabolic layer). On the
seed graph it returns PHB and PLA. Try expressing that against two disconnected
datasets — you can't, without gluing them together first, which is precisely
what the shared `Compound.inchikey` does here.

### Versioning (TuringDB's headline differentiator)

`versioning_demo.py` shows the Git-style branching: an engineer hypothesises a
novel engineered enzyme that shortens the PHB route, branches the graph, adds
the speculative reaction, and re-runs the route count — all without touching the
validated graph on `main`. Merge it if the wet-lab validates, discard it if not.
No other production graph database has this built in, and for a research /
design workflow (reproducible experiments, audit trail, what-if exploration)
it is the most compelling part of the demo.

```bash
python examples/versioning_demo.py
```
