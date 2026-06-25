#!/usr/bin/env python3
"""
build_seed_data.py
==================
Generates the curated seed graph for the TuringDB biomaterials starter.

It does two things:
  1. Defines a small, hand-curated slice of biosynthetic chemistry (the kind of
     data you would otherwise pull from RetroRules) plus a biomaterial property
     graph.
  2. Uses RDKit to compute a *canonical SMILES* and *InChIKey* for every compound
     that has a structure. The InChIKey is the universal join key that stitches
     the metabolic layer to the polymer/property layer, so we compute it
     programmatically rather than hand-typing it (hand-typed InChIKeys are a
     classic source of silent join failures).

Outputs (written next to this script):
  retrorules_slice/compounds.csv
  retrorules_slice/enzymes.csv
  retrorules_slice/reactions.csv
  retrorules_slice/reaction_participants.csv
  property_graph/polymers.csv
  property_graph/properties.csv
  property_graph/polymer_properties.csv
  ../load/nodes.jsonl
  ../load/edges.jsonl

Run:  python data/build_seed_data.py
"""

import csv
import json
import os

from rdkit import Chem
from rdkit.Chem import inchi

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.join(HERE, "retrorules_slice")
PG = os.path.join(HERE, "property_graph")
LOAD = os.path.abspath(os.path.join(HERE, "..", "load"))


def canon(smiles):
    """Return (canonical_smiles, inchikey) or ('', '') if no structure given."""
    if not smiles:
        return "", ""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"RDKit could not parse SMILES: {smiles!r}")
    return Chem.MolToSmiles(mol), inchi.MolToInchiKey(mol)


# --------------------------------------------------------------------------
# 1. COMPOUNDS  (metabolites, precursors, monomers)
# --------------------------------------------------------------------------
# role: feedstock | intermediate | cofactor | monomer
# kegg / chebi are filled where we are confident; blanks are intentional and
# are reconciled automatically when you run load_retrorules.py against the
# full RetroRules / MNXref data. CoA-thioester intermediates carry no SMILES
# here (the CoA moiety is large and not needed for the polymer linkage); they
# are identified by KEGG/ChEBI and get an InChIKey on full load.
COMPOUNDS = [
    # id,             name,                         smiles,                  role,         kegg,     chebi,    is_monomer
    ("cpd_glucose",   "D-Glucose",                  "OC[C@H]1O[C@@H](O)[C@H](O)[C@@H](O)[C@@H]1O", "feedstock",   "C00031", "17634", False),
    ("cpd_pyruvate",  "Pyruvate",                   "CC(=O)C(=O)O",          "intermediate","C00022", "15361", False),
    ("cpd_accoa",     "Acetyl-CoA",                 "",                      "intermediate","C00024", "15351", False),
    ("cpd_aacoa",     "Acetoacetyl-CoA",            "",                      "intermediate","C00332", "15345", False),
    ("cpd_3hbcoa",    "(R)-3-Hydroxybutanoyl-CoA",  "",                      "intermediate","",       "",      False),
    ("cpd_3hb",       "(R)-3-Hydroxybutanoic acid", "C[C@@H](O)CC(=O)O",     "monomer",     "C01089", "",      True),
    ("cpd_lactate",   "(S)-Lactic acid",            "C[C@H](O)C(=O)O",       "monomer",     "C00186", "422",   True),
    ("cpd_succinate", "Succinic acid",              "OC(=O)CCC(=O)O",        "monomer",     "C00042", "15741", True),
    ("cpd_glycolate", "Glycolic acid",              "OCC(=O)O",              "monomer",     "C00160", "17497", True),
    # cofactors (kept light; useful for balanced reactions and realism)
    ("cpd_coa",       "Coenzyme A",                 "",                      "cofactor",    "C00010", "15346", False),
    ("cpd_nadph",     "NADPH",                      "",                      "cofactor",    "C00005", "16474", False),
]

