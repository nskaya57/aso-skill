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
| `features` | object | The canonical feature list (free vs pro). The ONLY truth for `semantic` + Description. |
| `audiences` | array | Audience terms the app serves (lift related keywords toward semantic 8). |
| `scoring` | object | `{ rank_strength, w_cov, w_str }` — the deterministic competitor parameters. |
| `field_limits` | object | `{ title, subtitle, keywords, keywords_min, promo, description }` char limits. |

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

## `features` block

Group by tier; each entry is a short, concrete capability. Phase 4 judges
relevancy only against this list; Phase 5 writes the Description only from it.
Do not list a capability the app does not have.

```json
"features": {
  "free": ["live shift/break/earnings tracking", "automatic overtime", "..."],
  "pro":  ["cloud sync", "Apple/Google Calendar sync", "PDF export", "..."]
}
```
