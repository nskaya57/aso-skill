---
name: aso-keyword-pipeline
description: >-
  Build a complete, production-grade App Store Optimization (ASO) keyword and
  metadata package for a mobile app, one language at a time. Use this skill
  whenever the user wants to do ASO keyword research, analyze competitor
  keywords, build or fill an App Store / Google Play keyword field, write a
  localized app Title / Subtitle / Keywords / Promo / Description, score
  keywords by relevancy and competitor coverage, or localize store listings
  into a new language. Trigger it even when the user only says things like
  "do the keywords for the German store", "add a new language to the ASO
  sheet", "score these competitor keywords", "build the App Store metadata",
  or names competitor apps and a country. The skill is app-agnostic: it reads
  an app config (app id, competitors, target languages, feature list) and runs
  a deterministic 5-phase pipeline that fixes the usual failure mode where the
  process drifts or copies a previous language once the context gets long.
---

# ASO Keyword Pipeline

Produce a full ASO metadata package for **one app, one locale at a time**:
competitor keyword harvest → merged matrix → filtering → scoring → final
Title / Subtitle / Keywords / Promo / Description, written 100% in the
locale's native language and validated for character limits and duplication.

This skill is **config-driven and file-driven on purpose**. The single most
important property is determinism: the same inputs must always produce the
same output, no matter how long the conversation has run or whether the
context window was compacted. Read "The golden rules" before doing anything.

---

## The golden rules (read first — these prevent the known failure mode)

The classic way this pipeline breaks is: the context gets long, the scoring
rubric or the feature list falls out of context, and the model starts
*copying or calibrating against a language it already finished*. Every rule
below exists to make that impossible.

1. **One locale per run.** A single invocation processes exactly ONE locale
   (e.g. `en-US`). Never score or compose two locales in the same run. If the
   user wants three languages, that is three independent runs.

2. **Never look at another locale.** Do not open, read, copy, or
   "calibrate against" another locale's `merged`, `scored`, or `fields`
   files. Each locale is built only from its own competitor data + the app
   config. If you feel the urge to compare to a finished language to decide a
   score or a word, that urge IS the bug — stop and apply the rubric instead.

3. **State lives in files, not in chat.** Every phase reads its input from a
   file and writes its output to a file (see `references/drive-hierarchy.md`).
   If the context is wiped between phases, the next phase reconstructs
   everything from disk. Never hold pipeline state only in your head.

4. **Scores and character counts are computed by scripts, never by eye.**
   `scripts/aso_score.py` computes the competitor score, the ≥3 filter, and
   the total. `scripts/validate_fields.py` checks every character limit and
   every duplicate rule. The ONLY judgement the model makes is the `semantic`
   relevancy score (one of six fixed tiers) and the native-language prose of
   the description. Everything else is deterministic.

5. **The config is the source of truth.** App id, competitor ids, target
   locales, brand terms, the feature list, and the scoring parameters all
   live in the app's config file — not in this conversation. If a value is
   missing from the config, ask for it and add it to the config; do not
   invent it.

---

## Inputs: the app config

Before running anything, load the app config. The skill ships a clean
skeleton at `assets/configs/_template.json` — **never edit it**. Phase 0b
copies it to `ASO/<AppName>/config.json` and fills it interactively from
the user. Follow `assets/config.schema.md` for field meanings. The config
carries:

- `app_name`, `app_store_id`, `play_package` — identity.
- `competitors` — the rival app ids/names whose keywords you harvest.
- `locales` — the list of target locales (e.g. `en-US`, `en-GB`, `de-DE`).
- `brand_terms` — names to strip in filtering (your brand + every competitor
  brand) so the keyword field is never wasted on a rival's name.
- `features` — the canonical feature list. This is the **only** thing
  `semantic` relevancy is judged against, and the **only** source of truth
  for the Description. Nothing outside this list may appear as a feature.
- `scoring` — the tunable scoring parameters (rank→strength buckets and the
  coverage/strength weights). Locking these in the config is what makes the
  competitor score identical across every locale and every run.
- `field_limits` — platform character limits (App Store: title 30, subtitle
  30, keywords 100).

If the user has not provided a config, build one with them first using
`assets/config.schema.md`, save it, and only then run the pipeline.

---

## The pipeline (6 phases — 4 interactive sub-prompts + the rest scripts)

Each phase is self-contained: it states its input file, its output file,
and what to do. Run them in order. For a fresh context you can run a
single phase by reading only that phase's reference file plus the config
— that is the intended "sub-prompt" usage.

