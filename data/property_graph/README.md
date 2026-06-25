# Dataset: Polymer property graph (property / function layer)

A curated table of biodegradable / bio-based polymers, the monomers they are
built from, and the functions an engineer designs *by* ("I need heat resistance
and biodegradability"). This is the "graph of properties / functions associated
to biomaterials" half of the brief.

## Files

| File | What it is | Node/edge |
|------|------------|-----------|
| `polymers.csv` | biomaterials with thermal/mechanical properties + monomer link | `:Polymer` (+ `:POLYMERIZES_TO`) |
| `properties.csv` | property/function nodes (thermal, mechanical, functional) | `:Property` |
| `polymer_properties.csv` | which polymer exhibits which function | `:HAS_PROPERTY` |

## What it covers

Six polymers: PHB, PHBV, PLA, PGA, PBS, PCL. Each links to its monomer
`Compound` (which is where this layer joins the metabolic layer) and to a set
of `Property` nodes derived from its attributes:

- **Biodegradable** / **Bio-based feedstock** — functional flags.
- **Heat resistant** — Tm ≥ 150 °C.
- **Highly crystalline** — crystallinity ≥ 50 %.
- **Rigid** — high modulus, low elongation. **Flexible / elastomeric** — high elongation.

The derivation rules live in `derive_polymer_properties()` in
`data/build_seed_data.py` — edit the thresholds there to change how materials
map to functions.

## Property values / provenance

Property values (`tg_c`, `tm_c`, `tensile_mpa`, `youngs_gpa`, `elongation_pct`,
`crystallinity_pct`, `density`) are **representative literature values for neat
polymers**. Real values vary with grade, molecular weight, crystallinity and
processing, so treat them as order-of-magnitude anchors for the demo, not
datasheet specs. For real numbers, the natural upgrade is PoLyInfo
(NIMS, ~18k polymers, ~100 properties — registration-gated, non-commercial, no
bulk API) for experimental data, or PI1M / RadonPy for computed data. Keep
those out of the committed repo and load them locally, the same way as
RetroRules.

`psmiles` uses `*` to mark polymerisation points (p-SMILES), the standard
polymer-informatics representation and a ready input for a polymer GNN.

## Regenerate

```bash
python data/build_seed_data.py
```
