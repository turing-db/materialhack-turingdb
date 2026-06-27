// Example queries for the Cupriavidus necator H16 graph (TuringDB dialect).
//   client.set_graph("cupriavidus_necator")
// Notes: TuringDB's Cypher subset has no OPTIONAL MATCH, UNWIND, MERGE, or
// IN-lists; multi-hop uses explicit repeated hops, not *1..n.

// --- 1. The organism --------------------------------------------------------
MATCH (s:Species)
RETURN s.displayName, s.strain, s.taxId, s.assembly, s.sourceDb;

// --- 2. Signature trait: PHA / PHB bioplastic biosynthesis ------------------
MATCH (p:Pathway)-[:hasEvent]->(r:Reaction)
WHERE p.displayName = 'PHAMetabolism'
RETURN r.displayName, r.biggId, r.reversible, r.gpr;

// --- 3. CO2 fixation: Calvin–Benson–Bassham cycle enzymes (by gene) ---------
MATCH (p:Pathway)-[:hasEvent]->(r:Reaction)-[:catalyzedBy]->(g:GeneProduct)
WHERE p.displayName = 'Calvin cycle/Pentose phosphate pathway'
RETURN r.displayName, g.locusTag;

// --- 4. RuBisCO: substrates and products with stoichiometry -----------------
MATCH (r:Reaction)-[e:input]->(m:Metabolite)
WHERE r.displayName = 'Ribulose bisphosphate carboxylase'
RETURN m.displayName, m.formula, e.stoichiometry;

MATCH (r:Reaction)-[e:output]->(m:Metabolite)
WHERE r.displayName = 'Ribulose bisphosphate carboxylase'
RETURN m.displayName, m.formula, e.stoichiometry;

// --- 5. What does a gene do? all reactions catalysed by a locus tag ---------
MATCH (g:GeneProduct)<-[:catalyzedBy]-(r:Reaction)
WHERE g.locusTag = 'H16_A1439'
RETURN r.displayName, r.biggId;

// --- 6. Largest metabolic subsystems ---------------------------------------
MATCH (p:Pathway)
RETURN p.displayName, p.numReactions
ORDER BY p.numReactions DESC LIMIT 15;

// --- 7. Reactions that consume CO2 (carbon-fixing / carboxylation) ----------
MATCH (r:Reaction)-[:input]->(m:Metabolite)
WHERE m.keggCompound = 'C00011'
RETURN r.displayName, r.biggId;

// --- 8. Two-hop biosynthesis: metabolite -> reaction -> product -------------
MATCH (a:Metabolite)<-[:input]-(r:Reaction)-[:output]->(b:Metabolite)
WHERE a.biggId = 'rb15bp'
RETURN a.displayName, r.displayName, b.displayName;

// --- 9. Bridge to the human Reactome graph (shared reaction cross-refs) ------
MATCH (r:Reaction)
WHERE r.reactomeHsa IS NOT NULL
RETURN r.displayName, r.biggId, r.reactomeHsa LIMIT 20;
