// Curated exploration presets for the Cupriavidus necator H16 graph.
// Each query RETURNs node variables so the visualizer renders the subgraph.
// Verified against the cupriavidus_necator graph (TuringDB Cypher subset:
// no OPTIONAL MATCH / UNWIND / MERGE / IN-lists; comma = join on shared var).

export const CNECATOR_GRAPH = 'cupriavidus_necator'

export interface Preset {
  label: string
  hint: string
  query: string
}

export interface PresetGroup {
  title: string
  icon: string // Blueprint icon name
  presets: Preset[]
}

export const PRESET_GROUPS: PresetGroup[] = [
  {
    title: 'Bioplastics · PHA / PHB',
    icon: 'lab-test',
    presets: [
      {
        label: 'PHA / PHB biosynthesis',
        hint: 'The PHAMetabolism subsystem and its reactions',
        query:
          "MATCH (p:Pathway)-[:hasEvent]->(r:Reaction) WHERE p.displayName = 'PHAMetabolism' RETURN p, r",
      },
      {
        label: 'PHB route + metabolites',
        hint: 'PHA reactions wired to the metabolites they produce',
        query:
          "MATCH (p:Pathway)-[:hasEvent]->(r:Reaction), (r)-[:output]->(m:Metabolite) WHERE p.displayName = 'PHAMetabolism' RETURN p, r, m",
      },
      {
        label: 'Acetoacetyl-CoA reductase (phaB)',
        hint: 'Reactions run by gene H16_A1439 and their products',
        query:
          "MATCH (g:GeneProduct)<-[:catalyzedBy]-(r:Reaction)-[:output]->(m:Metabolite) WHERE g.locusTag = 'H16_A1439' RETURN g, r, m",
      },
    ],
  },
  {
    title: 'CO₂ fixation · Calvin cycle',
    icon: 'globe',
    presets: [
      {
        label: 'Calvin–Benson–Bassham cycle',
        hint: 'CBB reactions and the genes that catalyse them',
        query:
          "MATCH (p:Pathway)-[:hasEvent]->(r:Reaction)-[:catalyzedBy]->(g:GeneProduct) WHERE p.displayName = 'Calvin cycle/Pentose phosphate pathway' RETURN p, r, g",
      },
      {
        label: 'RuBisCO reaction',
        hint: 'Ribulose-bisphosphate carboxylase: substrates → products',
        query:
          "MATCH (r:Reaction)-[:input]->(s:Metabolite), (r)-[:output]->(prod:Metabolite) WHERE r.displayName = 'Ribulose bisphosphate carboxylase' RETURN r, s, prod",
      },
      {
        label: 'CO₂-consuming reactions',
        hint: 'Every reaction that takes CO₂ (KEGG C00011) as a substrate',
        query:
          "MATCH (r:Reaction)-[:input]->(m:Metabolite) WHERE m.keggCompound = 'C00011' RETURN r, m",
      },
    ],
  },
  {
    title: 'Energy · H₂ & central metabolism',
    icon: 'flash',
    presets: [
      {
        label: 'Hydrogen metabolism',
        hint: 'The Hydrogen production subsystem ([NiFe] hydrogenase)',
        query:
          "MATCH (p:Pathway)-[:hasEvent]->(r:Reaction), (r)-[:output]->(m:Metabolite) WHERE p.displayName = 'Hydrogen production' RETURN p, r, m",
      },
      {
        label: 'Citric Acid Cycle',
        hint: 'TCA cycle reactions',
        query:
          "MATCH (p:Pathway)-[:hasEvent]->(r:Reaction) WHERE p.displayName = 'Citric Acid Cycle' RETURN p, r",
      },
    ],
  },
  {
    title: 'Overview',
    icon: 'diagram-tree',
    presets: [
      {
        label: 'Organism & all subsystems',
        hint: 'The species hub linked to its 209 metabolic subsystems',
        query: 'MATCH (p:Pathway)-[:species]->(s:Species) RETURN s, p',
      },
      {
        label: 'Compartments',
        hint: 'Cytosol / periplasm / extracellular and a sample of metabolites',
        query:
          'MATCH (c:Compartment)<-[:compartment]-(m:Metabolite) RETURN c, m LIMIT 150',
      },
    ],
  },
]

// The query run automatically when the explorer first opens.
export const DEFAULT_PRESET = PRESET_GROUPS[0].presets[1]

// Node colouring by label — distinct, legible hues (Blueprint palette).
export const LABEL_COLORS: Record<string, number> = {
  Reaction: 0xd1980b, // amber
  Metabolite: 0x29a634, // green
  GeneProduct: 0x7961db, // violet
  Pathway: 0xdb2c6f, // magenta
  Compartment: 0x00a396, // teal
  Species: 0x0385ff, // blue
}

export const LABEL_COLOR_HEX: Record<string, string> = {
  Reaction: '#d1980b',
  Metabolite: '#29a634',
  GeneProduct: '#7961db',
  Pathway: '#db2c6f',
  Compartment: '#00a396',
  Species: '#0385ff',
}
