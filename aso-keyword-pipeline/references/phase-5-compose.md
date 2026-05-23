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
- Describe **only** features that appear in `features.md` (`## Free
  features`, `## Pro features`, `## Workflow`). Never invent a capability.
  Label Pro features as such per `features.md`. If `features.md` is missing
  or thin, stop and run Phase 0c first; do not paraphrase from memory.
- Open by adapting the `## Workflow` narrative from `features.md` into 1–2
  sentences in the native language — that hook frames everything beneath.
- Structure: a one-line workflow-derived hook, then short benefit-led
  sections with bullet lists grouped by feature area (tracking, calendar,
  paint mode, templates, reminders, reports, Pro), then the subscription/
  legal lines, then an audience paragraph naming the locale-relevant
  audiences from `features.md` → `## Audiences`.
- Weave the high-value keywords (top of `scored.csv`) in naturally and in
  the native language; do not keyword-stuff (the store penalises unnatural
  repetition).
- Localize concrete details: currency word ("dollar"/"Euro"/"pound"),
  market-specific holidays (e.g. "UK bank holidays"), and audience terms
  that exist in that market.

## Output format (`fields.csv`)

`fields.csv` is **locale-specific** — exactly one row, six columns, written
to `ASO/<AppName>/v<version>/<locale>/fields.csv`:

```
locale,title,subtitle,keywords,promo,description
de-DE,Schichtplan Kalender - ShiftGo,Dienstplan Stunden & Verdienst,"polizei,schicht,arbeit,…","Behalte deine Schichten …","Jede Schicht, jede Pause …"
```

Use the writer script to avoid CSV-escape mistakes (a comma inside the
description corrupts a hand-rolled CSV silently):

```bash
python scripts/write_fields.py \
  --locale <locale> \
  --title "<title>" \
  --subtitle "<subtitle>" \
  --keywords "<comma,separated,tokens>" \
  --promo "<promo text>" \
  --description-file ASO/<AppName>/v<version>/<locale>/description.txt \
  --out ASO/<AppName>/v<version>/<locale>/fields.csv \
  --output-csv ASO/<AppName>/OUTPUT.csv
```

The script:
- writes `fields.csv` with one row, six columns, fully CSV-escaped;
- appends the same row to the app-level `OUTPUT.csv`, creating it with
  a header if missing;
- refuses to append a duplicate-locale row to `OUTPUT.csv` (catches
  re-runs that should overwrite instead of append).

The validator runs against the locale-specific `fields.csv`, not
`OUTPUT.csv`.

## Validate (mandatory — runs against `fields.csv`, not `OUTPUT.csv`)

```bash
python scripts/validate_fields.py \
  --in ASO/<AppName>/v<version>/<locale>/fields.csv \
  --config ASO/<AppName>/config.json \
  --locale <locale>
```

It must report **PASS** on all of:
- Title ≤30, Subtitle ≤30, Keywords ≤100 and ≥90, Promo ≤170, Description ≤4000.
- No token repeated across Title / Subtitle / Keyword field.
- No singular/plural pair inside the keyword field — checked with the
  locale-appropriate suffix list (English `+s/+es/+ies`, German
  `+e/+er/+en/+n/+s`, Turkish `+lar/+ler`, etc.). If the locale isn't
  in the table, falls back to English and warns. Override per-locale in
  `config.plural_rules.<locale>: ["lar","ler"]`.
- No stop words / `app` / `free` in the keyword field.
- Keyword field is comma-separated with no spaces.
- Validator refuses to run if multiple rows match the locale (catches
  the "ran against OUTPUT.csv by mistake" failure mode).

Fix and re-run until it passes. A locale is not done until the validator
is green.

## Description compliance check (recommended)

After the validator passes, run a feature-compliance spot-check against
`features.md`:

```bash
python scripts/parse_features.py \
  --in ASO/<AppName>/features.md \
  --check-description ASO/<AppName>/v<version>/<locale>/fields.csv \
  --locale <locale>
```

It flags every description bullet line that doesn't touch a feature or
audience token from `features.md`. Either add the matching feature to
`features.md` or remove the claim from the description.

## Write back `self_indexed` for the next locale

When this locale's `fields.csv` is final, the tokens in its Title +
Subtitle are now indexed by the store for the user's listing. Add them
to `config.locales[<locale>].self_indexed` so the **same** tokens don't
re-appear in the keyword field of OTHER locales when you compose them.

Tokens to write back: every word from `title` + `subtitle`, lower-cased,
minus the brand name and Apple-ignored words.

```jsonc
// before
"de-DE": { "country": "de", "device": "iphone", "allowed_scripts": ["latin"], "self_indexed": [] }

// after composing de-DE: Title "Schichtplan Kalender - ShiftGo",
// Subtitle "Dienstplan Stunden & Verdienst"
"de-DE": { ..., "self_indexed": ["schichtplan","kalender","dienstplan","stunden","verdienst"] }
```

## Done when

`fields.csv` is written and appended to `OUTPUT.csv`, the validator passes
with zero violations, and the Description is 100% native-language and
feature-exact.
