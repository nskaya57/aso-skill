#!/usr/bin/env python3
"""
aso_score.py — deterministic engine for the ASO keyword pipeline.

Stages:
  merge   raw/*.json            -> merged.csv   (keyword x competitor matrix)
  filter  merged.csv            -> filtered.csv (brand/script/stop/self + >=3, competitor computed)
  total   filtered.semantic.csv -> scored.csv   (validate semantic, recompute competitor, total, sort)

Only `semantic` is set by a human/model. competitor and total are computed
here so they never drift, no matter how long the context has run.

Pure standard library. No network.
"""
import argparse
import csv
import glob
import json
import os
import sys
import unicodedata

LEGAL_SEMANTIC = {10, 8, 7, 5, 4, 1}
RESERVED_COLS = {"keyword", "volume", "competitor", "semantic", "total"}


# ----------------------------- helpers -------------------------------------

def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def norm(s):
    return (s or "").strip().lower()


def tokens(keyword):
    return [t for t in norm(keyword).replace(",", " ").split() if t]


def script_of(ch):
    """Return a coarse script name for an alphabetic char, else None."""
    if not ch.isalpha():
        return None
    name = unicodedata.name(ch, "")
    if "LATIN" in name:
        return "latin"
    if "CYRILLIC" in name:
        return "cyrillic"
    if "CJK" in name or "IDEOGRAPH" in name:
        return "han"
    if "HANGUL" in name:
        return "hangul"
    if "ARABIC" in name:
        return "arabic"
    if "HIRAGANA" in name or "KATAKANA" in name:
        return "kana"
    if "GREEK" in name:
        return "greek"
    if "HEBREW" in name:
        return "hebrew"
    if "THAI" in name:
        return "thai"
    if "DEVANAGARI" in name:
        return "devanagari"
    return "other"


def script_ok(keyword, allowed):
    allowed = set(allowed or [])
    for ch in keyword:
        s = script_of(ch)
        if s is not None and s not in allowed:
            return False
    return True


def is_brand(keyword, brand_terms, keep_terms):
    kw = norm(keyword)
    if kw in {norm(k) for k in keep_terms}:
        return False
    toks = set(tokens(kw))
    for bt in brand_terms:
        b = norm(bt)
        if " " in b:
            if b in kw:
                return True
        else:
            if b in toks:
                return True
    return False


def content_tokens(keyword, stopwords):
    sw = {norm(s) for s in stopwords}
    return [t for t in tokens(keyword) if t not in sw]


def strength_for_rank(rank, buckets):
    for b in buckets:
        if rank <= b["max"]:
            return b["value"]
    return 0.0


def parse_rank(cell):
    cell = (cell or "").strip()
    if cell == "":
        return None
    try:
        r = int(float(cell))
        return r if r > 0 else None
    except ValueError:
        return None


def competitor_columns(fieldnames):
    return [c for c in fieldnames if c not in RESERVED_COLS]


def compute_competitor(rank_cells, scoring, n_competitors):
    """rank_cells: list of raw cell strings for the competitor columns."""
    ranks = [r for r in (parse_rank(c) for c in rank_cells) if r is not None]
    n = len(ranks)
    if n == 0:
        return 0, 0
    strengths = [strength_for_rank(r, scoring["rank_strength"]) for r in ranks]
    avg_strength = sum(strengths) / n
    coverage_part = (n / n_competitors) * 10.0
    strength_part = avg_strength * 10.0
    score = scoring["w_cov"] * coverage_part + scoring["w_str"] * strength_part
    score = int(round(score))
    score = max(1, min(10, score))
    return score, n


# ------------------------------ stages -------------------------------------

def stage_merge(args):
    cfg = load_config(args.config)
    comp_names = [c["name"] for c in cfg["competitors"]]

    # map competitor name -> {keyword: best_rank}, and global volume
    per_comp = {name: {} for name in comp_names}
    volume = {}

    files = sorted(glob.glob(os.path.join(args.raw_dir, "*.json")))
    if not files:
        sys.exit(f"ERROR: no JSON files in {args.raw_dir}")

    name_lookup = {norm(n): n for n in comp_names}
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        fname = os.path.splitext(os.path.basename(fp))[0]
        cname = name_lookup.get(norm(data.get("app_name", fname))) \
            or name_lookup.get(norm(fname))
        if cname is None:
            sys.exit(f"ERROR: {fp} does not map to any config competitor "
                     f"(app_name/filename '{fname}'). Fix the config or filename.")
        if per_comp[cname]:
            sys.exit(f"ERROR: two raw files map to competitor '{cname}'.")
        for kw in data.get("keywords", []):
            k = norm(kw.get("keyword"))
            if not k:
                continue
            r = parse_rank(str(kw.get("ranking", "")))
            if r is None:
                continue
            prev = per_comp[cname].get(k)
            per_comp[cname][k] = r if prev is None else min(prev, r)
            v = kw.get("volume")
            try:
                v = int(v)
            except (TypeError, ValueError):
                v = None
            if v is not None:
                volume[k] = max(volume.get(k, 0), v)

    all_keywords = sorted({k for d in per_comp.values() for k in d})
    out_fields = ["keyword", "volume"] + comp_names
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        for k in all_keywords:
            row = {"keyword": k, "volume": volume.get(k, 5)}
            for name in comp_names:
                r = per_comp[name].get(k)
                row[name] = "" if r is None else r
            w.writerow(row)
    print(f"merge: {len(all_keywords)} unique keywords, "
          f"{len(comp_names)} competitor columns -> {args.out}")


