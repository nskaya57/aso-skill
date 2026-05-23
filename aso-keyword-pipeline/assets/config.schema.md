# App config schema

The config is the only thing that changes between apps. To run the pipeline
for a new app, copy `configs/shiftgo.json`, change the values, save it as the
app's `config.json` at the app root, and run the phases. Nothing app-specific
should live in the conversation — only in this file.

## Fields

| Key | Type | Meaning |
|---|---|---|
| `app_name` | string | Display name; used for the app folder and brand filtering. |
| `app_store_id` | string | Your app's Apple id (for reference / self-lookup). |
| `play_package` | string | Android package id (optional; App Store is the primary target). |
| `root_folder` | string | Drive root, default `"ASO"`. |
| `apptweak_key_env` | string | Name of the env var holding the AppTweak key. Never store the key itself here. |
| `competitors` | array | Ordered list of `{ "name": …, "app_id": … }`. Order = matrix column order. |
| `brand_terms` | array | Lower-case brand tokens to strip in Phase 3 (your brand + every competitor brand). |
| `keep_terms` | array | Tokens to keep even if they look like brand/stop words (rare). |
| `stopwords` | array | Generic auto-indexed + stop words to strip (`app`, `free`, `the`, `for`, …). |
| `locales` | object | Map of locale → `{ country, device, allowed_scripts, self_indexed }`. |
| `scoring` | object | `{ rank_strength, w_cov, w_str }` — the deterministic competitor parameters. |
| `field_limits` | object | `{ title, subtitle, keywords, keywords_min, promo, description }` char limits. |

> `features`, `audiences` and the workflow narrative live in **`features.md`**
> at the app root, not in this config — see `references/phase-0-prepare.md`
> § 0c. Phase 4 reads it for semantic judgement; Phase 5 reads it for the
> description.

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
  with no live listing.

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
