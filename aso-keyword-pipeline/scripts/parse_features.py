#!/usr/bin/env python3
"""
parse_features.py — Phase 0c output reader.

Parses ASO/<AppName>/features.md into a structured JSON blob the model
(Phase 4, Phase 5) and the validator (Phase 5 compliance check) can
consume without "eyeballing" markdown. Pure stdlib.

The contract is shallow on purpose: only `## Free features`,
`## Pro features`, `## Workflow`, `## Audiences` (case-insensitive) are
recognised. Anything else is ignored. Bullets are recognised as lines
beginning with `-` or `*`.

Usage:
    python parse_features.py --in ASO/<App>/features.md
    python parse_features.py --in ASO/<App>/features.md \\
        --check-description ASO/<App>/<locale>/fields.csv --locale <locale>
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

# Latin + German + Turkish + Cyrillic + CJK + Hangul
WORD_RE = re.compile(r"[a-zäöüßçğıöşüа-яё぀-ヿ一-鿿가-힯]+", re.IGNORECASE)
MIN_TOKEN_LEN = 4
# Compliance: a description paragraph PASSES if at least this many of its
# meaningful tokens map to the feature bag. Tuned so that natural-language
# prose with one or two scene-setting words (e.g. "track every shift,
# every break, every dollar") still passes when "shift" + "break" are in
# features.md, but a fully fabricated claim ("step counter, heart rate")
# fails.
PROSE_MATCH_RATIO = 0.30  # at least 30% of tokens must touch the bag


def parse_features_md(path):
    try:
        f = open(path, "r", encoding="utf-8-sig")
    except FileNotFoundError:
        sys.exit(f"ERROR: features.md not found at {path}. "
                 f"Run Phase 0c first (see references/phase-0-prepare.md).")
    out = {"free": [], "pro": [], "workflow": "", "audiences": []}
    current = None
    workflow_lines = []
    with f:
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


def build_feature_bag(features):
    """All ≥4-char tokens from free + pro + audiences + workflow."""
    bag = set()
    sources = features["free"] + features["pro"] + features["audiences"]
    sources.append(features["workflow"])
    for item in sources:
        for tok in WORD_RE.findall(item.lower()):
            if len(tok) >= MIN_TOKEN_LEN:
                bag.add(tok)
    return bag


def _meaningful_tokens(text):
    return [t for t in WORD_RE.findall(text.lower()) if len(t) >= MIN_TOKEN_LEN]


def check_description_compliance(features, description):
    """Two-tier check:
      • BULLET lines (•/-/*): every bullet must touch ≥1 feature/audience
        token. A bullet that touches none is flagged (strict).
      • PROSE lines (hook + audience paragraphs): each paragraph must
        have ≥PROSE_MATCH_RATIO of its meaningful tokens in the feature
        bag. Lower ratios are flagged (catches fabricated narratives).

    Returns (bullet_misses, prose_misses) where each is a list of
    (line_or_paragraph, reason).
    """
    bag = build_feature_bag(features)
    bullet_misses = []
    prose_misses  = []
    paragraph     = []

    def flush_prose():
        nonlocal paragraph
        if not paragraph:
            return
        joined = " ".join(paragraph)
        toks = _meaningful_tokens(joined)
        if toks:
            hits = sum(1 for t in toks if t in bag)
            ratio = hits / len(toks)
            if ratio < PROSE_MATCH_RATIO:
                prose_misses.append(
                    (joined[:140],
                     f"{hits}/{len(toks)} tokens match features.md "
                     f"({ratio:.0%} < {PROSE_MATCH_RATIO:.0%})"))
        paragraph = []

    for raw in description.splitlines():
        line = raw.strip()
        if not line:
            flush_prose()
            continue
        if line.startswith(("•", "-", "*")):
            flush_prose()
            body = line.lstrip("•-*").strip().lower()
            toks = _meaningful_tokens(body)
            if toks and not any(t in bag for t in toks):
                bullet_misses.append((line, "no token matches features.md"))
            continue
        # treat ALL-CAPS heading lines as section breaks, not prose
        stripped = re.sub(r"[^a-zA-ZäöüÄÖÜß]", "", line)
        if stripped and stripped.isupper() and len(stripped) >= 3:
            flush_prose()
            continue
        paragraph.append(line)
    flush_prose()
    return bullet_misses, prose_misses


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

    try:
        f = open(args.check_description, "r", encoding="utf-8-sig")
    except FileNotFoundError:
        sys.exit(f"ERROR: {args.check_description} not found. "
                 f"Run Phase 5 (compose) first.")
    with f:
        row = next((r for r in csv.DictReader(f)
                    if (r.get("locale") or "").strip().lower() == args.locale.lower()), None)
    if not row:
        sys.exit(f"ERROR: no row for locale {args.locale} in {args.check_description}")

    bullets, prose = check_description_compliance(features, row.get("description", ""))
    print(f"=== feature compliance for {args.locale} ===")
    if not bullets and not prose:
        print("  PASS — every bullet AND every prose paragraph touches "
              "features.md")
        return
    if bullets:
        print(f"\n  BULLET WARN — {len(bullets)} bullet(s) reference no "
              f"feature/audience token:")
        for line, reason in bullets:
            print(f"    ! {line}")
    if prose:
        print(f"\n  PROSE WARN — {len(prose)} paragraph(s) below "
              f"{PROSE_MATCH_RATIO:.0%} feature density:")
        for joined, reason in prose:
            print(f"    ! {reason}")
            print(f"      → {joined!r}")
    print("\n  Review each: either add the matching feature to features.md "
          "or remove the claim from the description.")
    sys.exit(2)


if __name__ == "__main__":
    main()
