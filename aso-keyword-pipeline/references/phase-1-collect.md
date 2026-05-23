# Phase 1 — Collect competitor keywords

**Input:** the app config (`competitors`, target `locale`, AppTweak key).
**Output:** one JSON per competitor in the locale's `raw/` folder.
**Decided by:** the AppTweak API (no judgement).

## Goal

For the single target locale, download each competitor's **best-100 ranked
keywords** and persist them, one JSON file per competitor, so later phases
read from disk and never depend on the API again.

## AppTweak request (per competitor)

For each `competitor` in the config, request its top ranked keywords for the
locale. Use the config values; do not hard-code:

- API key: `config.apptweak_key` (or the environment variable named in the
  config — never paste the key into output files).
- App id: the competitor's store id.
- Country / device: derived from the locale (e.g. `en-US` → country `us`,
  device `iphone`; `de-DE` → country `de`). The locale → (country, device)
  mapping is in the config `locales` entries.
- Limit: 100 (best-100). If the API paginates, page until you have the top
  100 by rank.

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