| Phase | Reference | Input → Output | Who decides |
|---|---|---|---|
| 0. Prepare | `references/phase-0-prepare.md` | user answers → `config.json` + `.env` + `features.md` + (optional) rclone remote | model (interactive, 4 sub-prompts) |
| 1. Collect | `references/phase-1-collect.md` | AppTweak API → `raw/*.json` | `scripts/fetch_keywords.py` (reads `.env`) |
| 2. Merge | `references/phase-2-merge.md` | `raw/*.json` → `merged.csv` | `aso_score.py --stage merge` |
| 3. Filter | `references/phase-3-filter.md` | `merged.csv` → `filtered.csv` | `aso_score.py --stage filter` |
| 4. Score | `references/phase-4-score.md` | `filtered.csv` → `scored.csv` (4a/4b/4c) | `fill_semantic.py` × 2 + `aso_score.py --stage total` |
| 5. Compose | `references/phase-5-compose.md` | `scored.csv` → `fields.csv` + Description | `write_fields.py` + `validate_fields.py` + `parse_features.py --check-description` |

A separate cross-cutting helper sits alongside the pipeline:

- `scripts/sync.py` — Phase 0d / runtime: push or pull the entire
  `ASO/<App>/` tree to/from a Google Drive rclone remote.

Always read the relevant phase reference file before doing that phase —
the rules and exact formats live there, deliberately out of this
overview so the overview stays short and stable.

### Phase 0 — Prepare (one-time per app)
Four interactive sub-prompts that fill the inputs every later phase
depends on:
- **0a** — App + competitors + locales → `ASO/<AppName>/config.json`.
  Creates the app folder; everything else hangs off it.
- **0b** — AppTweak API key → `.env` at project root (one shared `.env`
  even if you have multiple apps).
- **0c** — Free features, pro features, workflow narrative and audiences
  → `ASO/<AppName>/features.md`. Phase 4 reads it for semantic
  judgement, Phase 5 writes the Description only from it.
- **0d** *(optional)* — rclone Drive remote. Lets the same app open
  identically from another laptop / Gmail / OS. Skip if you only work
  on one machine.

Never paste app ids, features, or API keys into this conversation —
collect them with the user via the Phase 0 prompts
and write them to disk. See `phase-0-prepare.md`.

### Phase 1 — Collect
For each competitor in the config, fetch its best-100 ranked keywords for the
target locale from AppTweak, and save one JSON per competitor into the
locale's `raw/` folder, named by competitor. See `phase-1-collect.md` for the
exact JSON contract and the AppTweak parameters.

### Phase 2 — Merge
Union all competitor JSONs for the locale into a single keyword matrix:
`keyword, volume, <competitor columns…>`, one row per unique keyword, each
cell the app's rank (blank if it doesn't rank). Deterministic — run the
script. See `phase-2-merge.md`.

### Phase 3 — Filter
Remove brand terms (config `brand_terms`), wrong-script tokens for the locale,
and words the app's own visible metadata already indexes; then keep only
keywords ranked by **≥3** competitors. Deterministic — run the script. See
`phase-3-filter.md`.

### Phase 4 — Score
The script computes `competitor` (coverage × ranking strength) and, after you
fill `semantic`, computes `total = 0.6·semantic + 0.4·competitor`. You make
exactly one judgement per keyword: `semantic`, chosen from the six fixed tiers
against the config feature list. See `phase-4-score.md` — it contains the full
rubric. **Volume note:** ASA popularity is floored at 5 for almost all
keywords and carries no signal, so it is NOT used in the score; competitor
coverage is the de-facto traffic/volume proxy (a keyword many strong rivals
rank for is a high-traffic keyword).

### Phase 5 — Compose
From the top-`total` keywords, allocate tokens into Title (≤30), Subtitle
(≤30), and the Keyword field (≤100, target ≥90), with no token repeated
across fields and no plural/singular pair, then write the Promo and the full
Description **100% in the locale's native language**, describing only features
that exist in the config. Run `validate_fields.py` to prove the limits and the
no-duplication rules hold. See `phase-5-compose.md`.

---

## Drive / file layout

All artifacts live under a clean per-app, per-locale hierarchy described in
`references/drive-hierarchy.md`. Outputs are always written as **new** CSV
files (CSV auto-converts to a Google Sheet on upload); never edit an existing
sheet in place, because some Drive bridges cannot edit cells and will silently
fail. The mechanism (Google Drive connector tools, or rclone/rcon locally) is
environment-specific — the hierarchy is the contract, not the tool.

---

## Definition of done (for a locale)

A locale is finished only when ALL of these are true:

- `scored.csv` exists with `semantic ∈ {10,8,7,5,4,1}`, script-computed
  `competitor` and `total`, sorted by `total` descending.
- `fields.csv` exists with Title ≤30, Subtitle ≤30, Keywords ≤100 (≥90),
  and `validate_fields.py` reports zero violations and zero cross-field
  duplicates and zero plural pairs.
- The Description is 100% in the locale's native language and every feature
  it mentions appears in the config `features` list (no invented features).
- No other locale's files were read at any point during this run.
