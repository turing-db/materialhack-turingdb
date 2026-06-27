#!/usr/bin/env python3
"""
build_graph.py
==============
Build the Cupriavidus necator H16 graph from the BioModels genome-scale
metabolic model iCNH2025A (BioModels MODEL2502270001).

Parses the SBML (FBC v2 + groups) inside the COMBINE archive and emits the
node/edge parquet files consumed by `load_graph.py` (which calls the
`turing-parquet` bulk importer).

Graph model (a self-contained, organism-specific metabolic graph):
  Nodes:   Species, Compartment, Pathway, Reaction, Metabolite, GeneProduct
  Edges:   species, compartment, input, output, catalyzedBy, hasEvent

Run:  python build_graph.py
"""
import json
import os
import zipfile
import xml.etree.ElementTree as ET
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OMEX = os.path.join(HERE, "data", "iCNH2025A_Cnecator_GEM.omex")
SBML = os.path.join(HERE, "data", "model.xml")
OUT_NODES = os.path.join(HERE, "nodes.parquet")
OUT_EDGES = os.path.join(HERE, "edges.parquet")

# model.xml is large (8 MB) and derivable — extract it from the COMBINE archive if absent
if not os.path.exists(SBML):
    print(f"{SBML} missing; extracting from {OMEX}")
    with zipfile.ZipFile(OMEX) as z:
        z.extract("model.xml", os.path.join(HERE, "data"))

NS = {
    "s": "http://www.sbml.org/sbml/level3/version1/core",
    "fbc": "http://www.sbml.org/sbml/level3/version1/fbc/version2",
    "groups": "http://www.sbml.org/sbml/level3/version1/groups/version1",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
}

def q(prefix, tag):
    return f"{{{NS[prefix]}}}{tag}"

def fbc_attr(el, name):
    return el.get(q("fbc", name))

# ---- annotation parsing ----------------------------------------------------
def parse_annotations(el):
    """Return dict: namespace -> list[identifier] from identifiers.org RDF resources."""
    out = {}
    for li in el.iter(q("rdf", "li")):
        res = li.get(q("rdf", "resource"))
        if not res or "identifiers.org/" not in res:
            continue
        tail = res.split("identifiers.org/", 1)[1].strip("/")
        if "/" in tail:
            ns, ident = tail.split("/", 1)
        elif ":" in tail:
            ns, ident = tail.split(":", 1)
        else:
            continue
        out.setdefault(ns.lower(), []).append(ident)
    return out

def first(d, key):
    v = d.get(key)
    return v[0] if v else None

def clean(props):
    return {k: v for k, v in props.items() if v not in (None, "", [])}

# ---- GPR (gene-protein-reaction) parsing -----------------------------------
def parse_gpr(assoc):
    """Recursively render a geneProductAssociation into (rule_string, gene_set)."""
    genes = set()

    def render(el):
        tag = el.tag
        if tag == q("fbc", "geneProductRef"):
            g = fbc_attr(el, "geneProduct")
            genes.add(g)
            return g
        if tag == q("fbc", "and") or tag == q("fbc", "or"):
            op = " and " if tag.endswith("}and") else " or "
            return "(" + op.join(render(c) for c in el) + ")"
        for c in el:
            return render(c)
        return ""

    rule = render(assoc).strip()
    if rule.startswith("(") and rule.endswith(")") and "(" not in rule[1:-1]:
        rule = rule[1:-1]
    return rule, genes

# ---------------------------------------------------------------------------
print("parsing", SBML)
model = ET.parse(SBML).getroot().find(q("s", "model"))

nodes, edges = [], []

def add_node(nid, label, props):
    nodes.append({"id": nid, "label": label, "properties": json.dumps(clean(props))})

def add_edge(src, dst, rel, props=None):
    edges.append({"from": src, "to": dst, "relation": rel,
                  "properties": json.dumps(props or {})})

# ---- Species (organism) ----------------------------------------------------
model_ann = next((c for c in model if c.tag == q("s", "annotation")), None)
ann = parse_annotations(model_ann) if model_ann is not None else {}
SPECIES_ID = "SP_381666"
add_node(SPECIES_ID, "Species", {
    "displayName": "Cupriavidus necator",
    "name": model.get("name") or "Cupriavidus necator H16",
    "strain": "H16 (DSM 428 / ATCC 17699)",
    "taxId": first(ann, "taxonomy") or "381666",
    "assembly": first(ann, "assembly") or "GCF_004798725.1",
    "abbreviation": "CNE",
    "lineage": "Bacteria; Pseudomonadota; Betaproteobacteria; Burkholderiales; "
               "Burkholderiaceae; Cupriavidus",
    "sourceModel": "iCNH2025A",
    "sourceDb": "BioModels:MODEL2502270001",
    "schemaClass": "Species",
})

# ---- flux-bound parameters -------------------------------------------------
params = {}
lop = model.find(q("s", "listOfParameters"))
if lop is not None:
    for p in lop.findall(q("s", "parameter")):
        try:
            params[p.get("id")] = float(p.get("value"))
        except (TypeError, ValueError):
            pass

# ---- Compartments ----------------------------------------------------------
for c in model.find(q("s", "listOfCompartments")).findall(q("s", "compartment")):
    cid = c.get("id")
    a = parse_annotations(c)
    add_node(f"C_{cid}", "Compartment", {
        "displayName": c.get("name"), "name": c.get("name"),
        "biggId": first(a, "bigg.compartment") or cid,
        "sboTerm": c.get("sboTerm"), "schemaClass": "Compartment",
    })

