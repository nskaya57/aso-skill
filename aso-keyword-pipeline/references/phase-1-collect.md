# Phase 1 — Collect competitor keywords

**Input:** the app config (`competitors`, target `locale`, AppTweak key).
**Output:** one JSON per competitor in the locale's `raw/` folder.
**Decided by:** the AppTweak API (no judgement).

## Goal

For the single target locale, download each competitor's **best-100 ranked
keywords** and persist them, one JSON file per competitor, so later phases
read from disk and never depend on the API again.

## Run

```bash
python scripts/fetch_keywords.py \
  --config ASO/<AppName>/config.json \
  --locale <locale> \
  --out-dir ASO/<AppName>/<locale>/raw
```

The script reads `.env` (default `./.env`, override with `--env <path>`),
validates the config (≥3 competitors with numeric `app_id`, locale exists),
resolves the locale to country+device from `config.locales`, and writes one
JSON per competitor to `--out-dir`. The API key is sent only as the
`x-apptweak-key` HTTP header and never persisted to any output file.

## AppTweak endpoint reference

```
GET https://public-api.apptweak.com/api/public/store/keywords/suggestions/app.json
    ?apps=<app_id>
    &country=<cfg.locales[locale].country>      # e.g. us, gb, de, tr
    &device=<cfg.locales[locale].device>        # iphone | ipad | android
    &limit=500
    &offset=<0, 500, ...>
    &sort=score
    &sort_direction=desc

Headers:
    x-apptweak-key: <APPTWEAK_API_KEY from .env>
    Accept: application/json
```

Page until the response returns fewer than 500 keywords OR you have
collected `--max` (default 100, per the Phase 1 spec). The script handles
the loop; if you re-implement, replicate it.

The **volume** value AppTweak returns is the Apple Search Ads "Search
Popularity" index (5–100, floored at 5). Keep it in the JSON for reference,
but remember it is NOT used in scoring (see Phase 4).

## JSON contract (write exactly this shape)

Save each competitor as `raw/<CompetitorName>.json`:

```json
{
  "app_id": "645662133",
  "app_name": "MyShiftPlanner",
  "country": "us",
  "device": "iphone",
  "locale": "en-US",
  "total_keywords": 3270,
  "keywords": [
    { "keyword": "shift planner", "ranking": 1, "is_typo": false, "volume": 28, "score": 95 }
  ]
}
```

- `keyword` — lower-cased, trimmed.
- `ranking` — integer rank position (1 = best). Only keep keywords actually
  ranked within the best 100 you fetched.
- `is_typo`, `volume`, `score` — pass through from AppTweak as-is.
- `<CompetitorName>` in the filename must match the name you will use as the
  column header in Phase 2, so the matrix columns are stable.

## Rules

- Fetch for **one locale only** — the one this run is about.
- One file per competitor; do not concatenate competitors into one file.
- If a competitor returns nothing for the locale, still write its JSON with
  an empty `keywords` array so the column exists and is provably empty.
- Never write the API key into any saved file.

## Done when

`raw/` contains exactly one valid JSON per competitor in the config, each with
its `keywords` array, for this locale only.
