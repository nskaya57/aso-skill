#!/usr/bin/env python3
"""
write_fields.py — Phase 5 safe CSV writer.

Composes ASO/<App>/<locale>/fields.csv from individual inputs, with
proper CSV escaping. Append-on-success to ASO/<App>/OUTPUT.csv.

The reason this exists: a model writing CSV by hand can break the file
if title/subtitle/description contain commas, quotes, or newlines. csv
module does the escaping correctly, every time.

Usage:
    python write_fields.py --locale de-DE \\
        --title "Schichtplan Kalender - ShiftGo" \\
        --subtitle "Dienstplan Stunden & Verdienst" \\
        --keywords "polizei,schicht,..." \\
        --promo "Behalte deine Schichten ..." \\
        --description-file ASO/<App>/de-DE/description.txt \\
        --out ASO/<App>/de-DE/fields.csv \\
        --output-csv ASO/<App>/OUTPUT.csv
"""
import argparse
import csv
import os
import sys

COLS = ["locale", "title", "subtitle", "keywords", "promo", "description"]


def write_fields_csv(path, row, *, overwrite=True):
    if not overwrite and os.path.exists(path):
        sys.exit(f"ERROR: {path} exists and --no-overwrite given.")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerow(row)


def append_output_csv(path, row):
    new_file = not os.path.exists(path)
    # If existing, refuse to write a duplicate locale row (Phase 5 contract:
    # OUTPUT.csv is append-only, one row per locale).
    if not new_file:
        with open(path, "r", encoding="utf-8") as f:
            existing = [r for r in csv.DictReader(f) if r.get("locale") == row["locale"]]
        if existing:
            sys.exit(f"ERROR: OUTPUT.csv already has a row for locale "
                     f"'{row['locale']}'. Open the file and remove it first "
                     f"if you intended to overwrite.")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, quoting=csv.QUOTE_MINIMAL)
        if new_file:
            w.writeheader()
        w.writerow(row)


def main():
    p = argparse.ArgumentParser(description="Phase 5: write fields.csv safely")
    p.add_argument("--locale", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--subtitle", required=True)
    p.add_argument("--keywords", required=True)
    p.add_argument("--promo", required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--description", help="inline description text")
    group.add_argument("--description-file",
                       help="path to a UTF-8 file with the description")
    p.add_argument("--out", required=True, help="fields.csv path")
    p.add_argument("--output-csv",
                   help="if set, also append to this consolidated OUTPUT.csv")
    args = p.parse_args()

    if args.description_file:
        try:
            with open(args.description_file, "r", encoding="utf-8-sig") as f:
                description = f.read()
        except FileNotFoundError:
            sys.exit(f"ERROR: description file not found: {args.description_file}")
    else:
        description = args.description

    row = {
        "locale": args.locale,
        "title": args.title,
        "subtitle": args.subtitle,
        "keywords": args.keywords,
        "promo": args.promo,
        "description": description,
    }

    write_fields_csv(args.out, row)
    print(f"wrote {args.out} (locale={args.locale}, "
          f"title={len(args.title)}c, sub={len(args.subtitle)}c, "
          f"kw={len(args.keywords)}c, promo={len(args.promo)}c, "
          f"desc={len(description)}c)")

    if args.output_csv:
        append_output_csv(args.output_csv, row)
        print(f"appended row to {args.output_csv}")


if __name__ == "__main__":
    main()
