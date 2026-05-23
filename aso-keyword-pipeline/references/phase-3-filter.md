# Phase 3 — Filter

**Input:** `merged.csv` for the locale.
**Output:** `filtered.csv` for the locale.
**Decided by:** `scripts/aso_score.py --stage filter` (deterministic).

## Goal

Reduce the merged matrix to keywords worth scoring, by removing four classes
of noise and then applying the **≥3 competitor** rule. Doing this with a
script (not by eye) is what keeps every locale consistent.

## What gets removed, in order

1. **Brand terms.** Any keyword whose tokens are dominated by a name in
   config `brand_terms` (your own brand and every competitor brand). You never
   want to spend the keyword field ranking for a rival's name. Matching is on
   whole tokens, case-insensitive (e.g. `brand_terms: ["supershift","spoke",
   "shifter","myshiftplanner","shiftar","shiftgo"]`).

2. **Wrong-script tokens for the locale.** Each locale declares its
   `allowed_scripts` in the config (e.g. `["latin"]` for en/de/tr,
   `["cyrillic"]` for ru, `["han"]` for zh). Keywords containing characters
   outside the allowed scripts are dropped. This is what removes the Russian
   / Chinese / Korean rows from a Latin-script store. (Unicode script
   detection is deterministic; the script does it for you.)

3. **Generic auto-indexed words and stop words.** `app`, `free`, and the
   platform stop words (`the`, `a`, `for`, `with`, `my`, `and`, `of`, …) carry
   no ranking value because the store indexes them anyway. The list is in the
   config `stopwords`.

4. **Words the app already indexes.** Tokens already present in the app's own
   current Title/Subtitle for this locale (config `self_indexed[locale]`, if
   provided) are removed, so the keyword field never re-indexes something the
   visible metadata already covers. Skip this sub-step if `self_indexed` is
   empty for the locale (e.g. a brand-new app with no listing yet).

## Then apply the ≥3 rule

Keep only keywords ranked by **at least 3** of the competitors (≥3 non-blank
rank cells). Fewer than 3 is too weak a signal to score.

## How to run

```bash
python scripts/aso_score.py --stage filter \
  --in <locale>/merged.csv \
  --config <path-to-config.json> \
  --locale <locale> \
  --out <locale>/filtered.csv
```

The output `filtered.csv` has the same columns as `merged.csv` plus a
computed `competitor` column and an empty `semantic` column ready for Phase 4.

## Rules

- Removal is whole-token and case-insensitive; never substring-match (so
  "scheduler" is not removed just because "schedule" is a stopword — it
  isn't, but the principle stands).
- Do not remove a keyword just because it is a typo; a high-traffic
  misspelling can be a deliberate target. Typos are judged later via
  `semantic`.
- Keep a brand keyword only if config explicitly lists it under
  `keep_terms` (rare; e.g. you genuinely want your own brand in there).

## Done when

`filtered.csv` exists, every surviving keyword is ranked by ≥3 competitors,
brand/wrong-script/stop/self-indexed noise is gone, and the `competitor`
column is populated.
