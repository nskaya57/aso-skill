#!/usr/bin/env python3
"""
fetch_keywords.py — Phase 1 fetcher.

Reads .env at project root for APPTWEAK_API_KEY (or the env var named in
config.apptweak_key_env), then for one --locale fetches each competitor's
best-N ranked keywords from AppTweak and writes one JSON per competitor
to ASO/<AppName>/<locale>/raw/<CompetitorName>.json.

Pure standard library: only urllib + json + csv + argparse. No deps.

Usage:
    python fetch_keywords.py --config <path-to-config.json> \\
                             --locale en-US \\
                             --out-dir ASO/ShiftGo/en-US/raw \\
                             [--max 100] [--env .env]
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PAGE_LIMIT = 100  # default best-N per Phase 1 spec
ENDPOINT   = "https://public-api.apptweak.com/api/public/store/keywords/suggestions/app.json"
HEALTH_ENDPOINT = "https://public-api.apptweak.com/api/public/store/apps/metrics/current.json"

RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRIES = 3


def load_dotenv(path):
    """Tiny .env parser: KEY=VALUE per line, comments and blanks ignored.
    Uses utf-8-sig to swallow a UTF-8 BOM on Windows-saved files."""
    env = {}
    if not os.path.exists(path):
        return env
    with open(path, "r", encoding="utf-8-sig") as f:
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
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        sys.exit(f"ERROR: config not found: {path}. Run Phase 0b first.")
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: config is not valid JSON ({path}): {e}")


def validate_inputs(cfg, locale, api_key, key_var):
    if not api_key:
        sys.exit(f"ERROR: API key not found. The config expects '{key_var}' "
                 f"in .env (or env). Run Phase 0a (or `export {key_var}=...`).")
    comps = cfg.get("competitors", [])
    if len(comps) < 3:
        sys.exit(f"ERROR: config has {len(comps)} competitors; pipeline needs "
                 f"at least 3 (≥3 rule). See Phase 0b.")
    for c in comps:
        if not c.get("app_id"):
            sys.exit(f"ERROR: competitor '{c.get('name')}' has empty app_id. "
                     f"Run Phase 0b to fill it.")
        if not str(c["app_id"]).isdigit():
            sys.exit(f"ERROR: competitor '{c.get('name')}' app_id "
                     f"'{c['app_id']}' is not numeric.")
    if locale not in cfg.get("locales", {}):
        sys.exit(f"ERROR: locale '{locale}' not in config.locales. "
                 f"Available: {sorted(cfg.get('locales', {}).keys())}")


def http_get_json(url, headers, *, what="request"):
    """GET with retry/backoff on 429/5xx, surface friendly 403 message."""
    last_err = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            if e.code == 403 and "Unknown token" in body:
                sys.exit("ERROR: AppTweak rejected the API key (HTTP 403 "
                         "Unknown token). The token in .env is wrong or "
                         "revoked. Re-run Phase 0a with a fresh token.")
            if e.code in RETRY_STATUSES and attempt < MAX_RETRIES:
                wait = 2 ** attempt
                print(f"  [retry {attempt}/{MAX_RETRIES} in {wait}s — "
                      f"{what} HTTP {e.code}]", file=sys.stderr)
                time.sleep(wait)
                last_err = f"HTTP {e.code} — {body}"
                continue
            sys.exit(f"ERROR {what}: HTTP {e.code} — {body}")
        except urllib.error.URLError as e:
            if attempt < MAX_RETRIES:
                wait = 2 ** attempt
                print(f"  [retry {attempt}/{MAX_RETRIES} in {wait}s — "
                      f"{what} {e.reason}]", file=sys.stderr)
                time.sleep(wait)
                last_err = str(e.reason)
                continue
            sys.exit(f"ERROR {what}: {e.reason}")
    sys.exit(f"ERROR {what}: retries exhausted ({last_err})")


def preflight_check(api_key, cfg, locale):
    """Cheap metadata call against the first competitor to verify the key
    works before we spend credits on the full pull."""
    c = cfg["competitors"][0]
    loc = cfg["locales"][locale]
    qs = urllib.parse.urlencode({
        "apps": c["app_id"], "country": loc["country"],
        "device": loc["device"], "metrics": "app-power",
    })
    url = f"{HEALTH_ENDPOINT}?{qs}"
    http_get_json(url, {
        "x-apptweak-key": api_key,
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    }, what="preflight key check")


def fetch_page(api_key, app_id, country, device, offset, limit):
    qs = urllib.parse.urlencode({
        "apps": app_id, "country": country, "device": device,
        "limit": limit, "offset": offset,
        "sort": "score", "sort_direction": "desc",
    })
    url = f"{ENDPOINT}?{qs}"
    data = http_get_json(url, {
        "x-apptweak-key": api_key,
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    }, what=f"{app_id} ({country}/{device}) offset={offset}")
    # Defensive: AppTweak shape contract — surface a clear error if not present
    try:
        return data["result"][app_id]["suggestions"]
    except (KeyError, TypeError):
        sys.exit(f"ERROR: unexpected AppTweak response shape for {app_id}. "
                 f"First 200 chars: {json.dumps(data)[:200]}")


def fetch_competitor(api_key, app_id, country, device, max_total):
    """Page until <pagesize returned OR we have max_total keywords.
    Each page asks for only min(500, remaining) so we don't burn credits
    on rows we'll throw away."""
    suggestions, offset = [], 0
    while len(suggestions) < max_total:
        remaining = max_total - len(suggestions)
        page_size = min(500, remaining)
        sugs = fetch_page(api_key, app_id, country, device, offset, page_size)
        suggestions.extend(sugs)
        if len(sugs) < page_size:
            break  # last page
        offset += page_size
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
                   help=f"max keywords per competitor (default {PAGE_LIMIT}; spec says 100)")
    p.add_argument("--skip-preflight", action="store_true",
                   help="skip the API-key preflight check")
    args = p.parse_args()

    cfg = load_config(args.config)
    env = load_dotenv(args.env)
    key_var = cfg.get("apptweak_key_env", "APPTWEAK_API_KEY")
    api_key = env.get(key_var) or os.environ.get(key_var, "")

    if env and key_var not in env and key_var not in os.environ:
        print(f"WARN: config expects env var '{key_var}' but .env "
              f"({args.env}) has only {sorted(env.keys())}. Falling back to "
              f"shell environment.", file=sys.stderr)

    validate_inputs(cfg, args.locale, api_key, key_var)

    if not args.skip_preflight:
        print("  [preflight] checking API key ...", end=" ", flush=True)
        preflight_check(api_key, cfg, args.locale)
        print("ok")

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
        # AppTweak cost = #keywords + 1 base per call
        total_credits += len(sugs) + 1
        print(f"{len(sugs)} kw")

    print(f"done. estimated credits: ~{total_credits}")


if __name__ == "__main__":
    main()
