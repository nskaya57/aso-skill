#!/usr/bin/env python3
"""
fill_semantic.py — Phase 4 helper.

Copies filtered.csv → filtered.semantic.csv, applying a JSON map of
{ keyword: semantic_tier } so the semantic column is filled from a
single file the model produced. Validates that every value is one of
{10, 8, 7, 5, 4, 1} and that every keyword maps somewhere (missing
keywords get a default semantic of 1 — irrelevant — and are flagged).

Why this exists: Phase 4 was "manually edit the CSV". Hand-editing
breaks CSV escaping (a description in scored.csv with a comma can
shift columns). This script edits via the csv module, which can't.

Usage:
    # produce filtered.semantic.csv from filtered.csv + a JSON map
    python fill_semantic.py --in <locale>/filtered.csv \\
        --semantic-json <locale>/semantic.json \\
        --out <locale>/filtered.semantic.csv

    # generate a starter JSON skeleton from filtered.csv
    python fill_semantic.py --in <locale>/filtered.csv \\
        --emit-skeleton <locale>/semantic.json
"""
import argparse
import csv
import json
import sys

LEGAL = {10, 8, 7, 5, 4, 1}


def main():
    p = argparse.ArgumentParser(description="Phase 4: fill semantic column")
    p.add_argument("--in", dest="infile", required=True, help="filtered.csv")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--semantic-json",
                       help="JSON object { keyword: semantic }; tier ∈ {10,8,7,5,4,1}")
    group.add_argument("--emit-skeleton",
                       help="write a starter JSON with every keyword set to null")
    p.add_argument("--out", help="filtered.semantic.csv (required unless --emit-skeleton)")
    args = p.parse_args()

    with open(args.infile, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    if args.emit_skeleton:
        skel = {row["keyword"]: None for row in rows}
        with open(args.emit_skeleton, "w", encoding="utf-8") as f:
            json.dump(skel, f, ensure_ascii=False, indent=2)
        print(f"emitted skeleton with {len(skel)} keywords to "
              f"{args.emit_skeleton}. Fill each value with one of "
              f"{sorted(LEGAL)} and re-run with --semantic-json.")
        return

    if not args.out:
        sys.exit("ERROR: --out required when not emitting skeleton")

    with open(args.semantic_json, "r", encoding="utf-8-sig") as f:
        sem_map = json.load(f)

    errors, missing = [], []
    for row in rows:
        kw = row["keyword"]
        v = sem_map.get(kw)
        if v is None:
            missing.append(kw)
            row["semantic"] = 1
            continue
        try:
            iv = int(v)
        except (TypeError, ValueError):
            errors.append(f"{kw!r}: semantic value {v!r} is not an integer")
            continue
        if iv not in LEGAL:
            errors.append(f"{kw!r}: semantic {iv} not in {sorted(LEGAL)}")
            continue
        row["semantic"] = iv

    if errors:
        print("SEMANTIC VALIDATION FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    print(f"wrote {args.out} ({len(rows)} rows)")
    if missing:
        print(f"WARN: {len(missing)} keyword(s) missing from semantic-json — "
              f"defaulted to 1 (irrelevant). Review them:")
        for kw in missing[:20]:
            print(f"  ? {kw}")
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more")


if __name__ == "__main__":
    main()
