// ============================================================================
// Example queries for the TuringDB biomaterials starter graph.
// Run these in the TuringDB shell / visualizer, or via client.query(...).
// They assume the seed graph is loaded (see load/load_graph.py).
// ============================================================================


// ----------------------------------------------------------------------------
// USE CASE 1 — Retrosynthesis: how do I biosynthesise a monomer?
// ----------------------------------------------------------------------------

// 1a. Full biosynthetic route from a feedstock to the PHB monomer.
//     Alternating SUBSTRATE_OF (compound->reaction) and PRODUCES
//     (reaction->compound) edges trace the pathway.
MATCH route = (feed:Compound {role: "feedstock"})
              -[:SUBSTRATE_OF|PRODUCES*1..14]->
              (mono:Compound {name: "(R)-3-Hydroxybutanoic acid"})
RETURN route;

// 1b. The enzymes you would need to express, in order, for that route.
MATCH (feed:Compound {role: "feedstock"})
      -[:SUBSTRATE_OF|PRODUCES*1..14]->
      (mono:Compound {is_monomer: true})
MATCH (e:Enzyme)-[:CATALYZES]->(rxn:Reaction)<-[:SUBSTRATE_OF]-(:Compound)
RETURN DISTINCT mono.name AS monomer, e.name AS enzyme, e.ec AS ec, e.uniprot AS uniprot;

// 1c. One hop back: immediate precursors of the PHB monomer.
MATCH (rxn:Reaction)-[:PRODUCES]->(m:Compound {name: "(R)-3-Hydroxybutanoic acid"})
MATCH (pre:Compound)-[:SUBSTRATE_OF]->(rxn)
RETURN rxn.name AS reaction, collect(pre.name) AS precursors;


// ----------------------------------------------------------------------------
// USE CASE 2 — Property / function graph: design by requirement.
// ----------------------------------------------------------------------------

// 2a. "I need a material that is biodegradable AND heat resistant."
//     Return the polymer and the monomer it is built from.
MATCH (mono:Compound)-[:POLYMERIZES_TO]->(p:Polymer)-[:HAS_PROPERTY]->(f:Property)
WHERE f.name IN ["Biodegradable", "Heat resistant"]
WITH p, mono, collect(f.name) AS functions
WHERE size(functions) = 2
RETURN p.name AS polymer, mono.name AS monomer, p.tm_c AS melting_point_C, functions;

// 2b. Rank candidate biomaterials by a numeric requirement (heat resistance),
//     keeping only biodegradable ones.
MATCH (p:Polymer)-[:HAS_PROPERTY]->(:Property {name: "Biodegradable"})
WHERE p.tm_c >= 150
RETURN p.name AS polymer, p.tm_c AS Tm_C, p.tensile_mpa AS tensile_MPa
ORDER BY p.tm_c DESC;

// 2c. Which functions does each monomer give access to (via its polymers)?
MATCH (mono:Compound {is_monomer: true})-[:POLYMERIZES_TO]->(:Polymer)-[:HAS_PROPERTY]->(f:Property)
RETURN mono.name AS monomer, collect(DISTINCT f.name) AS achievable_functions;


// ----------------------------------------------------------------------------
// USE CASE 3 — The payoff: ONE graph, asked across both layers at once.
// "Biodegradable, heat-resistant materials whose monomer I can make from sugar."
// ----------------------------------------------------------------------------
MATCH (feed:Compound {role: "feedstock"})
      -[:SUBSTRATE_OF|PRODUCES*1..14]->
      (mono:Compound)-[:POLYMERIZES_TO]->(p:Polymer)
MATCH (p)-[:HAS_PROPERTY]->(:Property {name: "Biodegradable"})
MATCH (p)-[:HAS_PROPERTY]->(:Property {name: "Heat resistant"})
RETURN DISTINCT feed.name AS feedstock, mono.name AS monomer, p.name AS material;
