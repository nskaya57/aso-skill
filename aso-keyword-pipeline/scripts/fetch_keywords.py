#!/usr/bin/env python3
"""
fetch_keywords.py — Phase 1 fetcher.

Reads .env at project root for APPTWEAK_API_KEY (or the env var named in
config.apptweak_key_env), then for one --locale fetches each competitor's
best-100 ranked keywords from AppTweak and writes one JSON per competitor
to ASO/<AppName>/<locale>/raw/<CompetitorName>.json.

Pure standard library: only urllib + json + csv + argparse. No deps.

Usage:
    python fetch_keywords.py --config <path-to-config.json> \\
                             --locale en-US \\
                             --out-dir ASO/ShiftGo/en-US/raw
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

PAGE_LIMIT = 100  # best-100 per Phase 1 spec
ENDPOINT   = "https://public-api.apptweak.com/api/public/store/keywords/suggestions/app.json"


def load_dotenv(path):
    """Tiny .env parser: KEY=VALUE per line, comments and blanks ignored."""
    env = {}
    if not os.path.exists(path):
        return env
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_inputs(cfg, locale, api_key):
    if not api_key:
        sys.exit(f"ERROR: API key not found. Set it in .env "
                 f"(variable {cfg.get('apptweak_key_env', 'APPTWEAK_API_KEY')}) "
                 f"or export it in your shell. See Phase 0a.")
    comps = cfg.get("competitors", [])
    if len(comps) < 3:
        sys.exit(f"ERROR: config has {len(comps)} competitors; pipeline needs "
                 f"at least 3 (≥3 rule). See Phase 0b.")
    for c in comps:
        if not c.get("app_id"):
            sys.exit(f"ERROR: competitor '{c.get('name')}' has empty app_id. "
                     f"Run Phase 0b to fill it.")
        if not c["app_id"].isdigit():
            sys.exit(f"ERROR: competitor '{c.get('name')}' app_id "
                     f"'{c['app_id']}' is not numeric.")
    if locale not in cfg.get("locales", {}):
        sys.exit(f"ERROR: locale '{locale}' not in config.locales. "
                 f"Available: {sorted(cfg.get('locales', {}).keys())}")


def fetch_page(api_key, app_id, country, device, offset, limit=PAGE_LIMIT):
    qs = urllib.parse.urlencode({
        "apps": app_id, "country": country, "device": device,
        "limit": limit, "offset": offset,
        "sort": "score", "sort_direction": "desc",
    })
    url = f"{ENDPOINT}?{qs}"
    req = urllib.request.Request(url, headers={
        "x-apptweak-key": api_key,
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        sys.exit(f"ERROR fetching {app_id} ({country}/{device}): "
                 f"HTTP {e.code} — {body}")
    except urllib.error.URLError as e:
        sys.exit(f"ERROR fetching {app_id} ({country}/{device}): {e.reason}")


def fetch_competitor(api_key, app_id, country, device, max_total=PAGE_LIMIT):
    """Page until <500 returned (last page) OR we have max_total keywords."""
    suggestions, offset = [], 0
    while True:
        d = fetch_page(api_key, app_id, country, device, offset, limit=500)
        sugs = d["result"][app_id]["suggestions"]
        suggestions.extend(sugs)
        if len(sugs) < 500 or len(suggestions) >= max_total:
            break
        offset += 500
        time.sleep(0.4)
    return suggestions[:max_total]


def main():
    p = argparse.ArgumentParser(description="Phase 1: fetch competitor keywords")
    p.add_argument("--config", required=True)
    p.add_argument("--locale", required=True)
    p.add_argument("--out-dir", required=True,
                   help="output dir for <Competitor>.json files (e.g. ASO/<App>/<locale>/raw)")
    p.add_argument("--env", default=".env", help="path to .env file (default: ./.env)")
    p.add_argument("--max", type=int, default=PAGE_LIMIT,
                   help=f"max keywords per competitor (default {PAGE_LIMIT})")
    args = p.parse_args()

    cfg = load_config(args.config)
    env = load_dotenv(args.env)
    key_var = cfg.get("apptweak_key_env", "APPTWEAK_API_KEY")
    api_key = env.get(key_var) or os.environ.get(key_var, "")

    validate_inputs(cfg, args.locale, api_key)

    loc = cfg["locales"][args.locale]
    country, device = loc["country"], loc["device"]
    os.makedirs(args.out_dir, exist_ok=True)

    total_credits = 0
    for c in cfg["competitors"]:
        name = c["name"]
        app_id = c["app_id"]
        print(f"  {name} ({app_id}) [{country}/{device}] ...", end=" ", flush=True)
        sugs = fetch_competitor(api_key, app_id, country, device, args.max)
        out = {
            "app_id": app_id,
            "app_name": name,
            "country": country,
            "device": device,
            "locale": args.locale,
            "total_keywords": len(sugs),
            "keywords": [{
                "keyword": s["keyword"],
                "ranking": s["ranking"],
                "volume": s.get("volume"),
                "score": s.get("score"),
                "is_typo": s.get("is_typo", False),
            } for s in sugs],
        }
        path = os.path.join(args.out_dir, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        # AppTweak cost = #keywords + 1 base
        total_credits += len(sugs) + 1
        print(f"{len(sugs)} kw")

    print(f"done. estimated credits: ~{total_credits}")


if __name__ == "__main__":
    main()
