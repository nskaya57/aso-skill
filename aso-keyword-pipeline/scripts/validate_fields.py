#!/usr/bin/env python3
"""
validate_fields.py — prove a composed locale's fields satisfy every rule.

Checks (App Store):
  - Title <= title limit, Subtitle <= subtitle limit
  - Keyword field <= keywords limit and >= keywords_min
  - Promo <= promo limit, Description <= description limit
  - No token repeated across Title / Subtitle / Keyword field
  - No singular/plural pair inside the keyword field
  - No stop word / 'app' / 'free' inside the keyword field
  - Keyword field is comma-separated with NO spaces around commas

Reads fields.csv (one row for the locale) + the config. Exits non-zero on any
violation so the pipeline cannot mark a locale "done" while broken.

Pure standard library.
"""
import argparse
import csv
import json
import re
import sys


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def norm(s):
    return (s or "").strip().lower()


_WORD_RE = re.compile(r"[a-z0-9äöüßçğıöşüа-яё぀-ヿ一-鿿가-힯]+")


def word_tokens(text):
    """Alphanumeric/script tokens only. Drops punctuation (`-`, `&`,
    quotes, `…`) so dashes in titles don't become spurious tokens."""
    return [t for t in _WORD_RE.findall(norm(text)) if t and len(t) >= 2]


DEFAULT_PLURAL_SUFFIXES = {
    # English handles via stemming
    "en":    ["s", "es", "ies"],
    "en-US": ["s", "es", "ies"],
    "en-GB": ["s", "es", "ies"],
    # German: -e, -er, -en, -n, -s
    "de":    ["e", "er", "en", "n", "s"],
    "de-DE": ["e", "er", "en", "n", "s"],
    # Turkish: -lar / -ler
    "tr":    ["lar", "ler"],
    "tr-TR": ["lar", "ler"],
    # French: -s, -x
    "fr":    ["s", "x"],
    "fr-FR": ["s", "x"],
    # Spanish: -s, -es
    "es":    ["s", "es"],
    "es-ES": ["s", "es"],
    "es-MX": ["s", "es"],
    # Italian: -i, -e
    "it":    ["i", "e"],
    "it-IT": ["i", "e"],
    # Portuguese: -s, -es
    "pt":    ["s", "es"],
    "pt-BR": ["s", "es"],
    "pt-PT": ["s", "es"],
    # Dutch: -en, -s
    "nl":    ["en", "s"],
    "nl-NL": ["en", "s"],
    # Polish: -y, -e
    "pl":    ["y", "e"],
    "pl-PL": ["y", "e"],
}


def resolve_plural_suffixes(locale, custom):
    """Pick the suffix list to use for plural-pair detection.
    custom (list[str]) overrides; otherwise look up locale, then language,
    then fall back to English. None means "no detection" (validator skips
    the plural check)."""
    if custom is not None:
        return custom or None  # explicit [] → skip
    s = DEFAULT_PLURAL_SUFFIXES.get(locale)
    if s is None and locale and "-" in locale:
        s = DEFAULT_PLURAL_SUFFIXES.get(locale.split("-", 1)[0])
    return s or DEFAULT_PLURAL_SUFFIXES["en"]


def plural_pairs(kw_tokens, suffixes):
    """Return list of (singular, plural) pairs using the given suffix list.
    If `suffixes` is None or empty, returns []."""
    if not suffixes:
        return []
    s = set(kw_tokens)
    pairs = []
    for w in kw_tokens:
        for suffix in suffixes:
            plural = w + suffix
            if plural in s and plural != w:
                pairs.append((w, plural))
    seen, out = set(), []
    for a, b in pairs:
        key = tuple(sorted((a, b)))
        if key not in seen:
            seen.add(key)
            out.append((a, b))
    return out


