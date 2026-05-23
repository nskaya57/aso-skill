# Phase 4 — Score

**Input:** `filtered.csv` (has `competitor` filled, `semantic` empty).
**Output:** `scored.csv` (semantic + total filled, sorted by total).
**Decided by:** the script for `competitor`/`total`; you for `semantic` only.

This phase produces three numbers per keyword. Two are deterministic
(computed by the script); one is your judgement against the feature list.
Keeping it split this way is what makes scoring reproducible across runs.

> **Reminder:** judge each keyword in isolation, using ONLY this rubric and
> the config feature list. Never look at another locale's scores to decide.

---

## 4.1 `semantic` (0–10) — relevancy to the app (YOUR ONE JUDGEMENT)

`semantic` answers one question: **how directly does this keyword describe
what the app actually does?** Judge it only against `config.features`. Assign
exactly one of six tiers — no in-between values:

| Score | Meaning | Pattern (ShiftGo examples) |
|---|---|---|
| **10** | Core. The keyword *is* a name for the app's primary function. | `work shift calendar`, `shift scheduler`, `shift work schedule`, `shift tracker` |
| **8** | Strong adjacent. Same job, narrower angle, or an audience the config explicitly serves. | `duty calendar`, `nurse calendar`, `nurse schedule`, `roster`, `rotating schedule` |
| **7** | Related but generic/partial. Right domain, weak or fragmentary modifier. | `my shift`, `shift manager`, `planning shift`, `shift organizer` |
| **5** | Loose. One foot in the domain, one out. | `work`, `my duty`, `agenda work` |
| **4** | Weak / tangential / typo / wrong intent. | `shift events`, `shift games`, `shift work fatigue`, `shitty` |
| **1** | Irrelevant. Ranked by rivals but unrelated to the app. | `nte tasks`, `calinder for kids`, `auto add events` |

Discipline rules:

- Only `{10, 8, 7, 5, 4, 1}` are allowed. If you are tempted to write 9, 6,
  3, or 2, you are over-thinking — pick the tier whose description fits best.
- Judge **meaning**, not language. Wrong-language tokens were already removed
  in Phase 3, so anything you see here is in-locale.
- An audience term (nurse, firefighter, police, driver, carer…) lifts a
  keyword toward 8 **only if** that audience is named in `config.features`.
- A misspelling of a core term is still about the core function — score it on
  intent (a typo of "shift planner" is a high tier; "shitty" is a 4).

Fill the `semantic` column for every row in `filtered.csv`.

---

## 4.2 `competitor` (0–10) — coverage × ranking strength (SCRIPT, DETERMINISTIC)

This measures how strongly rivals validate the keyword: how **many** rank it
and how **high**. It is computed; you never set it by hand.

Per-app strength from rank (config `scoring.rank_strength`, default shown):

| Rank | strength |
|---|---|
| 1–5 | 1.00 |
| 6–10 | 0.80 |
| 11–25 | 0.50 |
| 26–50 | 0.25 |
| 51–100 | 0.10 |

With `n` = number of ranking apps (≥3) and `avg_strength` = mean strength of
the ranking apps:

```
coverage_part = (n / total_competitors) * 10
strength_part = avg_strength * 10
competitor    = round( W_cov * coverage_part + W_str * strength_part )   # clamp 1..10
```

Defaults `W_cov = 0.5`, `W_str = 0.5` (config `scoring.w_cov` / `w_str`,
must sum to 1). These live in the config so the number is identical for every
locale and every run.

**Why this doubles as the volume signal:** ASA popularity is floored at 5 for
nearly all keywords, so true volume is unavailable. A keyword that many strong
competitors rank for is, by definition, one that drives meaningful search
traffic — so `competitor` is the de-facto "high-volume potential" proxy the
brief asks for.

---

## 4.3 `total` (0–10) — final priority (SCRIPT, DETERMINISTIC)

```
total = round( semantic * 0.6 + competitor * 0.4 , 1 )
```

Verified against real data: sem 10 / comp 9 → 9.6; sem 8 / comp 10 → 8.8;
sem 5 / comp 10 → 7.0; sem 4 / comp 9 → 6.0. Do not change the 0.6/0.4 split
without re-deriving it.

Tie-break when two keywords share `total` and only one fits a field: prefer
(a) higher `volume`, then (b) shorter character length. Never fold volume or
length into `total` itself.

---

## How to run

After you have filled the `semantic` column in `filtered.csv` (save it as,
e.g., `filtered.semantic.csv`):

```bash
python scripts/aso_score.py --stage total \
  --in <locale>/filtered.semantic.csv \
  --config <path-to-config.json> \
  --out <locale>/scored.csv
```

The script validates that every `semantic` value is one of the six legal
tiers, recomputes `competitor` from the ranks (so a hand-edit can't corrupt
it), computes `total`, and sorts descending.

## Done when

`scored.csv` exists, every row has a legal `semantic`, a script-computed
`competitor` and `total`, sorted by `total` descending.