def stage_filter(args):
    cfg = load_config(args.config)
    scoring = cfg["scoring"]
    loc = cfg["locales"][args.locale]
    allowed = loc.get("allowed_scripts", ["latin"])
    self_idx = {norm(t) for t in loc.get("self_indexed", [])}
    brand = cfg.get("brand_terms", [])
    keep = cfg.get("keep_terms", [])
    stop = cfg.get("stopwords", [])

    with open(args.infile, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        comp_cols = competitor_columns(reader.fieldnames)
    n_comp = len(comp_cols)

    kept = []
    dropped = {"brand": 0, "script": 0, "generic": 0, "self": 0, "lt3": 0}
    for row in rows:
        kw = row["keyword"]
        if is_brand(kw, brand, keep):
            dropped["brand"] += 1
            continue
        if not script_ok(kw, allowed):
            dropped["script"] += 1
            continue
        ctoks = content_tokens(kw, stop)
        if not ctoks:
            dropped["generic"] += 1
            continue
        if self_idx and all(t in self_idx for t in ctoks):
            dropped["self"] += 1
            continue
        comp_score, n_rank = compute_competitor(
            [row.get(c, "") for c in comp_cols], scoring, n_comp)
        if n_rank < 3:
            dropped["lt3"] += 1
            continue
        row["competitor"] = comp_score
        row["semantic"] = ""
        kept.append(row)

    out_fields = ["keyword", "volume"] + comp_cols + ["competitor", "semantic"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        for row in kept:
            w.writerow({k: row.get(k, "") for k in out_fields})
    print(f"filter: kept {len(kept)} / {len(rows)}  dropped={dropped}  -> {args.out}")
    print("  next: fill the empty 'semantic' column with one of {10,8,7,5,4,1} "
          "per row (Phase 4 rubric), save as *.semantic.csv, then run --stage total.")


def stage_total(args):
    cfg = load_config(args.config)
    scoring = cfg["scoring"]

    with open(args.infile, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        comp_cols = competitor_columns(reader.fieldnames)
    n_comp = len(comp_cols)

    errors = []
    for i, row in enumerate(rows, start=2):  # +1 header, +1 1-indexed
        sem_raw = (row.get("semantic", "") or "").strip()
        try:
            sem = int(float(sem_raw))
        except ValueError:
            errors.append(f"  line {i} '{row['keyword']}': semantic '{sem_raw}' is not a number")
            continue
        if sem not in LEGAL_SEMANTIC:
            errors.append(f"  line {i} '{row['keyword']}': semantic {sem} not in {sorted(LEGAL_SEMANTIC)}")
            continue
        comp_score, _ = compute_competitor(
            [row.get(c, "") for c in comp_cols], scoring, n_comp)
        row["semantic"] = sem
        row["competitor"] = comp_score
        row["total"] = round(0.6 * sem + 0.4 * comp_score, 1)

    if errors:
        print("SEMANTIC VALIDATION FAILED — fix these and re-run:", file=sys.stderr)
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)

    def vol(row):
        try:
            return int(row.get("volume") or 0)
        except ValueError:
            return 0

    rows.sort(key=lambda r: (-r["total"], -vol(r), r["keyword"]))

    out_fields = ["keyword", "volume"] + comp_cols + ["competitor", "semantic", "total"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in out_fields})
    top = rows[0] if rows else None
    print(f"total: scored {len(rows)} keywords -> {args.out}")
    if top:
        print(f"  top keyword: '{top['keyword']}' "
              f"(sem {top['semantic']}, comp {top['competitor']}, total {top['total']})")


# ------------------------------- cli ---------------------------------------

def main():
    p = argparse.ArgumentParser(description="Deterministic ASO scoring engine")
    p.add_argument("--stage", required=True, choices=["merge", "filter", "total"])
    p.add_argument("--config", required=True)
    p.add_argument("--raw-dir", help="merge: folder of competitor JSONs")
    p.add_argument("--in", dest="infile", help="filter/total: input CSV")
    p.add_argument("--locale", help="filter: locale key, e.g. en-US")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    if args.stage == "merge":
        if not args.raw_dir:
            p.error("--raw-dir is required for --stage merge")
        stage_merge(args)
    elif args.stage == "filter":
        if not args.infile or not args.locale:
            p.error("--in and --locale are required for --stage filter")
        stage_filter(args)
    elif args.stage == "total":
        if not args.infile:
            p.error("--in is required for --stage total")
        stage_total(args)


if __name__ == "__main__":
    main()