# --------------------------------------------------------------------------
# 2. ENZYMES
# --------------------------------------------------------------------------
ENZYMES = [
    # id,          name,                              ec,         gene,   organism,            uniprot
    ("enz_pdh",    "Pyruvate dehydrogenase complex",  "1.2.4.1",  "aceE", "Escherichia coli",  "P0AFG8"),
    ("enz_phaA",   "Beta-ketothiolase (PhaA)",        "2.3.1.9",  "phaA", "Cupriavidus necator","P14611"),
    ("enz_phaB",   "Acetoacetyl-CoA reductase (PhaB)","1.1.1.36", "phaB", "Cupriavidus necator","P14697"),
    ("enz_phaC",   "PHA synthase (PhaC)",             "2.3.1.-",  "phaC", "Cupriavidus necator","P23608"),
    ("enz_ldh",    "L-lactate dehydrogenase",         "1.1.1.27", "ldhA", "Escherichia coli",  "P52643"),
]

# --------------------------------------------------------------------------
# 3. REACTIONS  +  PARTICIPANTS (compound -[role]- reaction)
# --------------------------------------------------------------------------
# Each reaction: id, name, ec, source, [(compound_id, role)] where role is
# 'substrate' or 'product'. enzyme link is by ec via CATALYZES at load time.
REACTIONS = [
    ("rxn_glyc", "Glycolysis (summary): Glucose -> 2 Pyruvate", "", "summary", [
        ("cpd_glucose", "substrate"),
        ("cpd_pyruvate", "product"),
    ]),
    ("rxn_pdh", "Pyruvate -> Acetyl-CoA", "1.2.4.1", "curated", [
        ("cpd_pyruvate", "substrate"), ("cpd_coa", "substrate"),
        ("cpd_accoa", "product"),
    ]),
    ("rxn_phaA", "2 Acetyl-CoA -> Acetoacetyl-CoA", "2.3.1.9", "curated", [
        ("cpd_accoa", "substrate"),
        ("cpd_aacoa", "product"), ("cpd_coa", "product"),
    ]),
    ("rxn_phaB", "Acetoacetyl-CoA -> (R)-3-Hydroxybutanoyl-CoA", "1.1.1.36", "curated", [
        ("cpd_aacoa", "substrate"), ("cpd_nadph", "substrate"),
        ("cpd_3hbcoa", "product"),
    ]),
    ("rxn_phaC", "(R)-3-Hydroxybutanoyl-CoA -> 3-Hydroxybutyrate (PHB monomer)", "2.3.1.-", "curated", [
        ("cpd_3hbcoa", "substrate"),
        ("cpd_3hb", "product"), ("cpd_coa", "product"),
    ]),
    ("rxn_ldh", "Pyruvate -> Lactate", "1.1.1.27", "curated", [
        ("cpd_pyruvate", "substrate"), ("cpd_nadph", "substrate"),
        ("cpd_lactate", "product"),
    ]),
]

# enzyme <-> reaction by EC
ENZYME_FOR_RXN = {
    "rxn_pdh": "enz_pdh",
    "rxn_phaA": "enz_phaA",
    "rxn_phaB": "enz_phaB",
    "rxn_phaC": "enz_phaC",
    "rxn_ldh": "enz_ldh",
}

# --------------------------------------------------------------------------
# 4. POLYMERS  (biomaterials)  + monomer links
# --------------------------------------------------------------------------
# Property values are representative literature values for neat polymers; they
# vary with grade, molecular weight, crystallinity and processing. Treat them
# as order-of-magnitude anchors for the demo, not datasheet specs.
# psmiles uses '*' for polymerization points.
POLYMERS = [
    # id,        name,                            abbrev, psmiles,            monomer_id,     tg_c, tm_c, tensile_mpa, youngs_gpa, elong_pct, cryst_pct, density, biodegradable, bio_based
    ("pol_phb",  "Poly(3-hydroxybutyrate)",       "PHB",  "*O[C@@H](C)CC(=O)*", "cpd_3hb",     4,   175,  40,   3.5,  5,    60, 1.25, True, True),
    ("pol_phbv", "Poly(3HB-co-3HV)",              "PHBV", "*OC(C)CC(=O)*",      "cpd_3hb",     0,   150,  25,   1.2,  20,   55, 1.23, True, True),
    ("pol_pla",  "Polylactic acid",               "PLA",  "*OC(C)C(=O)*",       "cpd_lactate", 58,  155,  60,   3.5,  6,    40, 1.24, True, True),
    ("pol_pga",  "Polyglycolic acid",             "PGA",  "*OCC(=O)*",          "cpd_glycolate",38, 225,  90,   7.0,  15,   50, 1.53, True, True),
    ("pol_pbs",  "Polybutylene succinate",        "PBS",  "*OCCCCOC(=O)CCC(=O)*","cpd_succinate",-32,114, 33,   0.6,  400,  40, 1.26, True, True),
    ("pol_pcl",  "Polycaprolactone",              "PCL",  "*OCCCCCC(=O)*",      "",            -60,  60,  22,   0.4,  800,  45, 1.14, True, False),
]

