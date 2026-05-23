# Phase 0 — Prepare (interactive setup)

**Input:** none (fresh app, or app with missing setup).
**Output:** `ASO/<AppName>/config.json`, `.env` (API key),
`ASO/<AppName>/features.md`, and optionally an rclone Drive remote.
**Decided by:** the model (one sub-prompt per artefact), confirmed by the user.

This phase exists so nothing app-specific lives in the conversation. Each
of the four sub-prompts below collects one artefact, writes it to disk,
and makes it the source of truth for every later phase.

Run **0a → 0b → 0c → 0d** in that order. The order matters: 0a creates
the `ASO/<AppName>/` folder that 0b's `.env` is anchored to and that 0c
writes into. 0d is optional (skip it if you don't want Drive sync).

---

## 0a — App + competitors → `config.json`

Walk the user through filling the app's config. Start from
`assets/configs/_template.json` and ask one question at a time, in this
order:

1. **App name** → `app_name`. Example: `ShiftGo`. This becomes the folder
   name `ASO/<AppName>/`, so prefer a clean single token.
2. **App Store ID** → `app_store_id`. Find via the App Store URL
   `apps.apple.com/.../id<NUMBER>` or
   `https://itunes.apple.com/lookup?id=<NUMBER>` to verify. Numeric only.
3. **Play package** (optional) → `play_package`. Example: `net.shiftgo.app`.
4. **Initial version** → `current_version`. Default `"1.0.0"`. Every
   downstream artefact (raw, merged, filtered, scored, fields) lives
   under `ASO/<AppName>/v<current_version>/<locale>/`. When you ship a
   new App Store version, bump this and rerun Phases 1-5 — old version
   stays intact.
5. **Competitor 1 name** + **app id**. Repeat for each competitor until
   the user has none left to add. **Minimum 3** (the ≥3 rule); recommend
   3–6 strong rivals.
6. **Brand terms to filter** → `brand_terms`. Pre-seed with the user's
   brand + every competitor brand they just named, lower-cased; ask if
   they want to add more (e.g. lookalike rivals like `homebase`,
   `deputy`).
7. **Target locales** → `locales`. Ask which App Store locales they
   want to produce (e.g. `en-US`, `en-GB`, `de-DE`, `tr-TR`). For each:
   ```json
   "en-US": { "country": "us", "device": "iphone", "allowed_scripts": ["latin"], "self_indexed": [] }
   ```
   Leave `self_indexed` empty for now — Phase 5 will populate it after
   the first locale is composed so the same tokens don't re-rank in
   sibling locales.

**Create the app folder** as part of this step:

```bash
mkdir -p ASO/<AppName>
# write the filled config here
ASO/<AppName>/config.json
```

This anchors every later artefact under `ASO/<AppName>/`.

### Rules

- Validate each app id is numeric (App Store IDs are always integers).
- If a competitor app id is unknown, do not invent one — ask the user
  to look it up.
- Never put the AppTweak API key into the config; that lives only in
  `.env` (Phase 0b).
- `features` and `audiences` are **not** in the config — they go to
  `features.md` (Phase 0c).

### Done when

A valid `config.json` exists at `ASO/<AppName>/config.json`, with
`app_store_id`, every competitor id, every target locale block, and
`current_version`.

---

## 0b — AppTweak API key → `.env`

**Read `config.apptweak_key_env`** first — it tells you which env var
name to use (default `APPTWEAK_API_KEY`). Use whatever the config says,
do not hard-code.

Ask the user once:

```
I need an AppTweak API key to fetch competitor keywords. Paste your
token here. It will be saved to .env (which is gitignored — never
committed).
```

Write the key to `.env` at the **project root** — the parent directory
of `ASO/<AppName>/`, i.e. one level above the app folder. There is one
shared `.env` per project, not one per app, because the AppTweak key
belongs to a single AppTweak account regardless of how many apps you
analyse:

```
.env
ASO/
  ShiftGo/
    config.json    # apptweak_key_env tells the script which variable to read
  OtherApp/
    config.json    # can reuse the same APPTWEAK_API_KEY from the shared .env
```

Use the variable name from the config:

```
<APPTWEAK_KEY_ENV>=xxxxxxxxxxxxxxxxxxxxxxxxx
```

### Existing-`.env` policy (idempotent, never destructive)

- If `.env` does not exist: create it with this one line.
- If `.env` exists and the variable is **not** present: append the new
  line. Leave every other line untouched.
- If `.env` exists and the variable **is** present with the same value:
  no-op. Confirm "API key already in .env".
- If `.env` exists and the variable **is** present with a different
  value: ask the user "overwrite the existing key?". On yes, replace
  just that one line; on no, abort.

### Gitignore

Ensure `.env` is gitignored. If `.gitignore` exists at the project
root, append `.env` if not already present. Otherwise create one with
`.env` and `**/.env`.

### Rules

- Never echo the full key in chat. Confirm with "API key saved to .env
  (first 6 chars: `XXXXXX…`)".
- Never commit `.env`. If it's already tracked, untrack with
  `git rm --cached .env`.
- Phase 1 (`scripts/fetch_keywords.py`) does a preflight call to verify
  the key before spending credits — a typo'd key fails fast there.

### Done when

`.env` exists at project root containing
`<config.apptweak_key_env>=…`, `.gitignore` contains `.env`, and the
key value is no longer in the chat transcript.

---

## 0c — Features + workflow → `features.md`

Ask the user three things, one block at a time, and write them into
`ASO/<AppName>/features.md`. The app folder must exist (Phase 0a
created it); never write features to `assets/configs/` (that's
templates, not runtime data).

### Block 1 — Free features

```
List every feature your app provides for FREE users. One short line per
capability — concrete, not marketing. Example:
  - live shift, break and earnings tracking
  - automatic overtime calculation (daily/weekly/monthly rules)
  - colour-coded shifts
```

Capture verbatim. Do not paraphrase, summarise, or add. If the user
lists a feature that sounds like marketing copy ("the best calendar"),
ask them to restate it as a capability.

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
open through daily use. 2-4 short paragraphs. This is the source of
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
- …

## Pro features
- …

## Workflow
[2-4 paragraphs of narrative]

## Audiences
- …
```

### How later phases use this

- **Phase 4 (semantic scoring)** reads Free + Pro to judge whether a
  keyword *is* a capability (tier 10) or adjacent. `Audiences` lifts
  to tier 8.
- **Phase 5 (description)** writes the native-language description
  from these lists + workflow. Nothing may appear in the description
  that isn't in `features.md`. `parse_features.py
  --check-description` enforces this against the produced
  `fields.csv`.

### Rules

- The user is the only source. Never invent.
- One sentence per feature; paragraphs go to Workflow.
- If a feature exists in both tiers, put it in Free with a paren note
  ("limited"); Pro is for capabilities exclusive to paying users.

### Done when

`features.md` exists at `ASO/<AppName>/features.md` with all sections
filled, every line user-confirmed.

---

## 0d — Drive sync via rclone (optional)

This step bridges `ASO/<AppName>/` to a Google Drive folder so the same
project can be opened from another laptop / Gmail / OS without manual
copying. Skip it entirely if you only work on one machine.

`rclone` is the chosen mechanism because:
- it survives OAuth token expiry on its own,
- `rclone config` works identically on macOS / Linux / Windows,
- CSVs auto-convert to Google Sheets on upload (via
  `--drive-import-formats csv`) and back to CSV on download,
- no Python deps — the skill stays stdlib-only.

### Install rclone (one-time per machine)

```bash
# macOS
brew install rclone

# Linux
curl https://rclone.org/install.sh | sudo bash

# Windows (Chocolatey)
choco install rclone
# or: download rclone.exe from rclone.org/downloads/
```

### Configure a Google Drive remote (one-time per Google account)

```bash
rclone config
```

Walk the user through:

| Prompt | Answer |
|---|---|
| `n/s/q>` | `n` (new remote) |
| `name>` | `gdrive` (or a custom name they'll remember) |
| `Storage>` | type `drive` (Google Drive) |
| `client_id>` | (Enter — use rclone's default) |
| `client_secret>` | (Enter) |
| `scope>` | `1` (full Drive — needed to convert CSV to Sheets and read existing files) |
| `service_account_file>` | (Enter — empty) |
| `Edit advanced config?` | `n` |
| `Use auto config?` | `y` → browser opens, user signs in + grants access |
| `Configure as Shared Drive?` | `n` (unless they store in a Shared Drive) |
| `Keep this remote?` | `y` |
| `n/s/q>` | `q` |

Then verify:

```bash
rclone lsd gdrive:    # lists Drive folders — should succeed
```

### Wire the remote into the config

Once the remote is configured, write its name into the app's config so
`scripts/sync.py` knows where to push:

```bash
# in ASO/<AppName>/config.json
"rclone_remote": "gdrive",
"drive_root": "ASO"
```

`drive_root` is the top-level folder on Drive; the script creates
`gdrive:<drive_root>/<AppName>/v<version>/<locale>/` mirroring the local
hierarchy.

### Test the round-trip

```bash
# Push current local state to Drive (creates the folder if missing)
python scripts/sync.py --config ASO/<AppName>/config.json --to-drive --dry-run
python scripts/sync.py --config ASO/<AppName>/config.json --to-drive
```

On Drive you'll see the same hierarchy as locally; CSVs appear as
native Google Sheets.

```bash
# On a SECOND machine: install rclone, run `rclone config` (different
# OAuth this time, but pointing to the same Google account), then
python scripts/sync.py --config ASO/<AppName>/config.json --from-drive
```

The folder + every artefact arrives intact.

### Rules

- The OAuth token from `rclone config` stays in
  `~/.config/rclone/rclone.conf` on each machine. **Never commit
  rclone.conf**. (Already gitignored implicitly because it's outside
  the repo; do not add an alias that would copy it in.)
- A user can have multiple remotes (`personal`, `work`,
  `team-shared`) — `config.rclone_remote` decides which one this app
  uses.
- The Gmail account behind the remote is configured per-machine in
  `rclone config`. Switching accounts = reconfigure the remote. The
  config doesn't store the account address.

### Done when

`rclone lsd <remote>:` lists folders successfully on every machine
where the user wants to work, and `config.rclone_remote` points to
that remote. `sync.py --to-drive --dry-run` reports zero errors.

---

## End-of-Phase-0 checklist

Before declaring Phase 0 done and proceeding to Phase 1:

- [ ] `ASO/<AppName>/config.json` exists, every competitor has a numeric
      `app_id`, every target locale has a country/device/allowed_scripts
      block, and `current_version` is set.
- [ ] `.env` exists at project root, contains
      `<config.apptweak_key_env>=…`, is gitignored.
- [ ] `ASO/<AppName>/features.md` exists with free + pro + workflow
      sections, every bullet user-confirmed.
- [ ] (optional) `config.rclone_remote` is set and
      `rclone lsd <remote>:` succeeds.
- [ ] The conversation contains none of: the API key value, an
      invented app id, an invented feature.

Only then run Phase 1.
