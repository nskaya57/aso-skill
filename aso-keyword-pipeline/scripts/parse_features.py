#!/usr/bin/env python3
"""
parse_features.py — Phase 0c output reader.

Parses ASO/<AppName>/features.md into a structured JSON blob the model
(Phase 4, Phase 5) and the validator (Phase 5 compliance check) can
consume without "eyeballing" markdown. Pure stdlib.

The contract is shallow on purpose: only `## Free features`,
`## Pro features`, `## Workflow`, `## Audiences` (case-insensitive) are
recognised. Anything else is ignored. Bullets are recognised as lines
beginning with `- ` or `* `.

Usage:
    python parse_features.py --in ASO/<App>/features.md
    python parse_features.py --in ASO/<App>/features.md --check-description ASO/<App>/<locale>/fields.csv --locale <locale>
"""
import argparse
import csv
import json
import re
import sys

RECOGNISED = {
    "free features": "free",
    "pro features": "pro",
    "workflow": "workflow",
    "audiences": "audiences",
}


def parse_features_md(path):
    out = {"free": [], "pro": [], "workflow": "", "audiences": []}
    current = None
    workflow_lines = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^##\s+(.+?)\s*$", line)
            if m:
                key = m.group(1).strip().lower()
                if current == "workflow":
                    out["workflow"] = "\n".join(workflow_lines).strip()
                    workflow_lines = []
                current = RECOGNISED.get(key)
                continue
            if current in ("free", "pro", "audiences"):
                bm = re.match(r"^\s*[-*]\s+(.+?)\s*$", line)
                if bm:
                    out[current].append(bm.group(1).strip())
            elif current == "workflow":
                workflow_lines.append(line.rstrip("\n"))
    if current == "workflow":
        out["workflow"] = "\n".join(workflow_lines).strip()
    return out


def check_description_compliance(features, description):
    """Light check: every line of the description that LOOKS like a
    feature claim should map (lower-case substring) to at least one
    feature bullet from free/pro, or to an audience term. Returns list
    of suspicious lines (claims that match nothing)."""
    feature_bag = set()
    for item in features["free"] + features["pro"]:
        for tok in re.findall(r"[a-zA-ZäöüÄÖÜßçğıöşüÇĞİÖŞÜ]+", item.lower()):
            if len(tok) >= 4:
                feature_bag.add(tok)
    for a in features["audiences"]:
        for tok in re.findall(r"[a-zA-Z]+", a.lower()):
            if len(tok) >= 4:
                feature_bag.add(tok)

    suspicious = []
    for line in description.splitlines():
        line_low = line.strip().lower()
        if not line_low or not line_low.startswith(("•", "-", "*")):
            continue
        body = line_low.lstrip("•-*").strip()
        toks = [t for t in re.findall(r"[a-zA-ZäöüÄÖÜßçğıöşüÇĞİÖŞÜ]+", body) if len(t) >= 4]
        if not toks:
            continue
        if not any(t in feature_bag for t in toks):
            suspicious.append(line.strip())
    return suspicious


def main():
    p = argparse.ArgumentParser(description="Parse features.md / check description")
    p.add_argument("--in", dest="infile", required=True, help="features.md")
    p.add_argument("--check-description", help="fields.csv to spot-check against features.md")
    p.add_argument("--locale", help="locale to pick from fields.csv when --check-description")
    args = p.parse_args()

    features = parse_features_md(args.infile)

    if not args.check_description:
        print(json.dumps(features, ensure_ascii=False, indent=2))
        return

    if not args.locale:
        sys.exit("ERROR: --locale required with --check-description")

    with open(args.check_description, "r", encoding="utf-8") as f:
        row = next((r for r in csv.DictReader(f)
                    if (r.get("locale") or "").strip().lower() == args.locale.lower()), None)
    if not row:
        sys.exit(f"ERROR: no row for locale {args.locale} in {args.check_description}")

    suspicious = check_description_compliance(features, row.get("description", ""))
    print(f"=== feature compliance for {args.locale} ===")
    if not suspicious:
        print("  PASS — every bullet line touches a feature/audience token from features.md")
        return
    print(f"  WARN — {len(suspicious)} description bullet(s) reference no feature/audience token:")
    for s in suspicious:
        print(f"    ! {s}")
    print("\n  Review each: either add the matching feature to features.md "
          "or remove the claim from the description.")
    sys.exit(2)


if __name__ == "__main__":
    main()
