# App config schema

The config is the only thing that changes between apps. The skill copies
the clean skeleton at `configs/_template.json` to the app's
`ASO/<AppName>/config.json` during Phase 0b and fills it interactively from
the user — never by hand-editing `_template.json`. Nothing app-specific
should live in the conversation, only in the resulting config file.

## Fields

Required unless marked **(optional)**.

| Key | Type | Meaning |
|---|---|---|
| `app_name` | string | Display name; used for the app folder and brand filtering. |
| `app_store_id` | string | Your app's Apple id (numeric, for reference / self-lookup). |
| `play_package` | string **(optional)** | Android package id; App Store is the primary target. |
| `current_version` | string | Active App Store version, e.g. `"1.0.0"`. Drives the `v<version>/` folder. Bump it when you release a new App Store build so the previous version's artefacts stay intact. |
| `root_folder` | string | Local folder root, default `"ASO"`. The app folder is `<root_folder>/<app_name>/`. |
| `drive_root` | string **(optional)** | Top-level folder name on Google Drive (Phase 0d / sync.py). Defaults to `root_folder`. The remote path is `<remote>:<drive_root>/<app_name>/v<version>/<locale>/`. |
| `rclone_remote` | string **(optional)** | The name you gave the Drive remote in `rclone config` (e.g. `gdrive`). Empty → sync.py refuses to run. Configured in Phase 0d. |
| `apptweak_key_env` | string | Env var name holding the AppTweak key (default `APPTWEAK_API_KEY`). The key itself lives in `.env`, never in this file. |
| `competitors` | array | Ordered list of `{ "name": …, "app_id": … }` (both required, `app_id` numeric). Order = matrix column order. **Minimum 3 entries** — the script aborts below this (≥3 rule). |
| `brand_terms` | array | Lower-case brand tokens to strip in Phase 3 (your brand + every competitor brand). Empty → brand filter is a no-op (the script warns). |
| `keep_terms` | array **(optional)** | **Single-token** entries preserved even if also in `stopwords` (overrides stopwords, Phase 3). Multi-word phrases (e.g. `"shift work"`) are NOT keep-matched token-by-token; if you need a phrase to survive, ensure at least one of its tokens isn't in `stopwords` to begin with. |
| `stopwords` | array | Generic auto-indexed + stop words to strip (`app`, `free`, `the`, `for`, …). |
| `locales` | object | Map of locale → `{ country, device, allowed_scripts, self_indexed }`. **Must contain at least one entry.** |
| `plural_rules` | object **(optional)** | Per-locale plural-suffix override for the Phase 5 validator. See "plural_rules" below. |
| `scoring` | object | `{ rank_strength, w_cov, w_str }` — the deterministic competitor parameters. |
| `field_limits` | object | `{ title, subtitle, keywords, keywords_min, promo, description }` char limits. |

> `features`, `audiences` and the workflow narrative live in **`features.md`**
> at the app root, not in this config — see `references/phase-0-prepare.md`
> § 0c. Phase 4 reads it for semantic judgement; Phase 5 reads it for the
> description.

## `competitors` entry

```json
"competitors": [
  { "name": "Competitor1", "app_id": "1234567890" },
  { "name": "Competitor2", "app_id": "9876543210" },
  { "name": "Competitor3", "app_id": "5555555555" }
]
```

- `name` is the column header in `merged.csv` and the JSON filename in
  `raw/`. Use a short PascalCase identifier — no spaces, no slashes.
- `app_id` is the App Store numeric id (digits only). Find it via the
  store URL `apps.apple.com/.../id<NUMBER>`.
- Order is preserved everywhere downstream; pick a stable order in
  Phase 0b and never reorder mid-project.

## `locales` entry

```json
"de-DE": {
  "country": "de",
  "device": "iphone",
  "allowed_scripts": ["latin"],
  "self_indexed": ["schichtplan", "kalender", "shiftgo"]
}
```

- `allowed_scripts` drives the Phase 3 wrong-script filter. Use `latin` for
  en/de/tr/fr/es, `cyrillic` for ru, `han` for zh, `hangul` for ko, etc.
- `self_indexed` are tokens already in this locale's current Title/Subtitle,
  removed from the keyword field in Phase 3. Leave empty `[]` for a new app
  with no live listing. **Phase 5 writes back tokens here** after composing
  the locale, so a later locale's keyword field doesn't repeat them.

## `plural_rules` block (optional, per-locale)

```json
"plural_rules": {
  "de-DE": ["e", "er", "en", "n", "s"],
  "tr-TR": ["lar", "ler"]
}
```

`validate_fields.py` uses these suffix lists to detect singular/plural
pairs in the keyword field. If a locale isn't listed here, the validator
falls back to its built-in table (English, German, Turkish, French,
Spanish, Italian, Portuguese, Dutch, Polish are pre-defined). Set the
value to `[]` to **disable** the plural-pair check for a locale.

## `scoring` block (the determinism knob)

```json
"scoring": {
  "rank_strength": [
    { "max": 5,   "value": 1.00 },
    { "max": 10,  "value": 0.80 },
    { "max": 25,  "value": 0.50 },
    { "max": 50,  "value": 0.25 },
    { "max": 100, "value": 0.10 }
  ],
  "w_cov": 0.5,
  "w_str": 0.5
}
```

Changing these changes every `competitor` score — so set them once, here, and
leave them. `w_cov` + `w_str` must equal 1. Raise `w_cov` to reward keywords
many rivals rank for; raise `w_str` to reward keywords rivals rank *highly*.

## `features.md` (not in this config)

Features, audiences and workflow narrative live in **`features.md`** at the
app root — created interactively in Phase 0c. Phase 4 reads it for the
`semantic` rubric; Phase 5 reads it for the Description.

Expected shape (see `references/phase-0-prepare.md` § 0c for the full
collection prompt):

```markdown
# AppName — Features & Workflow

## Free features
- live shift, break and earnings tracking
- automatic overtime calculation
- …

## Pro features
- cloud sync
- Apple Calendar sync (iCloud)
- …

## Workflow
[2–4 paragraphs describing how a typical user uses the app]

## Audiences
- nurses
- firefighters
- …
```

## `OUTPUT.csv` contract (Phase 5 consolidated output, per version)

Both `<locale>/fields.csv` and the version-level `OUTPUT.csv` share the
same six-column shape:

```
locale,title,subtitle,keywords,promo,description
```

- `fields.csv` (per locale, under `v<version>/<locale>/`) has **exactly
  one row**.
- `OUTPUT.csv` (per version, at `v<version>/OUTPUT.csv`) has **one row
  per locale**, appended in the order Phase 5 is run.
- Locale codes in the `locale` column must match the keys in
  `config.locales` exactly (e.g. `de-DE`, not `de`).
- **A new App Store version → new `OUTPUT.csv`.** Bump
  `config.current_version` before re-running the pipeline; previous
  version's `OUTPUT.csv` stays untouched under its own `v<x>/` folder
  for historical reference.
- `validate_fields.py` always runs against `fields.csv`. It refuses to
  run against `OUTPUT.csv` (multi-row guard).
