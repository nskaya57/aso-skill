# Drive & file hierarchy

The hierarchy is the contract. The local layout is mirrored exactly on
Google Drive by `scripts/sync.py` (Phase 0d). Both sides must look
identical so any phase can find its inputs without being told where
they are.

```
.env                                         # Phase 0b — API key (gitignored)
.gitignore                                   # must contain `.env` and `**/.env`
ASO/                                         # cfg.root_folder, default "ASO"
└── <AppName>/                               # cfg.app_name, e.g. ShiftGo/
    ├── config.json                          # Phase 0a — app + competitors + locales + version
    ├── features.md                          # Phase 0c — free/pro features + workflow + audiences
    └── v<current_version>/                  # cfg.current_version, e.g. v1.0.0/
        ├── <locale>/                        # e.g. en-US/  de-DE/  tr-TR/
        │   ├── raw/                          # Phase 1 output
        │   │   ├── <Competitor1>.json
        │   │   ├── <Competitor2>.json
        │   │   └── …
        │   ├── merged.csv                   # Phase 2 output
        │   ├── filtered.csv                 # Phase 3 output (semantic empty)
        │   ├── semantic.json                # Phase 4a — skeleton for the model to fill
        │   ├── filtered.semantic.csv        # Phase 4b — semantic applied
        │   ├── scored.csv                   # Phase 4c output (sorted by total)
        │   ├── description.txt              # Phase 5 — native-language description (input to write_fields)
        │   └── fields.csv                   # Phase 5 output (one row, this locale)
        └── OUTPUT.csv                        # consolidated per-version: one row per locale
```

## Versioning

- `cfg.current_version` is the active App Store version (e.g. `1.0.0`).
  Every Phase 1-5 artefact lands under `v<current_version>/`.
- When you ship a new version, **bump `config.current_version`** in
  Phase 0a (just edit the field) and rerun Phase 1-5. The previous
  version's files stay untouched under `v1.0.0/`; the new ones land in
  `v1.1.0/`.
- `OUTPUT.csv` is per-version (one file at `v<x>/OUTPUT.csv`), so
  comparing versions = comparing CSVs side by side.

## Rules

- **One folder per locale.** A locale's files never leak into another
  locale's folder. This physical separation is what enforces SKILL.md
  golden rule #2 ("never look at another locale"): a phase only ever
  opens paths under its own `v<x>/<locale>/`.
- **One folder per version.** Same enforcement: a Phase 5 run only
  ever opens paths under its own `v<current_version>/`.
- **Outputs are new files.** Always write a new CSV; never edit an
  existing sheet's cells in place. CSV uploaded to Google Drive
  auto-converts to a Sheet (via rclone `--drive-import-formats csv`)
  so you can review the result in the browser.
- **Sheet naming on Drive.** rclone uploads files with their local
  names, so the Sheet equivalent of `en-US/fields.csv` is a Sheet
  called `fields` inside the `en-US/` Drive folder. Don't manually
  rename Sheets in the Drive UI — sync.py won't find them on the
  next download.
- **Naming is stable.** Competitor JSON filenames and merged-matrix
  column headers use the exact competitor names from
  `config.competitors`, in config order, so every locale's matrix
  lines up column-for-column.
- **The config lives at the app root**, not inside a locale or
  version, because it spans every locale and every version.
- **`features.md` lives at the app root** too, single source of
  truth across all locales and versions of this app.

## Locale codes

Use BCP-47-style codes consistently: `en-US`, `en-GB`, `de-DE`,
`tr-TR`, `fr-FR`, … The `config.locales` entry maps each code to its
AppTweak country + device and `allowed_scripts`. The local folder name
matches the code exactly (no underscore, no lowercase-only).

## Drive sync semantics (Phase 0d + scripts/sync.py)

- `sync.py --to-drive` runs `rclone copy ASO/<App>/ <remote>:<drive_root>/<App>/`.
- `sync.py --from-drive` runs the reverse.
- `--drive-import-formats csv` and `--drive-export-formats csv` ensure
  CSVs round-trip as Google Sheets in the browser while staying
  CSV-shaped on disk.
- `sync.py --mirror` switches `copy` → `sync` (deletes destination
  extras). Use with care; needed when you delete a locale folder
  locally and want it gone on Drive too.
- `sync.py --version v1.0.0` restricts to one version subtree.