# --------------------------------------------------------------------------
# 5. PROPERTY / FUNCTION NODES  + polymer -> property links
# --------------------------------------------------------------------------
# These are the "function / property" nodes from the brief: the things an
# engineer searches *by* ("I need heat resistance + biodegradability").
PROPERTIES = [
    ("prop_biodeg",   "Biodegradable",        "functional", "Breaks down under industrial or marine/soil conditions"),
    ("prop_heat",     "Heat resistant",       "thermal",    "Melting point above ~150 C; tolerates processing/use heat"),
    ("prop_rigid",    "Rigid",                "mechanical", "High Young's modulus, low elongation at break"),
    ("prop_flexible", "Flexible / elastomeric","mechanical","Low modulus, high elongation at break"),
    ("prop_crystal",  "Highly crystalline",   "thermal",    "Crystallinity >= 50 percent"),
    ("prop_biobased", "Bio-based feedstock",  "functional", "Monomer derived from renewable/biological carbon"),
]

# polymer -> property edges (derived below from rules, plus a couple explicit)
def derive_polymer_properties():
    edges = []
    for p in POLYMERS:
        (pid, name, abbrev, psmiles, monomer_id, tg, tm, tensile, youngs,
         elong, cryst, density, biodeg, biobased) = p
        if biodeg:
            edges.append((pid, "prop_biodeg"))
        if biobased:
            edges.append((pid, "prop_biobased"))
        if tm is not None and tm >= 150:
            edges.append((pid, "prop_heat"))
        if cryst is not None and cryst >= 50:
            edges.append((pid, "prop_crystal"))
        if youngs is not None and youngs >= 3.0 and (elong is not None and elong <= 10):
            edges.append((pid, "prop_rigid"))
        if elong is not None and elong >= 100:
            edges.append((pid, "prop_flexible"))
    return edges


