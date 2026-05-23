# Drive & file hierarchy

The hierarchy is the contract. Whatever moves the files (Google Drive
connector tools, or rclone/rcon locally) is up to the environment — but the
shape below must be identical everywhere, so any phase can find its inputs
without being told where they are.

```
.env                                 # Phase 0a — AppTweak API key (gitignored)
ASO/                                 # root (config.root_folder, default "ASO")
└── <AppName>/                       # e.g. ShiftGo/
    ├── config.json                  # Phase 0b — app id + competitors + locales
    ├── features.md                  # Phase 0c — free/pro features + workflow + audiences
    ├── <locale>/                    # e.g. en-US/  en-GB/  de-DE/
    │   ├── raw/                      # Phase 1 output
    │   │   ├── <Competitor1>.json
    │   │   ├── <Competitor2>.json
    │   │   └── …
    │   ├── merged.csv               # Phase 2 output
    │   ├── filtered.csv             # Phase 3 output (semantic empty)
    │   ├── filtered.semantic.csv    # Phase 4 input  (semantic filled by model)
    │   ├── scored.csv               # Phase 4 output (sorted by total)
    │   └── fields.csv               # Phase 5 output (one row, this locale)
    └── OUTPUT.csv                    # consolidated final fields, one row per locale
```

## Rules

- **One folder per locale.** A locale's files never leak into another
  locale's folder. This physical separation is what enforces golden rule #2
  ("never look at another locale"): a phase only ever opens paths under its
  own `<locale>/`.
- **Outputs are new files.** Always write a new CSV; never edit an existing
  sheet's cells in place. Some Drive bridges cannot edit cells and fail
  silently — and an in-place edit also tempts cross-locale contamination.
  CSV uploaded to Google Drive auto-converts to a Sheet.
- **Sheet/tab naming.** When these CSVs become Google Sheet tabs, name each
  tab by the locale (`en-US`, `de-DE`) or by `<locale> <stage>` — never leave
  a tab called "Sheet1", and never reuse a previous locale's tab.
- **Naming is stable.** Competitor JSON filenames and the merged-matrix column
  headers use the exact competitor names from the config, in config order, so
  every locale's matrix lines up column-for-column.
- **The config lives at the app root**, not inside a locale, because it spans
  all locales.

## Locale codes

Use BCP-47-style codes consistently: `en-US`, `en-GB`, `de-DE`, `tr-TR`,
`fr-FR`, … The config `locales` entry maps each code to its AppTweak country
+ device and its `allowed_scripts`.
