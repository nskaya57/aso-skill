#!/usr/bin/env python3
"""
smoke_test.py — minimal end-to-end check.

Builds a tiny synthetic dataset (3 competitors, 1 locale) under a temp
directory, runs merge → filter → total → validate, and asserts each step
produces non-empty output. Catches:
  - script regressions (importable + runnable)
  - schema drift (config keys the scripts no longer read or vice versa)
  - obvious off-by-one in the pipeline

Run with: `python scripts/smoke_test.py`. Pure stdlib.
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def write(path, content, *, is_json=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if is_json:
            json.dump(content, f, indent=2)
        else:
            f.write(content)


def make_competitor_json(name, app_id, keywords):
    return {
        "app_id": app_id, "app_name": name,
        "country": "us", "device": "iphone", "locale": "en-US",
        "total_keywords": len(keywords),
        "keywords": [{"keyword": k, "ranking": r, "volume": 5, "score": 50.0,
                      "is_typo": False} for k, r in keywords],
    }


def run(cmd):
    """Run a subprocess, fail loudly on non-zero exit."""
    print(f"  $ {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("STDOUT:\n" + r.stdout)
        print("STDERR:\n" + r.stderr)
        sys.exit(f"FAIL: command exited {r.returncode}")
    return r.stdout


def main():
    tmp = tempfile.mkdtemp(prefix="aso_smoke_")
    print(f"workdir: {tmp}")
    try:
        cfg = {
            "app_name": "Acme", "app_store_id": "1000000001",
            "play_package": "com.acme.app", "root_folder": "ASO",
            "apptweak_key_env": "APPTWEAK_API_KEY",
            "competitors": [
                {"name": "Rival1", "app_id": "2000000001"},
                {"name": "Rival2", "app_id": "2000000002"},
                {"name": "Rival3", "app_id": "2000000003"},
            ],
            "brand_terms": ["acme", "rival1", "rival2", "rival3"],
            "keep_terms": [],
            "stopwords": ["app", "free", "the", "a", "for", "with", "and"],
            "locales": {
                "en-US": {"country": "us", "device": "iphone",
                          "allowed_scripts": ["latin"], "self_indexed": []}
            },
            "scoring": {
                "rank_strength": [
                    {"max": 5, "value": 1.00},   {"max": 10, "value": 0.80},
                    {"max": 25, "value": 0.50},  {"max": 50, "value": 0.25},
                    {"max": 100, "value": 0.10},
                ],
                "w_cov": 0.5, "w_str": 0.5,
            },
            "field_limits": {"title": 30, "subtitle": 30, "keywords": 100,
                             "keywords_min": 90, "promo": 170,
                             "description": 4000},
        }
        cfg_path = os.path.join(tmp, "config.json")
        write(cfg_path, cfg, is_json=True)

        raw_dir = os.path.join(tmp, "raw")
        # Each rival ranks 5 keywords; "shift planner" + "work calendar" by ≥3
        write(os.path.join(raw_dir, "Rival1.json"),
              make_competitor_json("Rival1", "2000000001",
                  [("shift planner", 1), ("work calendar", 8),
                   ("acme planner", 4), ("nurse shift", 12),
                   ("the work", 22)]), is_json=True)
        write(os.path.join(raw_dir, "Rival2.json"),
              make_competitor_json("Rival2", "2000000002",
                  [("shift planner", 4), ("work calendar", 2),
                   ("rival1 alt", 7), ("nurse shift", 18)]), is_json=True)
        write(os.path.join(raw_dir, "Rival3.json"),
              make_competitor_json("Rival3", "2000000003",
                  [("shift planner", 9), ("work calendar", 11),
                   ("shift tracker", 3), ("nurse shift", 6)]), is_json=True)

        merged = os.path.join(tmp, "merged.csv")
        filtered = os.path.join(tmp, "filtered.csv")
        scored = os.path.join(tmp, "scored.csv")
        fields = os.path.join(tmp, "fields.csv")

        sc = os.path.join(HERE, "aso_score.py")
        run([sys.executable, sc, "--stage", "merge", "--raw-dir", raw_dir,
             "--config", cfg_path, "--out", merged])
        rows = list(csv.DictReader(open(merged)))
        assert len(rows) >= 4, f"merged.csv has {len(rows)} rows; expected ≥4"

        run([sys.executable, sc, "--stage", "filter", "--in", merged,
             "--config", cfg_path, "--locale", "en-US", "--out", filtered])
        rows = list(csv.DictReader(open(filtered)))
        assert len(rows) >= 1, "filtered.csv empty — ≥3 rule too strict?"
        keywords_kept = {r["keyword"] for r in rows}
        # 3-app keywords should survive
        for k in ["shift planner", "work calendar", "nurse shift"]:
            assert k in keywords_kept, f"expected '{k}' to survive filter"
        # Brand should be gone
        for k in ["acme planner", "rival1 alt"]:
            assert k not in keywords_kept, f"brand '{k}' not dropped"

        # Fill semantic (forced rubric)
        semantic_map = {
            "shift planner": 10, "work calendar": 10,
            "nurse shift": 8, "shift tracker": 10,
        }
        sem_csv = os.path.join(tmp, "filtered.semantic.csv")
        with open(filtered) as fin, open(sem_csv, "w", newline="") as fout:
            r = csv.DictReader(fin)
            w = csv.DictWriter(fout, fieldnames=r.fieldnames)
            w.writeheader()
            for row in r:
                row["semantic"] = semantic_map.get(row["keyword"], 5)
                w.writerow(row)

        run([sys.executable, sc, "--stage", "total", "--in", sem_csv,
             "--config", cfg_path, "--out", scored])
        rows = list(csv.DictReader(open(scored)))
        assert all(r["total"] for r in rows), "missing total scores"
        assert all(int(r["semantic"]) in {10, 8, 7, 5, 4, 1} for r in rows)

        # Phase 5: fake a fields.csv to validate.
        # Title tokens (shift, planner, calendar) + Subtitle tokens
        # (work, schedule, tracker) must NOT appear in keywords field.
        write(fields,
              "locale,title,subtitle,keywords,promo,description\n"
              'en-US,"Shift Planner Calendar - Acme","Work Schedule & Tracker",'
              '"nurse,roster,duty,job,employee,scheduling,time,maker,calender,personal,hour,rotation,overtime",'
              '"Track shifts in real time.","Track every shift. Acme keeps your work calendar in one place."\n')
        vf = os.path.join(HERE, "validate_fields.py")
        run([sys.executable, vf, "--in", fields, "--config", cfg_path,
             "--locale", "en-US"])

        print("\nSMOKE OK — merge, filter, total, validate all green.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
