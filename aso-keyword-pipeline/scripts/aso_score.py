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
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        sys.exit(f"ERROR: config not found at {path}. Run Phase 0b first.")
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: config is not valid JSON ({path}): {e}")


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


def content_tokens(keyword, stopwords, keep_terms=None):
    """Strip stop words from a keyword's tokens. `keep_terms` overrides
    stopwords — a token listed in keep_terms is preserved even if it is
    also in stopwords."""
    sw = {norm(s) for s in stopwords}
    keep = {norm(s) for s in (keep_terms or [])}
    return [t for t in tokens(keyword) if t in keep or t not in sw]


def validate_config(cfg, *, need_locales=False, need_competitors=False):
    """Fail loud on common Phase 0 mistakes."""
    errs = []
    if need_competitors:
        comps = cfg.get("competitors", [])
        if len(comps) < 3:
            errs.append(f"config.competitors has {len(comps)} entries; "
                        f"pipeline needs at least 3 (≥3 rule)")
        for c in comps:
            if not c.get("app_id"):
                errs.append(f"competitor '{c.get('name')}' has empty app_id "
                            f"(Phase 0b)")
            elif not str(c["app_id"]).isdigit():
                errs.append(f"competitor '{c.get('name')}' app_id "
                            f"'{c['app_id']}' is not numeric")
    if need_locales and not cfg.get("locales"):
        errs.append("config.locales is empty (Phase 0b)")
    if errs:
        sys.exit("CONFIG VALIDATION FAILED:\n  - " + "\n  - ".join(errs))


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


def competitor_columns(fieldnames, cfg):
    """Return competitor column names in config order. Fail loud if the
    CSV's non-reserved columns don't exactly match config.competitors
    (catches stray columns that would otherwise be treated as a competitor
    and silently corrupt the score)."""
    expected = [c["name"] for c in cfg.get("competitors", [])]
    actual = [c for c in fieldnames if c not in RESERVED_COLS]
    if not expected:
        sys.exit("ERROR: config.competitors is empty (Phase 0a).")
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        extra   = sorted(set(actual)   - set(expected))
        msg = ["ERROR: CSV competitor columns don't match config.competitors:"]
        if missing: msg.append(f"  missing in CSV: {missing}")
        if extra:   msg.append(f"  unexpected in CSV: {extra}")
        msg.append(f"  expected (config order): {expected}")
        msg.append(f"  actual:                  {actual}")
        sys.exit("\n".join(msg))
    return expected


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
    validate_config(cfg, need_competitors=True)
    comp_names = [c["name"] for c in cfg["competitors"]]

    # map competitor name -> {keyword: best_rank}, and global volume
    per_comp = {name: {} for name in comp_names}
    volume = {}

    files = sorted(glob.glob(os.path.join(args.raw_dir, "*.json")))
    if not files:
        sys.exit(f"ERROR: no JSON files in {args.raw_dir}")

    name_lookup = {norm(n): n for n in comp_names}
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            sys.exit(f"ERROR: {fp} is not valid JSON: {e}")

        # Shape validation (P1-7) — guard against malformed raw input
        if not isinstance(data, dict):
            sys.exit(f"ERROR: {fp} top-level is not a JSON object")
        if "keywords" not in data or not isinstance(data["keywords"], list):
            sys.exit(f"ERROR: {fp} missing 'keywords' array")
        for i, kw in enumerate(data["keywords"]):
            if not isinstance(kw, dict):
                sys.exit(f"ERROR: {fp} keywords[{i}] is not a JSON object")
            if "keyword" not in kw or "ranking" not in kw:
                sys.exit(f"ERROR: {fp} keywords[{i}] missing 'keyword' or "
                         f"'ranking' field")

        fname = os.path.splitext(os.path.basename(fp))[0]
        cname = name_lookup.get(norm(data.get("app_name", fname))) \
            or name_lookup.get(norm(fname))
        if cname is None:
            sys.exit(f"ERROR: {fp} does not map to any config competitor "
                     f"(app_name/filename '{fname}'). Fix the config or filename.")
        if per_comp[cname]:
            sys.exit(f"ERROR: two raw files map to competitor '{cname}'.")
        for kw in data["keywords"]:
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
    validate_config(cfg, need_locales=True, need_competitors=True)
    if args.locale not in cfg["locales"]:
        sys.exit(f"ERROR: locale '{args.locale}' not in config.locales "
                 f"({sorted(cfg['locales'].keys())})")
    scoring = cfg["scoring"]
    loc = cfg["locales"][args.locale]
    allowed = loc.get("allowed_scripts", ["latin"])
    self_idx = {norm(t) for t in loc.get("self_indexed", [])}
    brand = cfg.get("brand_terms", [])
    keep = cfg.get("keep_terms", [])
    stop = cfg.get("stopwords", [])
    if not brand:
        print("WARN: config.brand_terms is empty — brand filter is a no-op. "
              "Phase 0b should at least seed it with the app name.",
              file=sys.stderr)

    with open(args.infile, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        comp_cols = competitor_columns(reader.fieldnames, cfg)
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
        ctoks = content_tokens(kw, stop, keep)
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
    # P1-6: warn when self_indexed eats more than 60% of the input — almost
    # always means the live Title/Subtitle changed since the list was last
    # refreshed (Phase 5 writes self_indexed back; if you bumped the version
    # or shipped a new listing without rerunning, it goes stale).
    if rows and dropped["self"] > 0.60 * len(rows):
        ratio = dropped["self"] / len(rows)
        print(f"  WARN: self_indexed dropped {dropped['self']} of {len(rows)} "
              f"({ratio:.0%}). Likely a stale self_indexed list — refresh it "
              f"to match the current live Title/Subtitle, then rerun "
              f"Phase 3.", file=sys.stderr)
    print("  next: fill the empty 'semantic' column with one of {10,8,7,5,4,1} "
          "per row (use scripts/fill_semantic.py), then run --stage total.")


def stage_total(args):
    cfg = load_config(args.config)
    scoring = cfg["scoring"]

    with open(args.infile, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        comp_cols = competitor_columns(reader.fieldnames, cfg)
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
