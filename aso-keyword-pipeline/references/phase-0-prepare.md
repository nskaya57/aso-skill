# Phase 0 — Prepare (interactive setup)

**Input:** none (fresh app, or app with missing setup).
**Output:** `.env` (API key), `config.json` (app + competitors), `features.md` (free/pro features + workflow + audiences).
**Decided by:** the model (one sub-prompt per artefact), confirmed by the user.

This phase exists so nothing app-specific lives in the conversation. Each of
the three sub-prompts below collects one artefact, writes it to disk, and
makes it the source of truth for every later phase.

Run all three before Phase 1.

---

## 0a — AppTweak API key → `.env`

Ask the user once:

```
I need an AppTweak API key to fetch competitor keywords. Paste your token here.
It will be saved to .env (which is gitignored — never committed).
```

Write the key to a `.env` file at the **app's project root** (the directory
that contains `ASO/<AppName>/`), in this exact shape:

```
APPTWEAK_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxx
```

Then ensure `.env` is gitignored. If a `.gitignore` exists at the project
root, append `.env` if not already present; otherwise create one with `.env`
and `**/.env` in it.

The config's `apptweak_key_env` field tells the script which environment
variable to read (default `APPTWEAK_API_KEY`). Phase 1 loads it from `.env`;
it is never written into any JSON/CSV output.

### Rules

- Never echo the full key back in chat after writing it. Confirm with
  "API key saved to .env (first 6 chars: `XXXXXX…`)" only.
- Never commit `.env`. If it's already tracked, untrack it with
  `git rm --cached .env`.
- If the user refuses to share a key, ask whether they want to provide it
  later via shell (`export APPTWEAK_API_KEY=...`); do not invent a fallback.

### Done when

`.env` exists at project root with `APPTWEAK_API_KEY=…`, `.gitignore`
contains `.env`, and the key is no longer in the chat transcript.

---

## 0b — App + competitors → `config.json`

Walk the user through filling the app's config. Start from
`assets/configs/_template.json` (or the existing app config if one exists)
and ask one question at a time, in this order:

1. **App name** → `app_name`. Example: `ShiftGo`.
2. **App Store ID** → `app_store_id`. Find via the App Store URL
   `apps.apple.com/.../id<NUMBER>` or
   `https://itunes.apple.com/lookup?id=<NUMBER>` to verify. Example: `6764889422`.
3. **Play package** (optional) → `play_package`. Example: `net.shiftgo.app`.
4. **Competitor 1 name** + **app id**. Repeat for each competitor until the
   user has none left to add. Recommend 3–6 strong rivals; never less than 3
   (the ≥3 rule needs them).
5. **Brand terms to filter** → `brand_terms`. Pre-seed with the user's brand
   + every competitor brand they just named, lower-cased; ask if they want
   to add more (e.g. lookalike rivals like `homebase`, `deputy`).
6. **Target locales** → `locales`. Ask which App Store locales they want to
   produce (e.g. `en-US`, `en-GB`, `de-DE`, `tr-TR`). For each, fill the
   block from the schema:
   ```json
   "en-US": { "country": "us", "device": "iphone", "allowed_scripts": ["latin"], "self_indexed": [] }
   ```
   Leave `self_indexed` empty for now — Phase 5 will populate it after the
   first locale is composed (so subsequent locales don't re-rank tokens
   already in Title/Subtitle).

Write the result to `assets/configs/<app_name_slug>.json` (slug =
lower-case, hyphenated). Confirm by reading back a one-line summary:
`Wrote config: app=<name>, 5 competitors, 4 locales, 12 brand_terms.`

### Rules

- Validate each app id is numeric (App Store IDs are always integers).
- If a competitor app id is unknown, do not invent one — ask the user to
  look it up. The pipeline fails loud later if an id is missing.
- Never put the AppTweak API key into the config; that lives only in `.env`.
- `features` and `audiences` are **not** in the config — they go to
  `features.md` (Phase 0c) so the description has room to breathe.

### Done when

A valid `config.json` exists, with `app_store_id`, every competitor id, and
every target locale block filled.

---

## 0c — Features + workflow → `features.md`

Ask the user three things, one block at a time, and write them into
`ASO/<AppName>/features.md`. Phase 0b must have created the app folder
(`ASO/<AppName>/`) already; if it hasn't, run Phase 0b first — never
write features to `assets/configs/` (that's where templates live, not
runtime data).

### Block 1 — Free features

```
List every feature your app provides for FREE users. One short line per
capability — concrete, not marketing. Example:
  - live shift, break and earnings tracking
  - automatic overtime calculation (daily/weekly/monthly rules)
  - colour-coded shifts
```

Capture verbatim. Do not paraphrase, summarise, or add. If the user lists a
feature that sounds like marketing copy ("the best calendar"), ask them to
restate it as a capability.

### Block 2 — Pro features

```
Same drill for PRO / subscription features. One short line each.
Example:
  - cloud sync (back up and restore on any device)
  - Apple Calendar sync (iCloud)
  - PDF export of reports and calendar
```

### Block 3 — Workflow

```
Describe in your own words how a typical user uses the app, from first
open through daily use. 2–4 short paragraphs. This is the source of
truth for the App Store Description — every claim in the description
will be checked against this and the feature lists above.
```

Free-form narrative. Capture verbatim, then read back to the user to
confirm.

### Block 4 (optional) — Audiences

Ask: "Which specific worker groups does this app serve? (e.g. nurses,
firefighters, hospitality)". Capture as a bullet list.

### `features.md` shape (write exactly this layout)

```markdown
# <AppName> — Features & Workflow

## Free features
- live shift, break and earnings tracking
- automatic overtime calculation
- …

## Pro features
- cloud sync
- …

## Workflow
[2–4 paragraphs of narrative]

## Audiences
- nurses
- firefighters
- …
```

### How later phases use this

- **Phase 4 (semantic scoring)** reads `Free features` + `Pro features` to
  judge whether a keyword *is* one of the app's capabilities (tier 10) or
  merely adjacent. `Audiences` lifts a keyword to tier 8 if the keyword
  names one of those audiences.
- **Phase 5 (description)** writes the native-language description from
  these lists + the workflow narrative. Nothing may appear in the
  description that isn't in `features.md`.

### Rules

- The user is the only source. Never invent a feature, even if every
  competitor has it. If the app lacks it, it stays out.
- One sentence per feature. If the user writes a paragraph, ask them to
  reduce it to one line + put the paragraph into Workflow.
- If a feature exists in both tiers ("multi-currency: free, but limited to 1
  currency for free"), put it in **Free** with a parenthetical note. Pro is
  for capabilities exclusive to paying users.

### Done when

`features.md` exists with all three (or four) sections filled, every line
written by the user (or paraphrased only with their confirmation), and the
user has confirmed the workflow paragraph reads true.

---

## End-of-Phase-0 checklist

Before declaring Phase 0 done and proceeding to Phase 1:

- [ ] `.env` exists at project root, contains `APPTWEAK_API_KEY=…`, is
      gitignored.
- [ ] `config.json` exists, every competitor has a numeric app id, every
      target locale has a country/device/allowed_scripts block.
- [ ] `features.md` exists with free + pro + workflow sections, every
      bullet user-confirmed.
- [ ] The conversation contains none of: the API key value, an invented
      app id, an invented feature.

Only then run Phase 1.