def main():
    p = argparse.ArgumentParser(description="Validate composed ASO fields")
    p.add_argument("--in", dest="infile", required=True, help="fields.csv")
    p.add_argument("--config", required=True)
    p.add_argument("--locale", required=True)
    args = p.parse_args()

    cfg = load_config(args.config)
    lim = cfg["field_limits"]
    stop = {norm(s) for s in cfg.get("stopwords", [])} | {"app", "free"}

    with open(args.infile, "r", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if norm(r.get("locale")) == norm(args.locale)]
    if not rows:
        sys.exit(f"ERROR: no row for locale {args.locale} in {args.infile}")
    if len(rows) > 1:
        sys.exit(f"ERROR: {len(rows)} rows for locale {args.locale} in "
                 f"{args.infile}. Validator expects locale-specific fields.csv "
                 f"(one row). OUTPUT.csv (multi-locale) is a consolidated "
                 f"reference; do not run validator against it.")
    row = rows[0]

    title = row.get("title", "")
    subtitle = row.get("subtitle", "")
    keywords = row.get("keywords", "")
    promo = row.get("promo", "")
    desc = row.get("description", "")

    problems = []
    oks = []

    def check(cond, ok_msg, bad_msg):
        (oks if cond else problems).append(ok_msg if cond else bad_msg)

    # length limits
    check(len(title) <= lim["title"],
          f"Title {len(title)}/{lim['title']}",
          f"Title TOO LONG {len(title)}/{lim['title']}")
    check(len(subtitle) <= lim["subtitle"],
          f"Subtitle {len(subtitle)}/{lim['subtitle']}",
          f"Subtitle TOO LONG {len(subtitle)}/{lim['subtitle']}")
    check(len(keywords) <= lim["keywords"],
          f"Keywords {len(keywords)}/{lim['keywords']}",
          f"Keywords TOO LONG {len(keywords)}/{lim['keywords']}")
    check(len(keywords) >= lim.get("keywords_min", 0),
          f"Keywords fill >= {lim.get('keywords_min', 0)} ({len(keywords)})",
          f"Keywords UNDERFILLED {len(keywords)} < {lim.get('keywords_min', 0)}")
    check(len(promo) <= lim["promo"],
          f"Promo {len(promo)}/{lim['promo']}",
          f"Promo TOO LONG {len(promo)}/{lim['promo']}")
    check(len(desc) <= lim["description"],
          f"Description {len(desc)}/{lim['description']}",
          f"Description TOO LONG {len(desc)}/{lim['description']}")

    # keyword field format: comma-separated, no spaces
    if " " in keywords:
        problems.append("Keyword field contains a SPACE (use comma-only, no spaces)")
    else:
        oks.append("Keyword field has no spaces")

    kw_tokens = [t.strip() for t in norm(keywords).split(",") if t.strip()]

    # stopwords in keyword field
    bad_stop = [t for t in kw_tokens if t in stop]
    check(not bad_stop,
          "No stop/generic words in keyword field",
          f"Stop/generic words in keyword field: {bad_stop}")

    # plural pairs in keyword field — locale-aware
    plural_cfg = (cfg.get("plural_rules") or {}).get(args.locale)
    suffixes = resolve_plural_suffixes(args.locale, plural_cfg)
    pairs = plural_pairs(kw_tokens, suffixes)
    if suffixes:
        check(not pairs,
              f"No singular/plural pairs in keyword field "
              f"(suffixes: {','.join(suffixes)})",
              f"Singular/plural pairs in keyword field: {pairs}")
    else:
        oks.append(f"Plural-pair check skipped for {args.locale} "
                   f"(no suffix rules — review keyword field manually)")

    # Internal duplicates inside the keyword field itself
    seen, kw_dups = set(), []
    for t in kw_tokens:
        if t in seen:
            kw_dups.append(t)
        else:
            seen.add(t)
    check(not kw_dups,
          "No duplicate tokens within keyword field",
          f"Duplicate tokens inside keyword field: {sorted(set(kw_dups))}")

    # cross-field duplication (token level)
    title_tok = set(word_tokens(title))
    sub_tok = set(word_tokens(subtitle))
    kw_set = set(kw_tokens)
    dup_ts = title_tok & sub_tok
    dup_tk = title_tok & kw_set
    dup_sk = sub_tok & kw_set
    # brand token in title is expected; ignore EVERY token of the app name
    # (so multi-word app names like "Work Day" don't trip false duplicates)
    appname_tokens = set(word_tokens(cfg.get("app_name", "")))
    for s in (dup_ts, dup_tk, dup_sk):
        s -= appname_tokens
    check(not dup_tk, "No Title<->Keyword duplicate tokens",
          f"Title<->Keyword duplicate tokens: {sorted(dup_tk)}")
    check(not dup_sk, "No Subtitle<->Keyword duplicate tokens",
          f"Subtitle<->Keyword duplicate tokens: {sorted(dup_sk)}")
    check(not dup_ts, "No Title<->Subtitle duplicate tokens",
          f"Title<->Subtitle duplicate tokens: {sorted(dup_ts)}")

    print(f"=== validate {args.locale} ===")
    for o in oks:
        print(f"  PASS  {o}")
    for pr in problems:
        print(f"  FAIL  {pr}")
    if problems:
        print(f"\nRESULT: FAIL ({len(problems)} violation(s)) — fix and re-run.")
        sys.exit(1)
    print("\nRESULT: PASS — locale fields are valid.")


if __name__ == "__main__":
    main()
