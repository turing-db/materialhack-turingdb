// ============================================================================
// Example queries for the MaterialHack x TuringDB biomaterials graph.
// Run via client.query("..."), the TuringDB shell, or the visualizer.
// They assume a graph is loaded (see load/load_graph.py or load/load_full_jsonl.py).
// ============================================================================


// ----------------------------------------------------------------------------
// USE CASE 1 — Retrosynthesis: how do I biosynthesise a monomer?
// A route alternates SUBSTRATE_OF (compound->reaction) and PRODUCES
// (reaction->compound). Cofactors live on USES_COFACTOR, off this backbone.
// ----------------------------------------------------------------------------

// 1a. Immediate precursors of the PHB monomer (one reaction back).
MATCH (sub:Compound)-[:SUBSTRATE_OF]->(rxn:Reaction)-[:PRODUCES]->(mono:Compound {name: "(R)-3-Hydroxybutanoic acid"})
RETURN sub.name AS precursor, rxn.ec AS ec, rxn.name AS reaction;

// 1b. A two-reaction backbone route into the PHB monomer.
//     Add more "-[:SUBSTRATE_OF]->(:Reaction)-[:PRODUCES]->(:Compound)" segments
//     to trace deeper routes.
MATCH (s:Compound)-[:SUBSTRATE_OF]->(r1:Reaction)-[:PRODUCES]->(mid:Compound)-[:SUBSTRATE_OF]->(r2:Reaction)-[:PRODUCES]->(mono:Compound {name: "(R)-3-Hydroxybutanoic acid"})
RETURN s.name AS start, mid.name AS intermediate, mono.name AS monomer
LIMIT 10;

// 1c. The enzymes that make the PHB monomer (enzyme -> reaction -> monomer).
MATCH (e:Enzyme)-[:CATALYZES]->(rxn:Reaction)-[:PRODUCES]->(mono:Compound {name: "(R)-3-Hydroxybutanoic acid"})
RETURN e.ec AS ec, e.name AS enzyme, rxn.name AS reaction;


// ----------------------------------------------------------------------------
// USE CASE 2 — Property / function graph: design by requirement.
// ----------------------------------------------------------------------------

// 2a. "I need a material that is biodegradable AND heat resistant."
//     The two requirements are two MATCH clauses on the same polymer (a join).
MATCH (mono:Compound)-[:POLYMERIZES_TO]->(p:Polymer)
MATCH (p)-[:HAS_PROPERTY]->(:Property {name: "Biodegradable"})
MATCH (p)-[:HAS_PROPERTY]->(:Property {name: "Heat resistant"})
RETURN p.name AS polymer, p.abbrev AS abbrev, mono.name AS monomer, p.tm_c AS melting_point_C
LIMIT 20;

// 2b. Rank biodegradable materials by heat resistance (numeric Tm).
MATCH (p:Polymer)-[:HAS_PROPERTY]->(:Property {name: "Biodegradable"})
WHERE p.tm_c >= 150
RETURN p.name AS polymer, p.tm_c AS Tm_C, p.tensile_mpa AS tensile_MPa
ORDER BY p.tm_c DESC;

// 2c. Which functions does each monomer give access to (via its polymers)?
//     One row per monomer/polymer/function.
MATCH (mono:Compound)-[:POLYMERIZES_TO]->(p:Polymer)-[:HAS_PROPERTY]->(f:Property)
WHERE mono.is_monomer = true
RETURN mono.name AS monomer, p.abbrev AS polymer, f.name AS function
ORDER BY mono.name;


// ----------------------------------------------------------------------------
// USE CASE 3 — The payoff: ONE graph, asked across both layers at once.
// "Biodegradable, heat-resistant materials, and a precursor of their monomer."
// Crosses the metabolic layer (precursor -> reaction -> monomer) and the
// property layer (monomer -> polymer -> properties) in a single query.
// ----------------------------------------------------------------------------
MATCH (mono:Compound)-[:POLYMERIZES_TO]->(p:Polymer)
MATCH (p)-[:HAS_PROPERTY]->(:Property {name: "Biodegradable"})
MATCH (p)-[:HAS_PROPERTY]->(:Property {name: "Heat resistant"})
MATCH (prec:Compound)-[:SUBSTRATE_OF]->(:Reaction)-[:PRODUCES]->(mono)
RETURN prec.name AS precursor, mono.name AS monomer, p.name AS material, p.abbrev AS abbrev
LIMIT 20;