# ==========================================================================
# WRITE OUTPUTS
# ==========================================================================
def main():
    os.makedirs(RR, exist_ok=True)
    os.makedirs(PG, exist_ok=True)
    os.makedirs(LOAD, exist_ok=True)

    nodes_jsonl = []
    edges_jsonl = []

    # ---- compounds ----
    comp_rows = []
    for (cid, name, smiles, role, kegg, chebi, is_mono) in COMPOUNDS:
        csmiles, ikey = canon(smiles)
        row = {
            "id": cid, "name": name, "smiles": csmiles, "inchikey": ikey,
            "kegg": kegg, "chebi": chebi, "role": role,
            "is_monomer": str(is_mono).lower(),
        }
        comp_rows.append(row)
        nodes_jsonl.append({"id": cid, "label": "Compound", "properties": row})
    write_csv(os.path.join(RR, "compounds.csv"),
              ["id", "name", "smiles", "inchikey", "kegg", "chebi", "role", "is_monomer"],
              comp_rows)

    # ---- enzymes ----
    enz_rows = []
    for (eid, name, ec, gene, org, uniprot) in ENZYMES:
        row = {"id": eid, "name": name, "ec": ec, "gene": gene,
               "organism": org, "uniprot": uniprot}
        enz_rows.append(row)
        nodes_jsonl.append({"id": eid, "label": "Enzyme", "properties": row})
    write_csv(os.path.join(RR, "enzymes.csv"),
              ["id", "name", "ec", "gene", "organism", "uniprot"], enz_rows)

    # ---- reactions + participants ----
    rxn_rows = []
    part_rows = []
    for (rid, name, ec, source, parts) in REACTIONS:
        row = {"id": rid, "name": name, "ec": ec, "source": source}
        rxn_rows.append(row)
        nodes_jsonl.append({"id": rid, "label": "Reaction", "properties": row})
        for (cid, prole) in parts:
            part_rows.append({"compound_id": cid, "reaction_id": rid, "role": prole})
            if prole == "substrate":
                edges_jsonl.append({"from": cid, "to": rid, "type": "SUBSTRATE_OF"})
            else:
                edges_jsonl.append({"from": rid, "to": cid, "type": "PRODUCES"})
        # enzyme -> reaction
        eid = ENZYME_FOR_RXN.get(rid)
        if eid:
            edges_jsonl.append({"from": eid, "to": rid, "type": "CATALYZES"})
    write_csv(os.path.join(RR, "reactions.csv"),
              ["id", "name", "ec", "source"], rxn_rows)
    write_csv(os.path.join(RR, "reaction_participants.csv"),
              ["compound_id", "reaction_id", "role"], part_rows)

    # ---- polymers + monomer links ----
    pol_rows = []
    for p in POLYMERS:
        (pid, name, abbrev, psmiles, monomer_id, tg, tm, tensile, youngs,
         elong, cryst, density, biodeg, biobased) = p
        row = {
            "id": pid, "name": name, "abbrev": abbrev, "psmiles": psmiles,
            "monomer_id": monomer_id, "tg_c": tg, "tm_c": tm,
            "tensile_mpa": tensile, "youngs_gpa": youngs,
            "elongation_pct": elong, "crystallinity_pct": cryst,
            "density": density, "biodegradable": str(biodeg).lower(),
            "bio_based": str(biobased).lower(),
        }
        pol_rows.append(row)
        node_props = {k: v for k, v in row.items() if k != "monomer_id"}
        nodes_jsonl.append({"id": pid, "label": "Polymer", "properties": node_props})
        if monomer_id:
            edges_jsonl.append({"from": monomer_id, "to": pid, "type": "POLYMERIZES_TO"})
    write_csv(os.path.join(PG, "polymers.csv"),
              ["id", "name", "abbrev", "psmiles", "monomer_id", "tg_c", "tm_c",
               "tensile_mpa", "youngs_gpa", "elongation_pct", "crystallinity_pct",
               "density", "biodegradable", "bio_based"], pol_rows)

    # ---- property nodes ----
    prop_rows = []
    for (pid, name, kind, desc) in PROPERTIES:
        row = {"id": pid, "name": name, "kind": kind, "description": desc}
        prop_rows.append(row)
        nodes_jsonl.append({"id": pid, "label": "Property", "properties": row})
    write_csv(os.path.join(PG, "properties.csv"),
              ["id", "name", "kind", "description"], prop_rows)

    # ---- polymer -> property edges ----
    pp_rows = []
    for (pol_id, prop_id) in derive_polymer_properties():
        pp_rows.append({"polymer_id": pol_id, "property_id": prop_id})
        edges_jsonl.append({"from": pol_id, "to": prop_id, "type": "HAS_PROPERTY"})
    write_csv(os.path.join(PG, "polymer_properties.csv"),
              ["polymer_id", "property_id"], pp_rows)

    # ---- combined JSONL for native TuringDB import ----
    with open(os.path.join(LOAD, "nodes.jsonl"), "w") as f:
        for n in nodes_jsonl:
            f.write(json.dumps(n) + "\n")
    with open(os.path.join(LOAD, "edges.jsonl"), "w") as f:
        for e in edges_jsonl:
            f.write(json.dumps(e) + "\n")

    print(f"compounds : {len(comp_rows)}")
    print(f"enzymes   : {len(enz_rows)}")
    print(f"reactions : {len(rxn_rows)}  (participants: {len(part_rows)})")
    print(f"polymers  : {len(pol_rows)}")
    print(f"properties: {len(prop_rows)}  (polymer->property edges: {len(pp_rows)})")
    print(f"nodes.jsonl: {len(nodes_jsonl)}  edges.jsonl: {len(edges_jsonl)}")


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)


if __name__ == "__main__":
    main()
