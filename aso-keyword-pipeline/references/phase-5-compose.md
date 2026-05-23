# Phase 5 — Compose the metadata

**Input:** `scored.csv` (sorted by `total`).
**Output:** `fields.csv` + the full Description, validated.
**Decided by:** you (allocation + native prose), `validate_fields.py` (limits).

## Goal

Turn the ranked keywords into the final App Store listing for the locale:
Title, Subtitle, Keyword field, Promo Text, Description — written **100% in
the locale's native language** and describing **only** features in the config.

---

## How the store reads your fields (the rules that drive allocation)

- The store **combines tokens across Title + Subtitle + Keyword field** to
  form search phrases. So store **single tokens**, never whole phrases —
  "shift" in the title and "calendar" in the subtitle already gets you
  "shift calendar". Putting "shift calendar" as one keyword wastes space.
- **Never repeat a token across fields.** A token in the Title or Subtitle is
  already indexed; repeating it in the Keyword field burns characters.
- **No plural/singular pair of the same word** — the store stems those; keep
  the shorter form. (Different derivations like `scheduler` vs `scheduling`
  are NOT a plural pair; the store does not merge them, so both may stay if
  both clear the bar — otherwise keep the higher-`total` one.)
- Drop generic auto-indexed words (`app`, `free`) and stop words from the
  keyword field — they were filtered in Phase 3, keep them out here too.

## Character limits (App Store; from config `field_limits`)

| Field | Limit | Target |
|---|---|---|
| Title | 30 | use 26–30, lead with the single strongest keyword + brand |
| Subtitle | 30 | use 26–30, second strongest cluster |
| Keyword field | 100 | **≥ 90**, comma-separated, no spaces after commas |
| Promo Text | 170 | updatable without review; benefit-led |
| Description | 4000 | see prose rules below |

## Allocation procedure

1. Take the top of `scored.csv`. The highest-`total` tokens that best describe
   the app go into the **Title** (≤30) and **Subtitle** (≤30), as readable
   human phrases (these are visible to users, so they must read naturally,
   not as keyword soup).
2. Collect the remaining high-`total` tokens that bring **new** intent (not
   already in Title/Subtitle, not plural pairs of each other) into the
   **Keyword field**, comma-separated, no spaces, packing to ≥90/100 chars.
   Prefer single tokens; spend the saved characters on more distinct intents.
3. Anything strong that did not fit becomes natural language in the
   Description.

## The Description — native language, feature-exact

- Write it **entirely in the locale's native language**. Not a translation of
  the English version — native, idiomatic copy. A German listing reads as if
  written by a German speaker; a Turkish listing, by a Turkish speaker. The
  store ranks the description's words, so native phrasing also matters for ASO.
- Describe **only** features that exist in `config.features`. Never invent a
  capability. If a feature is Pro-gated, label it as such per the config.
- Structure: a one-line hook, then short benefit-led sections with bullet
  lists grouped by feature area (tracking, calendar, paint mode, templates,
  reminders, reports, Pro), then the subscription/legal lines, then an
  audience paragraph naming the locale-relevant audiences from the config.
- Weave the high-value keywords in naturally and in the native language;
  do not keyword-stuff (the store penalises unnatural repetition).
- Localize concrete details: currency word ("dollar"/"Euro"/"pound"),
  market-specific holidays (e.g. "UK bank holidays"), and audience terms
  that exist in that market.

## Output format (`fields.csv`)

One row, these columns:

```
locale,title,subtitle,keywords,promo,description
de-DE,Schichtplan Kalender - ShiftGo,Dienstplan Stunden & Verdienst,"polizei,schicht,arbeit,…","Behalte deine Schichten …","Jede Schicht, jede Pause …"
```

Append this row to the app-level `OUTPUT.csv` as well (the consolidated,
all-locales output), creating `OUTPUT.csv` if it does not exist. Append only —
never rewrite other locales' rows.

## Validate (mandatory — proves the brief's requirements)

```bash
python scripts/validate_fields.py \
  --in <locale>/fields.csv \
  --config <path-to-config.json> \
  --locale <locale>
```

It must report **PASS** on all of:
- Title ≤30, Subtitle ≤30, Keywords ≤100 and ≥90, Promo ≤170, Description ≤4000.
- No token repeated across Title / Subtitle / Keyword field.
- No singular/plural pair inside the keyword field.
- No stop words / `app` / `free` in the keyword field.
- Keyword field is comma-separated with no spaces.

Fix and re-run until it passes. A locale is not done until the validator is
green.

## Done when

`fields.csv` is written and appended to `OUTPUT.csv`, the validator passes
with zero violations, and the Description is 100% native-language and
feature-exact.
