#!/usr/bin/env python3
"""
sync.py — Phase 0d / runtime Drive sync via rclone.

Bridges the local ASO/<AppName>/ folder to a Google Drive folder using
the rclone remote configured in Phase 0d. CSV files auto-convert to
Google Sheets (so OUTPUT.csv becomes a real Sheet you can edit in
Drive); JSON and markdown stay as raw files.

Why rclone (not Drive API direct):
- OAuth handled by rclone — survives token expiry, multi-device, multi-
  account out of the box.
- No Python deps — keeps the skill stdlib-only.
- The exact same `gdrive:` remote works whether the user is on Mac or
  Windows or another laptop; only `rclone config` differs per machine.

Usage:
    # Push the entire app folder to Drive (versioned + locale files)
    python scripts/sync.py --config ASO/<App>/config.json --to-drive

    # Pull from Drive (useful when switching to a new machine)
    python scripts/sync.py --config ASO/<App>/config.json --from-drive

    # Push only the active version
    python scripts/sync.py --config ASO/<App>/config.json --to-drive --version v1.0.0
"""
import argparse
import json
import os
import shutil
import subprocess
import sys


def load_config(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        sys.exit(f"ERROR: config not found at {path}. Run Phase 0a first.")
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: config is not valid JSON ({path}): {e}")


def require_rclone():
    if not shutil.which("rclone"):
        sys.exit(
            "ERROR: rclone is not installed.\n"
            "  macOS:   brew install rclone\n"
            "  Linux:   curl https://rclone.org/install.sh | sudo bash\n"
            "  Windows: choco install rclone   (or download from rclone.org)\n"
            "Then run `rclone config` to add a Google Drive remote.\n"
            "See references/phase-0-prepare.md § 0d.")
    try:
        subprocess.run(["rclone", "version"], capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(f"ERROR: `rclone version` failed: {e}")


def require_remote(remote):
    r = subprocess.run(["rclone", "listremotes"],
                       capture_output=True, text=True, check=True)
    remotes = {ln.strip().rstrip(":") for ln in r.stdout.splitlines() if ln.strip()}
    if remote not in remotes:
        sys.exit(
            f"ERROR: rclone remote '{remote}' not found. Available: "
            f"{sorted(remotes) or '<none>'}.\nRun `rclone config` and add a "
            f"Google Drive remote with that name, or update "
            f"config.rclone_remote to one of the existing ones.")


def local_app_path(cfg, config_path):
    """Resolve ASO/<AppName>/ on disk from the config path."""
    root = cfg.get("root_folder", "ASO")
    app_name = cfg["app_name"]
    base = os.path.dirname(os.path.abspath(config_path))
    # config.json lives at ASO/<AppName>/config.json by convention
    if os.path.basename(base) == app_name and \
       os.path.basename(os.path.dirname(base)) == root:
        return base
    # Fall back: assume CWD contains ASO/
    return os.path.join(os.getcwd(), root, app_name)


def remote_app_path(cfg):
    """Drive path: <drive_root>/<AppName>/ — drive_root defaults to the
    same root_folder as local (e.g. 'ASO')."""
    root = cfg.get("drive_root") or cfg.get("root_folder", "ASO")
    return f"{root}/{cfg['app_name']}"


def run_rclone(args, *, dry_run=False, quiet=False):
    if dry_run:
        args = args + ["--dry-run"]
    if not quiet:
        print(f"  $ {' '.join(args)}")
    r = subprocess.run(args)
    if r.returncode != 0:
        sys.exit(f"rclone exited {r.returncode}")


def sync_path(local, remote, *, direction, dry_run=False, delete_extra=False):
    """direction: 'up' (local→remote) or 'down' (remote→local)."""
    if direction == "up":
        src, dst = local, remote
    else:
        src, dst = remote, local
    args = ["rclone", "copy", src, dst,
            # CSVs convert to Google Sheets on upload; download converts back
            "--drive-import-formats", "csv",
            "--drive-export-formats", "csv",
            "-v"]
    if delete_extra:
        args[1] = "sync"  # 'sync' deletes extras at the destination
    run_rclone(args, dry_run=dry_run)


def main():
    p = argparse.ArgumentParser(description="rclone-based Drive sync for ASO/<App>")
    p.add_argument("--config", required=True, help="path to ASO/<App>/config.json")
    direction = p.add_mutually_exclusive_group(required=True)
    direction.add_argument("--to-drive",   action="store_true", help="push local → Drive")
    direction.add_argument("--from-drive", action="store_true", help="pull Drive → local")
    p.add_argument("--version", help="restrict to a single version folder, e.g. v1.0.0")
    p.add_argument("--dry-run", action="store_true", help="show what would change, don't change")
    p.add_argument("--mirror",  action="store_true",
                   help="delete extra files at the destination (rclone sync, not copy)")
    args = p.parse_args()

    cfg = load_config(args.config)
    remote = cfg.get("rclone_remote")
    if not remote:
        sys.exit("ERROR: config.rclone_remote is empty. Run Phase 0d to set it.")

    require_rclone()
    require_remote(remote)

    local = local_app_path(cfg, args.config)
    remote_path = remote_app_path(cfg)

    if args.version:
        local = os.path.join(local, args.version)
        remote_path = f"{remote_path}/{args.version}"

    remote_full = f"{remote}:{remote_path}"
    direction_label = "up" if args.to_drive else "down"
    print(f"sync {direction_label}: {local}  <->  {remote_full}")

    if args.to_drive and not os.path.isdir(local):
        sys.exit(f"ERROR: local path {local} does not exist.")

    sync_path(local, remote_full,
              direction="up" if args.to_drive else "down",
              dry_run=args.dry_run,
              delete_extra=args.mirror)
    print("done.")


if __name__ == "__main__":
    main()