# ---- Metabolites -----------------------------------------------------------
for sp in model.find(q("s", "listOfSpecies")).findall(q("s", "species")):
    mid = sp.get("id")
    a = parse_annotations(sp)
    charge = fbc_attr(sp, "charge")
    add_node(mid, "Metabolite", {
        "displayName": sp.get("name"), "name": sp.get("name"),
        "biggId": first(a, "bigg.metabolite"),
        "formula": fbc_attr(sp, "chemicalFormula"),
        "charge": int(charge) if charge not in (None, "") else None,
        "compartmentId": sp.get("compartment"),
        "chebi": first(a, "chebi"), "keggCompound": first(a, "kegg.compound"),
        "metanetx": first(a, "metanetx.chemical"), "biocyc": first(a, "biocyc"),
        "seedCompound": first(a, "seed.compound"), "hmdb": first(a, "hmdb"),
        "sboTerm": sp.get("sboTerm"), "schemaClass": "SimpleEntity",
    })
    if sp.get("compartment"):
        add_edge(mid, f"C_{sp.get('compartment')}", "compartment")

# ---- Gene products ---------------------------------------------------------
lgp = model.find(q("fbc", "listOfGeneProducts"))
if lgp is not None:
    for g in lgp.findall(q("fbc", "geneProduct")):
        gid = fbc_attr(g, "id")
        a = parse_annotations(g)
        add_node(f"G_{gid}", "GeneProduct", {
            "displayName": fbc_attr(g, "label") or gid,
            "label": fbc_attr(g, "label") or gid,
            "locusTag": fbc_attr(g, "label") or gid,
            "uniprot": first(a, "uniprot"), "ncbiGene": first(a, "ncbigene"),
            "asap": first(a, "asap"), "ecogene": first(a, "ecogene"),
            "schemaClass": "ReferenceGeneProduct",
        })

# ---- Reactions -------------------------------------------------------------
for r in model.find(q("s", "listOfReactions")).findall(q("s", "reaction")):
    rid = r.get("id")
    a = parse_annotations(r)
    gpr_rule, gpr_genes = "", set()
    assoc = r.find(q("fbc", "geneProductAssociation"))
    if assoc is not None:
        gpr_rule, gpr_genes = parse_gpr(assoc)
    reactome_hsa = [x for x in a.get("reactome", []) if x.startswith("R-HSA-")]
    add_node(rid, "Reaction", {
        "displayName": r.get("name"), "name": r.get("name"),
        "biggId": first(a, "bigg.reaction"),
        "reversible": r.get("reversible") == "true",
        "lowerFluxBound": params.get(fbc_attr(r, "lowerFluxBound")),
        "upperFluxBound": params.get(fbc_attr(r, "upperFluxBound")),
        "ecNumber": first(a, "ec-code"), "metanetx": first(a, "metanetx.reaction"),
        "biocyc": first(a, "biocyc"), "rhea": first(a, "rhea"),
        "seedReaction": first(a, "seed.reaction"),
        "reactomeHsa": ";".join(reactome_hsa) if reactome_hsa else None,
        "gpr": gpr_rule or None, "geneCount": len(gpr_genes),
        "sboTerm": r.get("sboTerm"), "schemaClass": "Reaction",
    })
    add_edge(rid, SPECIES_ID, "species")
    lr = r.find(q("s", "listOfReactants"))
    if lr is not None:
        for sr in lr.findall(q("s", "speciesReference")):
            add_edge(rid, sr.get("species"), "input",
                     {"stoichiometry": float(sr.get("stoichiometry", 1))})
    lp = r.find(q("s", "listOfProducts"))
    if lp is not None:
        for sr in lp.findall(q("s", "speciesReference")):
            add_edge(rid, sr.get("species"), "output",
                     {"stoichiometry": float(sr.get("stoichiometry", 1))})
    for g in sorted(gpr_genes):
        add_edge(rid, f"G_{g}", "catalyzedBy")

# ---- Pathways (subsystems from groups) -------------------------------------
lg = model.find(q("groups", "listOfGroups"))
if lg is not None:
    for grp in lg.findall(q("groups", "group")):
        gid = grp.get(q("groups", "id"))
        name = (grp.get(q("groups", "name")) or "").strip()
        members = grp.find(q("groups", "listOfMembers"))
        member_ids = [m.get(q("groups", "idRef"))
                      for m in members.findall(q("groups", "member"))] if members is not None else []
        pid = f"P_{gid}"
        add_node(pid, "Pathway", {
            "displayName": name, "name": name, "groupId": gid,
            "kind": grp.get(q("groups", "kind")), "sboTerm": grp.get("sboTerm"),
            "numReactions": len(member_ids),
            "source": "BioModels iCNH2025A subsystem", "schemaClass": "Pathway",
        })
        add_edge(pid, SPECIES_ID, "species")
        for m in member_ids:
            add_edge(pid, m, "hasEvent")

# ---- write parquet ---------------------------------------------------------
ndf = pd.DataFrame(nodes, columns=["id", "label", "properties"])
edf = pd.DataFrame(edges, columns=["from", "to", "relation", "properties"])
ndf.to_parquet(OUT_NODES, index=False)
edf.to_parquet(OUT_EDGES, index=False)
print(f"nodes: {len(ndf)} -> {OUT_NODES}")
print(ndf["label"].value_counts().to_string())
print(f"\nedges: {len(edf)} -> {OUT_EDGES}")
print(edf["relation"].value_counts().to_string())
