# aso-keyword-pipeline

A config-driven, **deterministic** App Store Optimization (ASO) skill for
Claude. It builds a complete keyword + metadata package for a mobile app —
**one language at a time** — and is reusable across apps via a single config
file.

It is designed to fix the usual failure mode of long ASO sessions: once the
context gets long (or is compacted), the process drifts and starts copying a
language it already finished. This skill makes that impossible.

## How it stays deterministic

- **Config-driven.** App id, competitors, target locales, brand terms, the
  feature list, and the scoring parameters all live in one config file
  (`assets/configs/<app>.json`), never in the conversation.
- **One locale per run, never cross-referenced.** Each locale is built only
  from its own competitor data + the config. The file layout enforces this
  physically.
- **Scores and character limits are computed by scripts, not by eye.**
  `scripts/aso_score.py` computes the competitor score, the ≥3 filter, and the
  total; `scripts/validate_fields.py` proves every character limit and
  no-duplication rule. The only human/model judgement is the `semantic`
  relevancy tier and the native-language description.
- **State lives in files.** Every phase reads its input from disk and writes
  its output to disk, so a wiped context is recoverable.

## The 6-phase pipeline

| Phase | Reference | Input → Output |
|---|---|---|
| 0. Prepare | `references/phase-0-prepare.md` | user answers → `.env` + `config.json` + `features.md` |
| 1. Collect | `references/phase-1-collect.md` | AppTweak API → `raw/*.json` |
| 2. Merge | `references/phase-2-merge.md` | `raw/*.json` → `merged.csv` |
| 3. Filter | `references/phase-3-filter.md` | `merged.csv` → `filtered.csv` |
| 4. Score | `references/phase-4-score.md` | `filtered.csv` → `scored.csv` |
| 5. Compose | `references/phase-5-compose.md` | `scored.csv` → `fields.csv` + Description |

**Phase 0** is interactive and one-time per app. It collects the three pieces
of app-specific state the conversation must never carry: the AppTweak API key
(`.env`), the app id + competitor ids + locales (`config.json`), and the
free/pro features + workflow narrative (`features.md`). The first two are
boilerplate; the third drives both the semantic rubric (Phase 4) and the
native-language description (Phase 5), so the description never invents a
feature.

## Scoring (Phase 4)

```
competitor = round( 0.5·(n/total_competitors)·10  +  0.5·avg_rank_strength·10 )   # deterministic
semantic   ∈ {10, 8, 7, 5, 4, 1}                                                  # one judgement, rubric-bound
total      = round( 0.6·semantic + 0.4·competitor , 1 )
```

`semantic` is judged only against `features.md` (Phase 0c output).
`competitor` doubles as the volume/traffic proxy (ASA popularity is floored
at 5 and carries no signal). Rank→strength buckets and the coverage/strength
weights are tunable in the config.

## Use it for a new app

1. Run **Phase 0** — the skill walks you through three sub-prompts:
   (0a) paste your AppTweak API key → saved to `.env` (gitignored);
   (0b) name the app and its competitors (App Store IDs) + target locales
   → written to `config.json`;
   (0c) list free features, pro features, the workflow, and the audiences
   → written to `features.md`.
2. Run Phases 1–5 in order, **one locale at a time**.

## Scripts

