# Cupriavidus necator explorer

A browser UI for exploring the [`cupriavidus_necator`](../cupriavidus_necator)
graph, built by **reusing the [TuringDB Visualizer](https://github.com/turing-db/turingdb-visualizer)**
(React + Vite + Three.js / WebGL — GPU-instanced, handles ~20k nodes) and adding
a curated, organism-specific exploration layer on top.

Rather than fork the visualizer, this directory ships only the **customization
overlay** plus a setup script that fetches the upstream app at a pinned commit
and applies the overlay — so the PR stays small and tracks upstream cleanly.

## Quick start

```bash
cd cupriavidus_explorer
./setup.sh        # clone the pinned visualizer into ./app and apply the overlay
./run.sh          # ensure the graph is loaded, then start the explorer
# open http://localhost:8080   (or the printed Network URL)
```

Prereqs: Node ≥ 18 + npm, Python 3, and a TuringDB server. `run.sh` will load
the `cupriavidus_necator` graph from [`../cupriavidus_necator`](../cupriavidus_necator)
(run that directory's `load_graph.py` once if you haven't). Ports are overridable
via `TURING_FRONTEND_PORT` (default 8080) and `TURING_API_PORT` (default 6666).

## What the overlay adds

All additive — no upstream behaviour removed (`overlay/` mirrors the visualizer's
`src/` layout and is copied over the clone):

| File | Change |
|------|--------|
| `src/components/viewer/cupriavidus-panel.tsx` | **New** left dock: organism header, curated one-click preset queries, a *colour nodes by type* toggle + legend; auto-runs a starter view and auto-collapses when the node inspector opens. |
| `src/utils/cnecator-presets.ts` | **New** preset query definitions (PHA/PHB, Calvin cycle, H₂, central metabolism, overview) and the node-label → colour map. |
| `src/pages/viewer.tsx` | Mounts `<CupriavidusPanel/>`. |
| `src/stores/app.store.ts` | Defaults the selected graph to `cupriavidus_necator`. |

## Using it

- **Left panel** — click a preset to render that subgraph: e.g. *PHA / PHB
  biosynthesis*, *Calvin–Benson–Bassham cycle*, *RuBisCO*, *Hydrogen metabolism*,
  *Organism & all subsystems*.
- **Colour nodes by type** — Reaction (amber), Metabolite (green), GeneProduct
  (violet), Pathway (magenta), Compartment (teal), Species (blue).
- **Double-click** a node to expand its neighbours; **click** for the inspector.
- The upstream Cypher bar still works for ad-hoc queries. TuringDB's dialect has
  no `OPTIONAL MATCH` / `UNWIND` / `MERGE` / `IN`-lists — use explicit hops and
  `OR` chains. All presets `RETURN` node variables so they render on the canvas.

## Layout

```
cupriavidus_explorer/
├── README.md
├── setup.sh           ← clone pinned visualizer into app/ + apply overlay + npm install
├── run.sh             ← ensure graph loaded, then `npm run dev` in app/
├── ensure_graph.py    ← stdlib-only check/load of the graph over the REST API
├── .gitignore         ← ignores the generated app/
└── overlay/           ← files copied onto the upstream visualizer
    └── src/…
```

Upstream is pinned in `setup.sh` (`VIS_COMMIT`); bump it to track newer
visualizer releases.
