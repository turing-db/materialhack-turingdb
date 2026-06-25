# Dataset: RetroRules slice (metabolic / retrosynthesis layer)

A small, hand-curated slice of biosynthetic chemistry for bioplastic monomers.
It plays the role that [RetroRules](https://retrorules.org) plays at full scale,
but is tiny, fully open, and clones in seconds. Swap in real RetroRules data
with `load/load_retrorules.py` when you want depth (see below).

## Files

| File | What it is | Node/edge |
|------|------------|-----------|
| `compounds.csv` | metabolites, precursors, monomers, cofactors | `:Compound` |
| `enzymes.csv` | enzymes with EC numbers and UniProt IDs | `:Enzyme` |
| `reactions.csv` | biochemical reactions | `:Reaction` |
| `reaction_participants.csv` | which compound is substrate/product of which reaction | `:SUBSTRATE_OF` / `:PRODUCES` |

## What it covers

Two bioplastic routes that share central carbon metabolism, so the graph
branches the way a real metabolic network does:

- **PHB route:** glucose → (glycolysis) → pyruvate → acetyl-CoA → acetoacetyl-CoA
  → (R)-3-hydroxybutanoyl-CoA → **3-hydroxybutyrate** (the PHB monomer).
  Enzymes: PhaA (EC 2.3.1.9), PhaB (EC 1.1.1.36), PhaC (PHA synthase).
- **PLA route:** pyruvate → **lactate** (the PLA monomer), via lactate
  dehydrogenase (EC 1.1.1.27).

Succinate and glycolate (monomers of PBS and PGA) are present as compounds but
their upstream pathways are intentionally *not* modelled — they are hooks for
you to extend during the hackathon.

## Identifiers and the join key

- `inchikey` is computed from `smiles` with RDKit and is the join key to every
  other chemical source (see `schema/SCHEMA.md`).
- `kegg` / `chebi` are filled where confident. Blanks are intentional: CoA
  thioester intermediates carry no SMILES (the CoA moiety is large and not
  needed for the polymer linkage) and are identified by KEGG/ChEBI instead.
- Curated IDs should be reconciled against MNXref/RetroRules when you load the
  full data — the loader merges on `inchikey`, so duplicates collapse cleanly.

## Property values / provenance

Compound structures are standard. The pathway is the canonical
*Cupriavidus necator* PHB pathway and the homofermentative lactate pathway;
EC numbers and representative UniProt accessions are included for the enzymes.

## Growing this with real RetroRules data

RetroRules is **not** committed here. It is a ~2 GB SQLite file (~6M rows,
~15 tables) and inherits mixed licences from KEGG, MetaCyc, BiGG and Rhea, so it
cannot be redistributed in a public repo. Download it yourself from
<https://retrorules.org/dl>, then:

The raw sources are **not** committed (hundreds of MB, mixed upstream licences —
see the top-level `NOTICE`). Place the three open flat files in `data/external/`:
`retrorules_metanetx.csv` (RetroRules v3 templates, MetaNetX export),
`chem_prop.tsv` and `reac_prop.tsv` (MetaNetX/MNXref compound + reaction
properties). Then build the derived slice (committed to
`data/retrorules_expanded/`):

```bash
python data/expand_from_retrorules.py            # ~1500-compound cap, 2 hops
```

The expander matches the seed monomer InChIKeys against MetaNetX (tolerating the
neutral-acid vs ionized protonation difference), slices the reactions around
them, and emits this same CSV schema. `load/load_graph.py` then loads both
folders, deduplicating compounds on `inchikey` so the real reactions attach
directly to the seed monomers.

## Regenerate

```bash
python data/build_seed_data.py
```