```bash
# Phase 1 — fetch competitor keywords (reads .env, runs preflight key check,
#          retries 429/5xx with backoff). Default --max 100 per competitor.
python scripts/fetch_keywords.py --config ASO/<App>/config.json \
  --locale <locale> --out-dir ASO/<App>/v<version>/<locale>/raw [--max 100] [--env .env]

# Phase 2 — merge competitor JSONs into a matrix
python scripts/aso_score.py --stage merge  --raw-dir ASO/<App>/v<version>/<locale>/raw \
  --config ASO/<App>/config.json --out ASO/<App>/v<version>/<locale>/merged.csv

# Phase 3 — filter brand / wrong-script / stop / self-indexed + ≥3 + competitor
python scripts/aso_score.py --stage filter --in ASO/<App>/v<version>/<locale>/merged.csv \
  --config ASO/<App>/config.json --locale <locale> --out ASO/<App>/v<version>/<locale>/filtered.csv

# Phase 4a — emit a semantic.json skeleton for the model to fill
python scripts/fill_semantic.py --in ASO/<App>/v<version>/<locale>/filtered.csv \
  --emit-skeleton ASO/<App>/v<version>/<locale>/semantic.json

# Phase 4b — apply the filled semantic.json to filtered.csv
python scripts/fill_semantic.py --in ASO/<App>/v<version>/<locale>/filtered.csv \
  --semantic-json ASO/<App>/v<version>/<locale>/semantic.json \
  --out ASO/<App>/v<version>/<locale>/filtered.semantic.csv

# Phase 4c — compute totals + sort
python scripts/aso_score.py --stage total --in ASO/<App>/v<version>/<locale>/filtered.semantic.csv \
  --config ASO/<App>/config.json --out ASO/<App>/v<version>/<locale>/scored.csv

# Phase 4/5 — read features.md as structured JSON
python scripts/parse_features.py --in ASO/<App>/features.md

# Phase 5 — write fields.csv + append to OUTPUT.csv (safe CSV escaping)
python scripts/write_fields.py --locale <locale> --title "..." --subtitle "..." \
  --keywords "..." --promo "..." --description-file desc.txt \
  --out ASO/<App>/v<version>/<locale>/fields.csv --output-csv ASO/<App>/v<version>/OUTPUT.csv

# Phase 5 — validate composed fields
python scripts/validate_fields.py --in ASO/<App>/v<version>/<locale>/fields.csv \
  --config ASO/<App>/config.json --locale <locale>

# Phase 5 — feature-compliance check (bullets + prose paragraphs vs features.md)
python scripts/parse_features.py --in ASO/<App>/features.md \
  --check-description ASO/<App>/v<version>/<locale>/fields.csv --locale <locale>

# Phase 0d / runtime — push or pull the app to Google Drive (rclone)
python scripts/sync.py --config ASO/<App>/config.json --to-drive
python scripts/sync.py --config ASO/<App>/config.json --from-drive

# smoke test — synthetic 3-competitor / 1-locale end-to-end (no network)
python scripts/smoke_test.py
```

Pure standard library, no dependencies. Python ≥3.7.

External tools used by the skill (install only what you need):
- `rclone` — Phase 0d / sync.py only. Install per [rclone.org/downloads](https://rclone.org/downloads/).
  Not needed if you only work on one machine.

`smoke_test.py` does not exercise Phase 1 (it needs the AppTweak API) or
sync.py (it needs an rclone remote); test those manually against a known
app/locale/remote before relying on them.

## Getting started

1. Clone or copy this folder into Claude Code's skills directory:
   - **Project-local:** `<your-app>/.claude/skills/aso-keyword-pipeline/`
   - **User-level:** `~/.claude/skills/aso-keyword-pipeline/`
2. Open the project in Claude. The skill auto-triggers on ASO requests
   ("do keywords for the German store", "add a new language to the ASO
   sheet", etc.).
3. The first action the skill takes is **Phase 0** — four interactive
   sub-prompts in this order:
   - **0a** — App name + competitors + locales → creates
     `ASO/<App>/config.json` and the app folder.
   - **0b** — AppTweak API key → `.env` at the project root.
   - **0c** — Free / pro features + workflow → `ASO/<App>/features.md`.
   - **0d** *(optional)* — Google Drive sync via rclone. Lets the same
     project open identically on another laptop / Gmail account.

## Multi-machine / multi-account flow

Drive sync (Phase 0d) is the bridge between machines:

```
Machine A                                Machine B (new laptop)
─────────                                ──────────────────────
brew install rclone                      brew install rclone
rclone config  → "gdrive"                rclone config  → "gdrive"
   (sign in with your Google account)       (sign in with the SAME account)
                                          git clone <skill repo>
sync.py --to-drive                        sync.py --from-drive
   → ASO/ uploaded                          ← ASO/ downloaded
```

The Google account is configured per-machine in `rclone config` (each
machine gets its own OAuth token, stored locally in
`~/.config/rclone/rclone.conf`). `config.rclone_remote` only stores the
remote NAME, not the account — so the same config file works for every
machine the user authorises against the same Google account. To switch
to a different Gmail, reconfigure the remote.

## Layout

```
aso-keyword-pipeline/
├── SKILL.md
├── references/        phase-0..5, drive-hierarchy
├── assets/            config.schema.md, configs/{_template.json, _template.features.md}
└── scripts/           fetch_keywords.py, aso_score.py, fill_semantic.py,
                        parse_features.py, write_fields.py, validate_fields.py,
                        sync.py, smoke_test.py
```

## License

MIT (or your preference — set before publishing).
