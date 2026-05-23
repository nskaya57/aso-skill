# Phase 2 — Merge into a keyword matrix

**Input:** `raw/*.json` for the locale.
**Output:** `merged.csv` for the locale.
**Decided by:** `scripts/aso_score.py --stage merge` (no judgement).

## Goal

Turn N competitor keyword lists into one table: one row per **unique**
keyword, one column per competitor, each cell that competitor's rank for the
keyword (blank if it does not rank it).

## Output format (`merged.csv`)

```
keyword,volume,<Competitor1>,<Competitor2>,<Competitor3>,<Competitor4>,<Competitor5>
shift planner,28,1,8,11,4,2
work calendar,5,4,10,1,23,5
```

- Column order for competitors must match the config `competitors` order, so
  every locale's matrix has the same column layout.
- `volume` = the maximum `volume` seen for that keyword across the competitor
  JSONs (kept for reference only).
- A blank cell means that competitor did not rank for the keyword.
- One row per unique keyword; deduplicate case-insensitively on the trimmed
  keyword string.

## How to run

```bash
python scripts/aso_score.py --stage merge \
  --raw-dir <locale>/raw \
  --config <path-to-config.json> \
  --out <locale>/merged.csv
```

The script reads every JSON in `raw/`, maps each competitor to its column by
name, unions all keywords, and writes `merged.csv`. It is fully deterministic
— do not merge by hand.

## Rules

- Do not drop, score, or filter anything here — Phase 2 is a pure union.
- Keep typo keywords at this stage; filtering happens in Phase 3.
- If two raw files map to the same competitor name, that is a config error —
  stop and report it rather than silently overwriting a column.

## Done when

`merged.csv` exists with one row per unique keyword and one rank column per
competitor in config order.
