#!/usr/bin/env python3
"""
expand_from_retrorules.py
=========================
Expands the curated seed graph (data/retrorules_slice) with REAL biosynthetic
chemistry from three open MetaNetX/RetroRules flat files, then emits the result
in the seed CSV schema so the two merge on ``inchikey`` at load time.

Inputs (place under data/external/ — NOT committed, see .gitignore + NOTICE):
  retrorules_metanetx.csv   RetroRules v3 reaction templates (MetaNetX-derived).
      columns: TEMPLATE_ID, SCORE, TEMPLATE(=SMARTS), REACTIONS(=;-sep MNXR ids),
               RADII, REACTIONS_COUNT, ECS(=;-sep EC numbers), ECS_COUNT,
               RADIUS_MIN, RADIUS_MAX, VALID(=True/False), DATASETS
  reac_prop.tsv             MetaNetX/MNXref reaction properties (388 '#' comment
      lines, then '#ID\tmnx_equation\treference\tclassifs\tis_balanced\tis_transport').
      Equation: "1 MNXM..@MNXD1 + ... = 1 MNXM..@MNXD1 + ...".
  chem_prop.tsv             MetaNetX/MNXref compound properties (~1.5M rows, 810
      MB -> STREAMED). header:
        '#ID\tname\treference\tformula\tcharge\tmass\tInChI\tInChIKey\tSMILES'

Making multi-hop traversal meaningful
  A few molecules (water, H+, CO2, ATP, NAD(P)(H), CoA, ...) participate in a
  huge fraction of reactions. Treating them as ordinary path nodes produces
  nonsense routes ("fluoride -> NADH -> 3-hydroxybutyrate"). So we classify these
  *currency metabolites* (curated InChIKey/name set) and:
    * mark their Compound nodes role=cofactor / is_currency=true,
    * keep them as participants but route them onto USES_COFACTOR edges at load
      time (the load step reads the compound role), NOT the SUBSTRATE_OF/PRODUCES
      backbone, so variable-length backbone queries follow real chemistry,
    * never expand the slice *through* them.
  We also drop transport reactions (is_transport=T — same molecule moved across a
  compartment, not a real transformation) and degenerate reactions whose carbon
  backbone is unchanged.

The InChIKey join gotcha (verified against the real file)
  MetaNetX stores the *ionized* species, so its full InChIKey differs from the
  seed's *neutral acid* in the final (charge) block (-N vs -M/-L). Match in tiers:
  full -> first 25 chars (connectivity+stereo) -> first 14 (connectivity only),
  decided by stereo agreement then chemical-name similarity. Seed-anchor compounds
  are emitted with the SEED's InChIKey + id so the load-time merge collapses them
  onto the existing seed monomer node.

Run:
  python data/expand_from_retrorules.py                       # defaults
  python data/expand_from_retrorules.py --max-compounds 3000 --max-hops 3
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher

csv.field_size_limit(10_000_000)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))

MNXM_RE = re.compile(r"MNXM\d+")
EC_FULL_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")

# Curated currency metabolites by InChIKey connectivity block (first 14 chars).
# These are the universal cofactors/inorganics that, if walked through, make
# multi-hop paths meaningless. Stable across InChI versions.
CURRENCY_IK14 = {
    "XLYOFNOQVPJJNP",  # water
    "GPRLSGONYQIRFK",  # H+ / proton (also "PMF" in MNXref)
    "CURLTUGMZLYLDI",  # CO2
    "MYMOFIZGZYHOMD",  # O2 (dioxygen)
    "MHAJPDPJQMAIIY",  # hydrogen peroxide
    "QGZKDVFQNNGYKY",  # ammonia / ammonium
    "NBIIXXVUZAFLBC",  # phosphate (Pi)
    "XPPKVPWEQAFLFU",  # diphosphate (PPi)
    "BVKZGUZCCUSVTD",  # carbonic acid / bicarbonate
    "ZKHQWZAMYRWXGA",  # ATP
    "XTWYTFMLZFPYCI",  # ADP
    "UDMBCSSLTHHNCD",  # AMP
    "XKMLYUALXHKNFT",  # GTP
    "QGWNDRXFNXRZMB",  # GDP
    "RQFCJASXJCIDSX",  # GMP
    "PGAVKCOVUIYSFO",  # UTP
    "XCCTYIAWTASOJW",  # UDP
    "DJJCXFVJDGTHFX",  # UMP
    "PCDQPRRSZKQHHS",  # CTP
    "ZWIADYZPOWUWEW",  # CDP
    "IERHLVCPSMICTF",  # CMP
    "BAWFJGJZGIEFAR",  # NAD+
    "BOPGDPNILDQYTO",  # NADH
    "XJLXINKUBYWONI",  # NADP+
    "ACFIXJIJDZMPPO",  # NADPH
    "VWWQXMAJTJZDQX",  # FAD
    "YPZRHBJKEMOYQH",  # FADH2
    "FVTCRASFADXXNN",  # FMN
    "RGJOEKWQDUBAIZ",  # coenzyme A
    "QAOWNCQODCNURD",  # sulfate
    "RWSOTUBLDIXVET",  # hydrogen sulfide
    "BVKZGUZCCUSVTD",  # bicarbonate (dup-safe)
}
CURRENCY_NAMES = {
    "h2o", "water", "h(+)", "h+", "proton", "oh(-)", "hydroxide", "co2",
    "carbon dioxide", "o2", "dioxygen", "oxygen", "nh3", "nh4(+)", "ammonia",
    "ammonium", "hco3(-)", "bicarbonate", "hydrogencarbonate", "h2o2",
    "hydrogen peroxide", "phosphate", "orthophosphate", "diphosphate",
    "pyrophosphate", "ppi", "atp", "adp", "amp", "gtp", "gdp", "gmp", "utp",
    "udp", "ump", "ctp", "cdp", "cmp", "itp", "idp", "imp", "nad(+)", "nad",
    "nadh", "nadp(+)", "nadp", "nadph", "fad", "fadh2", "fmn", "fmnh2", "coa",
    "coenzyme a", "sulfate", "sulphate", "sulfite", "electron",
}
# Group-transfer / electron-carrier cofactor *families* — matched as substrings
# because MetaNetX names them with variable chain lengths ("ubiquinone-8",
# "menaquinol-7", ...). These shuttle electrons or one-carbon units between
# otherwise-unrelated reactions, so they must stay off the carbon backbone.
CURRENCY_NAME_SUBSTR = (
    "ubiquinon", "ubiquinol", "menaquinon", "menaquinol", "plastoquinon",
    "plastoquinol", "demethylmenaquino", "naphthoquino",
    "glutathion", "thioredoxin", "tetrahydrofolat", "dihydrofolat",
    "adenosyl-l-methionin", "adenosyl-l-homocystein", "adenosylmethionin",
    "acyl-carrier", "ferredoxin", "ferricytochrome", "ferrocytochrome",
)


def log(msg):
    print(msg, flush=True)


def block25(ik):
    parts = ik.split("-")
    return "-".join(parts[:2]) if len(parts) >= 2 else ik


def block14(ik):
    return ik.split("-", 1)[0] if ik else ik


def is_currency(ik, name):
    if block14(ik) in CURRENCY_IK14:
        return True
    n = (name or "").strip().lower()
    if n in CURRENCY_NAMES:
        return True
    return any(s in n for s in CURRENCY_NAME_SUBSTR)


def open_metanetx(path):
    with open(path, newline="") as f:
        for line in f:
            if line.startswith("#"):
                continue
            yield line.rstrip("\n")


# --------------------------------------------------------------------------
# 1. RetroRules templates:  MNXR -> best (score, template_id)
# --------------------------------------------------------------------------
def load_retrorules(path):
    templates = {}            # template_id -> {smarts, ecs, datasets, radius}
    mnxr_best = {}            # mnxr -> (score, template_id)
    n_rows = n_valid = 0
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = {n: i for i, n in enumerate(header)}
        for row in reader:
            n_rows += 1
            if row[idx["VALID"]].strip().lower() != "true":
                continue
            n_valid += 1
            tid = row[idx["TEMPLATE_ID"]]
            try:
                score = float(row[idx["SCORE"]])
            except ValueError:
                score = 0.0
            templates[tid] = {
                "smarts": row[idx["TEMPLATE"]],
                "ecs": [e for e in row[idx["ECS"]].split(";") if e],
                "datasets": row[idx["DATASETS"]],
                "radius": row[idx["RADIUS_MAX"]],
            }
            for mnxr in row[idx["REACTIONS"]].split(";"):
                mnxr = mnxr.strip()
                if not mnxr:
                    continue
                prev = mnxr_best.get(mnxr)
                if prev is None or score > prev[0]:
                    mnxr_best[mnxr] = (score, tid)
    log(f"  retrorules rows={n_rows:,}  valid={n_valid:,}  "
        f"distinct MNXR with template={len(mnxr_best):,}")
    return templates, mnxr_best


# --------------------------------------------------------------------------
# 2. reaction equations:  MNXR -> dict   [template MNXR only, transport dropped]
# --------------------------------------------------------------------------
def load_reactions(path, keep_mnxr):
    rxn = {}
    n_transport = n_degenerate = n_ok = 0
    for line in open_metanetx(path):
        cols = line.split("\t")
        if len(cols) < 2:
            continue
        mnxr = cols[0]
        if mnxr not in keep_mnxr:
            continue
        if len(cols) > 5 and cols[5].strip() == "T":   # is_transport
            n_transport += 1
            continue
        eq = cols[1]
        if "=" not in eq:
            continue
        lhs, rhs = eq.split(" = ", 1) if " = " in eq else eq.split("=", 1)
        subs, prods = MNXM_RE.findall(lhs), MNXM_RE.findall(rhs)
        if not subs or not prods:
            continue
        rxn[mnxr] = {
            "subs": subs,
            "prods": prods,
            "is_balanced": cols[4].strip() if len(cols) > 4 else "",
        }
        n_ok += 1
    log(f"  reactions kept={n_ok:,}  (dropped transport={n_transport:,})")
    return rxn


# --------------------------------------------------------------------------
# 3. chem_prop pass 1:  seed anchors  +  currency-metabolite MNXM set
# --------------------------------------------------------------------------
def read_seed_compounds(path):
    with open(path, newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("inchikey")]


def scan_pass1(chem_path, seeds):
    full_set = {s["inchikey"]: s for s in seeds}
    b25_set, b14_set = defaultdict(list), defaultdict(list)
    for s in seeds:
        b25_set[block25(s["inchikey"])].append(s)
        b14_set[block14(s["inchikey"])].append(s)

    candidates = defaultdict(list)
    currency_mnxm = set()
    scanned = 0
    for line in open_metanetx(chem_path):
        scanned += 1
        if scanned % 400_000 == 0:
            log(f"    pass1: scanned {scanned:,} rows")
        cols = line.split("\t")
        if len(cols) < 8:
            continue
        mnxm, name, ik = cols[0], cols[1], cols[7]
        smiles = cols[8] if len(cols) > 8 else ""
        if not ik:
            continue
        if is_currency(ik, name):
            currency_mnxm.add(mnxm)
        if ik in full_set:
            candidates[full_set[ik]["id"]].append((0, mnxm, name, smiles, ik))
        elif block25(ik) in b25_set:
            for s in b25_set[block25(ik)]:
                candidates[s["id"]].append((1, mnxm, name, smiles, ik))
        elif block14(ik) in b14_set:
            for s in b14_set[block14(ik)]:
                candidates[s["id"]].append((2, mnxm, name, smiles, ik))

    tier_name = {0: "full", 1: "connectivity+stereo (25)", 2: "connectivity (14)"}
    anchors, tier_counts, report = {}, {0: 0, 1: 0, 2: 0}, []
    for s in seeds:
        cands = candidates.get(s["id"], [])
        if not cands:
            report.append((s["name"], None, "UNMATCHED"))
            continue
        seed_b25, seed_name = block25(s["inchikey"]), s["name"].lower()

        def rank(c):
            tier, mnxm, name, smiles, ik = c
            stereo = 1 if block25(ik) == seed_b25 else 0
            return (stereo, SequenceMatcher(None, seed_name, name.lower()).ratio(), -tier)

        cands.sort(key=rank, reverse=True)
        tier, mnxm, name, smiles, ik = cands[0]
        anchors[mnxm] = s
        tier_counts[tier] += 1
        report.append((s["name"], f"{mnxm} ({name})", tier_name[tier]))

    log(f"    seeds={len(seeds)}  matched={len(anchors)}  "
        f"currency MNXM identified={len(currency_mnxm):,}")
    log(f"    tiers: full={tier_counts[0]} stereo={tier_counts[1]} conn={tier_counts[2]}")
    for nm, mx, tier in report:
        log(f"      - {nm:30s} -> {mx or '(no hit)':45s} [{tier}]")
    return anchors, currency_mnxm


# --------------------------------------------------------------------------
# 4. slice: BFS along the CARBON BACKBONE (currency mets are never traversed)
# --------------------------------------------------------------------------
def slice_graph(anchors, rxn, mnxr_best, currency, max_compounds, max_hops,
                max_rxn_per_compound, hub_threshold):
    # backbone participants per reaction (drop currency + same-on-both-sides)
    backbone = {}             # mnxr -> (bb_subs, bb_prods)
    compound_rxns = defaultdict(list)
    for mnxr, rec in rxn.items():
        ss, pp = set(rec["subs"]), set(rec["prods"])
        bb_s = {m for m in ss - pp if m not in currency}
        bb_p = {m for m in pp - ss if m not in currency}
        if not bb_s or not bb_p:
            continue              # cofactor-only / no net carbon change
        backbone[mnxr] = (bb_s, bb_p)
        for m in bb_s | bb_p:
            compound_rxns[m].append(mnxr)
    degree = {m: len(rs) for m, rs in compound_rxns.items()}
    hubs = {m for m, d in degree.items() if d > hub_threshold}
    log(f"  backbone reactions={len(backbone):,}  "
        f"high-degree carbon hubs (>{hub_threshold}, not expanded)={len(hubs):,}")

    included, compounds, frontier = set(), set(anchors), set(anchors)
    for hop in range(1, max_hops + 1):
        nxt, added = set(), 0
        for m in sorted(frontier):
            cand = sorted(set(compound_rxns.get(m, [])),
                          key=lambda r: mnxr_best[r][0], reverse=True)[:max_rxn_per_compound]
            for mnxr in cand:
                if mnxr in included or len(compounds) >= max_compounds:
                    continue
                included.add(mnxr)
                added += 1
                bb_s, bb_p = backbone[mnxr]
                for p in bb_s | bb_p:
                    if p not in compounds and len(compounds) < max_compounds:
                        compounds.add(p)
                        if p not in hubs:
                            nxt.add(p)
            if len(compounds) >= max_compounds:
                break
        log(f"  hop {hop}: +{added} reactions, compounds={len(compounds)}, next frontier={len(nxt)}")
        frontier = nxt
        if not frontier or len(compounds) >= max_compounds:
            break

    # also pull in the currency participants of the included reactions, so the
    # USES_COFACTOR layer is complete (they are NOT expansion points).
    all_compounds = set(compounds)
    for mnxr in included:
        rec = rxn[mnxr]
        for m in set(rec["subs"]) | set(rec["prods"]):
            all_compounds.add(m)
    log(f"  slice: {len(compounds)} backbone + "
        f"{len(all_compounds) - len(compounds)} cofactor compounds, {len(included)} reactions")
    return all_compounds, included, currency


# --------------------------------------------------------------------------
# 5. chem_prop pass 2: full properties for the slice
# --------------------------------------------------------------------------
def fetch_props(chem_path, needed):
    props, scanned = {}, 0
    for line in open_metanetx(chem_path):
        scanned += 1
        if scanned % 400_000 == 0:
            log(f"    pass2: scanned {scanned:,}, found {len(props)}/{len(needed)}")
        cols = line.split("\t")
        if cols and cols[0] in needed:
            props[cols[0]] = {
                "name": cols[1] if len(cols) > 1 else "",
                "formula": cols[3] if len(cols) > 3 else "",
                "charge": cols[4] if len(cols) > 4 else "",
                "mass": cols[5] if len(cols) > 5 else "",
                "inchikey": cols[7] if len(cols) > 7 else "",
                "smiles": cols[8] if len(cols) > 8 else "",
            }
            if len(props) == len(needed):
                break
    log(f"    resolved props for {len(props)}/{len(needed)} compounds")
    return props


# --------------------------------------------------------------------------
# 6. emit
# --------------------------------------------------------------------------
COMP_HDR = ["id", "name", "smiles", "inchikey", "kegg", "chebi", "role",
            "is_monomer", "is_currency", "formula", "charge", "mass"]
RXN_HDR = ["id", "name", "ec", "source", "smarts", "ec_list", "score",
           "datasets", "radius", "is_balanced"]
ENZ_HDR = ["id", "name", "ec", "gene", "organism", "uniprot"]


def sanitize_ec(ec):
    return "enz_ec_" + ec.replace(".", "_").replace("-", "x")


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})


def emit(out_dir, compounds, included, currency, anchors, props, rxn, mnxr_best, templates):
    os.makedirs(out_dir, exist_ok=True)
    cid_of, comp_rows, nodes = {}, [], []
    n_cofactor = n_dropped = 0
    for mnxm in sorted(compounds):
        if mnxm in anchors:
            s = anchors[mnxm]
            cid = s["id"]
            row = {"id": cid, "name": s["name"], "smiles": s["smiles"],
                   "inchikey": s["inchikey"], "kegg": s.get("kegg", ""),
                   "chebi": s.get("chebi", ""), "role": s.get("role", "monomer"),
                   "is_monomer": s.get("is_monomer", "false"), "is_currency": "false",
                   "formula": "", "charge": "", "mass": ""}
        else:
            p = props.get(mnxm)
            if not p or not p.get("inchikey"):
                n_dropped += 1
                continue
            cof = mnxm in currency or is_currency(p["inchikey"], p["name"])
            if cof:
                n_cofactor += 1
            cid = "cpd_" + mnxm
            row = {"id": cid, "name": p["name"], "smiles": p["smiles"],
                   "inchikey": p["inchikey"], "kegg": "", "chebi": "",
                   "role": "cofactor" if cof else "intermediate",
                   "is_monomer": "false", "is_currency": "true" if cof else "false",
                   "formula": p["formula"], "charge": p["charge"], "mass": p["mass"]}
        cid_of[mnxm] = cid
        comp_rows.append(row)
        nodes.append({"id": cid, "label": "Compound", "properties": row})

    rxn_rows, part_rows, edges, ec_seen = [], [], [], {}
    for mnxr in sorted(included):
        rec = rxn[mnxr]
        score, tid = mnxr_best[mnxr]
        tmpl = templates[tid]
        ecs = tmpl["ecs"]
        rid = "rr_" + mnxr
        rxn_rows.append({"id": rid, "name": f"RetroRules reaction {mnxr}",
                         "ec": ecs[0] if ecs else "", "source": "retrorules",
                         "smarts": tmpl["smarts"], "ec_list": ";".join(ecs),
                         "score": score, "datasets": tmpl["datasets"],
                         "radius": tmpl["radius"], "is_balanced": rec["is_balanced"]})
        nodes.append({"id": rid, "label": "Reaction", "properties": rxn_rows[-1]})
        parts = [(m, "substrate") for m in rec["subs"]] + [(m, "product") for m in rec["prods"]]
        seen_part = set()
        for m, role in parts:
            cid = cid_of.get(m)
            if not cid or (cid, role) in seen_part:
                continue
            seen_part.add((cid, role))
            part_rows.append({"compound_id": cid, "reaction_id": rid, "role": role})
            # edge type is decided at LOAD time from the compound role; here we
            # still emit the chemical role so the data round-trips.
            if role == "substrate":
                edges.append({"from": cid, "to": rid, "type": "SUBSTRATE_OF"})
            else:
                edges.append({"from": rid, "to": cid, "type": "PRODUCES"})
        for ec in ecs:
            if not EC_FULL_RE.match(ec):
                continue
            eid = sanitize_ec(ec)
            if eid not in ec_seen:
                ec_seen[eid] = {"id": eid, "name": f"EC {ec}", "ec": ec,
                                "gene": "", "organism": "", "uniprot": ""}
                nodes.append({"id": eid, "label": "Enzyme", "properties": ec_seen[eid]})
            edges.append({"from": eid, "to": rid, "type": "CATALYZES"})

    write_csv(os.path.join(out_dir, "compounds.csv"), COMP_HDR, comp_rows)
    write_csv(os.path.join(out_dir, "reactions.csv"), RXN_HDR, rxn_rows)
    write_csv(os.path.join(out_dir, "reaction_participants.csv"),
              ["compound_id", "reaction_id", "role"], part_rows)
    write_csv(os.path.join(out_dir, "enzymes.csv"), ENZ_HDR, list(ec_seen.values()))
    with open(os.path.join(out_dir, "nodes.jsonl"), "w") as f:
        for n in nodes:
            f.write(json.dumps(n) + "\n")
    with open(os.path.join(out_dir, "edges.jsonl"), "w") as f:
        for e in edges:
            f.write(json.dumps(e) + "\n")

    log("")
    log("  === emitted ===")
    log(f"  compounds.csv             : {len(comp_rows)}  "
        f"({n_cofactor} cofactor, dropped {n_dropped} structureless)")
    log(f"  reactions.csv             : {len(rxn_rows)}")
    log(f"  reaction_participants.csv : {len(part_rows)}")
    log(f"  enzymes.csv               : {len(ec_seen)}")
    log(f"  nodes.jsonl / edges.jsonl : {len(nodes)} / {len(edges)}")


# ==========================================================================
# FULL MODE — million-node graph via APOC-format LOAD JSONL
# ==========================================================================
# The connected metabolic core (~47k compounds, ~72k reactions) is embedded in
# the full ~1.5M MetaNetX compound catalogue. We ingest EVERY compound (so node
# count clears 1M) and EVERY non-transport reaction, wiring the cofactor-aware
# backbone so multi-hop traversal stays meaningful across the whole core. Output
# is a single APOC `useTypes` JSONL file loadable with `LOAD JSONL ... AS graph`.

def load_all_reactions(path):
    """ALL non-transport reactions with a parseable equation (template optional)."""
    rxn, parts = {}, set()
    n_transport = 0
    for line in open_metanetx(path):
        cols = line.split("\t")
        if len(cols) < 2:
            continue
        mnxr = cols[0]
        if len(cols) > 5 and cols[5].strip() == "T":
            n_transport += 1
            continue
        eq = cols[1]
        if "=" not in eq:
            continue
        lhs, rhs = eq.split(" = ", 1) if " = " in eq else eq.split("=", 1)
        subs, prods = MNXM_RE.findall(lhs), MNXM_RE.findall(rhs)
        if not subs or not prods:
            continue
        rxn[mnxr] = {"subs": subs, "prods": prods,
                     "is_balanced": cols[4].strip() if len(cols) > 4 else ""}
        parts.update(subs)
        parts.update(prods)
    log(f"  reactions kept={len(rxn):,} (dropped transport={n_transport:,}); "
        f"distinct participants={len(parts):,}")
    return rxn, parts


def _jprops(d):
    return {k: v for k, v in d.items() if v not in ("", None)}


def build_full(out_dir, chem_tsv, reac_tsv, rr_csv, seed_compounds, seed_dir_pg):
    os.makedirs(out_dir, exist_ok=True)
    log("[1/5] all non-transport reactions ...")
    rxn, participants = load_all_reactions(reac_tsv)
    log("[2/5] RetroRules templates (EC / SMARTS enrichment) ...")
    templates, mnxr_best = load_retrorules(rr_csv)
    log("[3/5] seed anchors + currency metabolites (chem_prop pass 1) ...")
    seeds = read_seed_compounds(seed_compounds)
    anchors, currency = scan_pass1(chem_tsv, seeds)
    seed_anchor_mnxm = {s["id"]: m for m, s in anchors.items()}

    gpath = os.path.join(out_dir, "graph.jsonl")
    nid = 0          # APOC node id counter
    rid = 0          # APOC relationship id counter
    idmap = {}       # MNXM -> node id (only for reaction participants + anchors)
    offbackbone = set()   # MNXM kept OFF the carbon backbone (cofactor OR structureless)
    log("[4/5] streaming compounds -> APOC nodes (chem_prop pass 2) ...")
    n_comp = n_cof = n_generic = 0
    with open(gpath, "w") as g:
        for line in open_metanetx(chem_tsv):
            cols = line.split("\t")
            if len(cols) < 8:
                continue
            mnxm, name, ik = cols[0], cols[1], cols[7]
            anc = anchors.get(mnxm)
            cur = (mnxm in currency) or is_currency(ik, name)
            struct = bool(ik)
            # A meaningful biosynthetic hop is between two concretely-structured
            # molecules. Currency metabolites AND structureless participants
            # (ferredoxin, ETF, "AH2", carrier proteins, generic classes) are kept
            # off the SUBSTRATE_OF/PRODUCES backbone. Anchors are always backbone.
            backbone_ok = bool(anc) or (struct and not cur)
            role = ("monomer" if anc else "cofactor" if cur
                    else "intermediate" if struct else "generic")
            core = (mnxm in participants) or bool(anc)
            # Core compounds (in a reaction) carry the full property set. The
            # ~1.2M isolated catalogue compounds keep only light identity fields
            # so the whole 1.5M-node graph fits in memory (heavy columns like
            # SMILES/formula/mass would otherwise blow past an 8GB box).
            if core:
                props = {
                    "id": "cpd_" + mnxm, "mnx_id": mnxm,
                    "name": (anc["name"] if anc else name),
                    "smiles": cols[8] if len(cols) > 8 else "",
                    "inchikey": ik,
                    "formula": cols[3] if len(cols) > 3 else "",
                    "charge": cols[4] if len(cols) > 4 else "",
                    "mass": cols[5] if len(cols) > 5 else "",
                    "kegg": (anc.get("kegg", "") if anc else ""),
                    "role": role,
                    "is_monomer": bool(anc and anc.get("is_monomer") == "true"),
                    "is_currency": cur, "has_structure": struct, "in_core": True,
                }
                idmap[mnxm] = nid
            else:
                props = {"id": "cpd_" + mnxm, "mnx_id": mnxm, "name": name,
                         "inchikey": ik, "role": role, "is_currency": cur,
                         "in_core": False}
            g.write(json.dumps({"type": "node", "id": str(nid),
                                "labels": ["Compound"], "properties": _jprops(props)}) + "\n")
            if not backbone_ok:
                offbackbone.add(mnxm)
            n_comp += 1
            n_cof += cur
            n_generic += (not struct)
            nid += 1
            if n_comp % 400_000 == 0:
                log(f"    wrote {n_comp:,} compound nodes")

        # ---- reaction nodes ----
        log("[5/5] reaction / enzyme / property nodes + relationships ...")
        rmap, ec_nodes = {}, {}
        for mnxr, rec in rxn.items():
            tmpl = templates.get(mnxr_best[mnxr][1]) if mnxr in mnxr_best else None
            ecs = tmpl["ecs"] if tmpl else []
            props = {
                "id": "rr_" + mnxr, "mnx_id": mnxr,
                "name": f"reaction {mnxr}", "source": "metanetx",
                "is_balanced": rec["is_balanced"],
                "smarts": tmpl["smarts"] if tmpl else "",
                "ec": ecs[0] if ecs else "",
                "ec_list": ";".join(ecs),
                "score": str(mnxr_best[mnxr][0]) if mnxr in mnxr_best else "",
                "datasets": tmpl["datasets"] if tmpl else "",
                "radius": tmpl["radius"] if tmpl else "",
                "has_template": mnxr in mnxr_best,
            }
            g.write(json.dumps({"type": "node", "id": str(nid),
                                "labels": ["Reaction"], "properties": _jprops(props)}) + "\n")
            rmap[mnxr] = nid
            nid += 1
            for ec in ecs:
                if EC_FULL_RE.match(ec) and ec not in ec_nodes:
                    ec_nodes[ec] = None     # placeholder, assign id below

        # ---- enzyme nodes ----
        for ec in ec_nodes:
            g.write(json.dumps({"type": "node", "id": str(nid), "labels": ["Enzyme"],
                                "properties": {"id": sanitize_ec(ec), "name": f"EC {ec}",
                                               "ec": ec}}) + "\n")
            ec_nodes[ec] = nid
            nid += 1

        # ---- property layer (seed polymers + properties) ----
        pol_rows = []
        polmap = {}
        pol_path = os.path.join(seed_dir_pg, "polymers.csv")
        if os.path.exists(pol_path):
            with open(pol_path, newline="") as f:
                pol_rows = list(csv.DictReader(f))
            for p in pol_rows:
                pp = {k: v for k, v in p.items() if k != "monomer_id"}
                g.write(json.dumps({"type": "node", "id": str(nid), "labels": ["Polymer"],
                                    "properties": _jprops(pp)}) + "\n")
                polmap[p["id"]] = nid
                nid += 1
        prop_rows, propmap = [], {}
        prop_path = os.path.join(seed_dir_pg, "properties.csv")
        if os.path.exists(prop_path):
            with open(prop_path, newline="") as f:
                prop_rows = list(csv.DictReader(f))
            for pr in prop_rows:
                g.write(json.dumps({"type": "node", "id": str(nid), "labels": ["Property"],
                                    "properties": _jprops(pr)}) + "\n")
                propmap[pr["id"]] = nid
                nid += 1

        # ---- relationships ----
        def rel(label, s_id, s_lab, e_id, e_lab):
            nonlocal rid
            g.write(json.dumps({"type": "relationship", "id": str(rid), "label": label,
                                "start": {"id": str(s_id), "labels": [s_lab]},
                                "end": {"id": str(e_id), "labels": [e_lab]},
                                "properties": {}}) + "\n")
            rid += 1

        n_back = n_cofedge = n_cat = 0
        for mnxr, rec in rxn.items():
            r_id = rmap[mnxr]
            seen = set()
            for m, role in [(x, "s") for x in rec["subs"]] + [(x, "p") for x in rec["prods"]]:
                c_id = idmap.get(m)
                if c_id is None:
                    continue
                off = (m in offbackbone)
                key = (c_id, "cof" if off else role)
                if key in seen:
                    continue
                seen.add(key)
                if off:
                    rel("USES_COFACTOR", r_id, "Reaction", c_id, "Compound"); n_cofedge += 1
                elif role == "s":
                    rel("SUBSTRATE_OF", c_id, "Compound", r_id, "Reaction"); n_back += 1
                else:
                    rel("PRODUCES", r_id, "Reaction", c_id, "Compound"); n_back += 1
            tmpl = templates.get(mnxr_best[mnxr][1]) if mnxr in mnxr_best else None
            for ec in (tmpl["ecs"] if tmpl else []):
                if ec in ec_nodes and ec_nodes[ec] is not None:
                    rel("CATALYZES", ec_nodes[ec], "Enzyme", r_id, "Reaction"); n_cat += 1

        # property-layer edges
        n_poly = n_hasprop = 0
        for p in pol_rows:
            mid = p.get("monomer_id")
            if mid and mid in seed_anchor_mnxm and seed_anchor_mnxm[mid] in idmap:
                rel("POLYMERIZES_TO", idmap[seed_anchor_mnxm[mid]], "Compound",
                    polmap[p["id"]], "Polymer"); n_poly += 1
        pp_path = os.path.join(seed_dir_pg, "polymer_properties.csv")
        if os.path.exists(pp_path):
            with open(pp_path, newline="") as f:
                for row in csv.DictReader(f):
                    if row["polymer_id"] in polmap and row["property_id"] in propmap:
                        rel("HAS_PROPERTY", polmap[row["polymer_id"]], "Polymer",
                            propmap[row["property_id"]], "Property"); n_hasprop += 1

    log("")
    log("  === FULL GRAPH emitted (APOC JSONL) ===")
    log(f"  file                 : {gpath}")
    log(f"  Compound nodes       : {n_comp:,}  ({n_cof:,} cofactor, "
        f"{n_generic:,} structureless/off-backbone)")
    log(f"  Reaction nodes       : {len(rmap):,}")
    log(f"  Enzyme nodes         : {len(ec_nodes):,}")
    log(f"  Polymer/Property     : {len(polmap)} / {len(propmap)}")
    log(f"  TOTAL NODES          : {nid:,}")
    log(f"  backbone edges       : {n_back:,}  (SUBSTRATE_OF + PRODUCES)")
    log(f"  USES_COFACTOR edges  : {n_cofedge:,}")
    log(f"  CATALYZES edges      : {n_cat:,}")
    log(f"  POLYMERIZES_TO / HAS_PROPERTY : {n_poly} / {n_hasprop}")
    log(f"  TOTAL EDGES          : {rid:,}")
    log(f"  monomer anchors wired: {sorted(seed_anchor_mnxm)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--external-dir", default=os.path.join(ROOT, "data", "external"))
    ap.add_argument("--seed-compounds",
                    default=os.path.join(ROOT, "data", "retrorules_slice", "compounds.csv"))
    ap.add_argument("--out-dir", default=None,
                    help="output dir (default: retrorules_expanded for slice, "
                         "retrorules_full for --full)")
    ap.add_argument("--full", action="store_true",
                    help="ingest the ENTIRE catalogue (~1.5M compounds, ~72k reactions) "
                         "as an APOC LOAD JSONL file — million-node scale")
    ap.add_argument("--max-compounds", type=int, default=6000)
    ap.add_argument("--max-hops", type=int, default=4)
    ap.add_argument("--max-rxn-per-compound", type=int, default=40)
    ap.add_argument("--hub-threshold", type=int, default=250,
                    help="carbon compounds in more backbone reactions than this "
                         "are not expanded through (keeps the slice from blowing up)")
    args = ap.parse_args()

    rr_csv = os.path.join(args.external_dir, "retrorules_metanetx.csv")
    reac_tsv = os.path.join(args.external_dir, "reac_prop.tsv")
    chem_tsv = os.path.join(args.external_dir, "chem_prop.tsv")
    seed_pg = os.path.join(ROOT, "data", "property_graph")
    for p in (rr_csv, reac_tsv, chem_tsv, args.seed_compounds):
        if not os.path.exists(p):
            sys.exit(f"missing input: {p}")

    if args.full:
        out_dir = args.out_dir or os.path.join(ROOT, "data", "retrorules_full")
        build_full(out_dir, chem_tsv, reac_tsv, rr_csv, args.seed_compounds, seed_pg)
        log(f"\nDone. Load with:  LOAD JSONL 'graph.jsonl' AS biomaterials_full")
        return

    out_dir = args.out_dir or os.path.join(ROOT, "data", "retrorules_expanded")
    log("[1/6] RetroRules templates ...")
    templates, mnxr_best = load_retrorules(rr_csv)
    log("[2/6] reaction equations (dropping transport) ...")
    rxn = load_reactions(reac_tsv, set(mnxr_best))
    log("[3/6] seed anchors + currency metabolites (chem_prop pass 1, ~810MB) ...")
    seeds = read_seed_compounds(args.seed_compounds)
    anchors, currency = scan_pass1(chem_tsv, seeds)
    if not anchors:
        sys.exit("no seed compounds matched MetaNetX — aborting")
    log(f"[4/6] slicing backbone (cap={args.max_compounds}, hops={args.max_hops}) ...")
    compounds, included, currency = slice_graph(
        anchors, rxn, mnxr_best, currency, args.max_compounds, args.max_hops,
        args.max_rxn_per_compound, args.hub_threshold)
    log("[5/6] compound properties (chem_prop pass 2) ...")
    props = fetch_props(chem_tsv, compounds - set(anchors))
    log("[6/6] emit ...")
    emit(args.out_dir or out_dir, compounds, included, currency, anchors, props,
         rxn, mnxr_best, templates)
    log(f"\nDone. Wrote slice to {out_dir}")


if __name__ == "__main__":
    main()
