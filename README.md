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

## The 5-phase pipeline

| Phase | Reference | Input → Output |
|---|---|---|
| 1. Collect | `references/phase-1-collect.md` | AppTweak API → `raw/*.json` |
| 2. Merge | `references/phase-2-merge.md` | `raw/*.json` → `merged.csv` |
| 3. Filter | `references/phase-3-filter.md` | `merged.csv` → `filtered.csv` |
| 4. Score | `references/phase-4-score.md` | `filtered.csv` → `scored.csv` |
| 5. Compose | `references/phase-5-compose.md` | `scored.csv` → `fields.csv` + Description |

## Scoring (Phase 4)

```
competitor = round( 0.5·(n/total_competitors)·10  +  0.5·avg_rank_strength·10 )   # deterministic
semantic   ∈ {10, 8, 7, 5, 4, 1}                                                  # one judgement, rubric-bound
total      = round( 0.6·semantic + 0.4·competitor , 1 )
```

`semantic` is judged only against the config feature list. `competitor` doubles
as the volume/traffic proxy (ASA popularity is floored at 5 and carries no
signal). Rank→strength buckets and the coverage/strength weights are tunable in
the config.

## Use it for a new app

1. Copy `assets/configs/shiftgo.json`, fill in app id, competitor ids, target
   locales, brand terms, and the feature list. See `assets/config.schema.md`.
2. Run the phases in order for one locale at a time.

## Scripts

```bash
# merge competitor JSONs into a matrix
python scripts/aso_score.py --stage merge  --raw-dir <locale>/raw --config <config> --out <locale>/merged.csv
# filter (brand / wrong-script / stop / self-indexed) + ≥3 rule + competitor
python scripts/aso_score.py --stage filter --in <locale>/merged.csv --config <config> --locale <locale> --out <locale>/filtered.csv
# after filling `semantic`, compute total and sort
python scripts/aso_score.py --stage total  --in <locale>/filtered.semantic.csv --config <config> --out <locale>/scored.csv
# validate composed fields
python scripts/validate_fields.py --in <locale>/fields.csv --config <config> --locale <locale>
```

Pure standard library, no dependencies.

## Layout

```
aso-keyword-pipeline/
├── SKILL.md
├── references/        phase-1..5, drive-hierarchy
├── assets/            config.schema.md, configs/shiftgo.json
└── scripts/           aso_score.py, validate_fields.py
```

## License

MIT (or your preference — set before publishing).
