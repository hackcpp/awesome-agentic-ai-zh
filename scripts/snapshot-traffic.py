#!/usr/bin/env python3
"""
snapshot-traffic.py — capture a weekly traffic snapshot for trend analysis.

`gh api repos/<repo>/traffic/views` (and `clones`) only return the **last 14 days**.
Anything older is unrecoverable. This script captures a periodic snapshot and writes
it to `docs/traffic/snapshots/YYYY-MM-DD.json` so historical trend is preserved.

Captures per snapshot:
- 14-day rolling totals (views + clones × {count, uniques})
- Daily breakdown (14 entries × {timestamp, count, uniques})
- Top 10 referrers (where visitors came from)
- Top 10 popular paths (which pages they read)
- Point-in-time totals (stars, forks, open_issues, subscribers)

Each file is ~5-10 KB. Over 5 years of weekly snapshots ≈ 1-3 MB total — negligible.

Designed to run from a weekly cron (workflow integration is a separate concern;
see `weekly-traffic-snapshot.yml` if shipped). Idempotent — re-running on the same
day overwrites the file.

Usage:
    python scripts/snapshot-traffic.py                          # write today's snapshot
    python scripts/snapshot-traffic.py --dry-run                # print JSON, don't write
    python scripts/snapshot-traffic.py --out path/to/file.json  # custom output path
    python scripts/snapshot-traffic.py --repo owner/name        # override repo (default: auto-detect)

Env:
    `gh` (GitHub CLI) on PATH, authenticated with repo-traffic permission.
    GitHub requires push access to the repo to read traffic data.

Exit codes:
    0 — snapshot written (or printed in --dry-run)
    1 — gh api failed for one or more endpoints
    2 — environment error (gh missing / auth failed / repo not push-accessible)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "traffic" / "snapshots"


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess | None:
    """Wrap subprocess.run with explicit UTF-8 decoding.

    Windows defaults `text=True` to the platform locale (cp950 on zh-TW Windows),
    which crashes on gh-api responses that contain non-ASCII (referrer names like
    "Github.com — Articles", em-dashes, CJK paths). Force UTF-8 across the board.
    """
    try:
        return subprocess.run(
            cmd,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout,
        )
    except (subprocess.SubprocessError, OSError) as e:
        print(f"  ! subprocess error: {e}", file=sys.stderr)
        return None


def detect_repo() -> str | None:
    """Auto-detect owner/repo from `gh repo view`."""
    result = _run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        timeout=10,
    )
    if result is None or result.returncode != 0:
        return None
    name = (result.stdout or "").strip()
    return name or None


def gh_api(path: str) -> dict | list | None:
    """Single `gh api <path>` call. Returns parsed JSON or None on failure."""
    result = _run(["gh", "api", path], timeout=20)
    if result is None:
        return None
    if result.returncode != 0:
        print(f"  ! gh api {path} failed: {(result.stderr or '').strip()[:120]}",
              file=sys.stderr)
        return None
    try:
        return json.loads(result.stdout or "")
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        print(f"  ! gh api {path} JSON decode error: {e}", file=sys.stderr)
        return None


def take_snapshot(repo: str, now: datetime) -> tuple[dict, list[str]]:
    """Fetch all traffic + summary metrics for `repo`.

    `now` is passed in (rather than called inside) so the snapshot_at timestamp
    matches the date used for the output filename — no midnight-UTC race.

    Returns (snapshot_dict, list_of_failed_endpoints).
    Each failed endpoint is recorded but does not abort — partial snapshots are
    better than no snapshot when a single API call hiccups.
    """
    failed: list[str] = []

    def _fetch(label: str, path: str):
        data = gh_api(path)
        if data is None:
            failed.append(label)
        return data

    print(f"Snapshotting {repo}...", file=sys.stderr)
    views = _fetch("views", f"repos/{repo}/traffic/views")
    clones = _fetch("clones", f"repos/{repo}/traffic/clones")
    referrers = _fetch("referrers", f"repos/{repo}/traffic/popular/referrers")
    paths = _fetch("paths", f"repos/{repo}/traffic/popular/paths")
    meta = _fetch("meta", f"repos/{repo}")

    snapshot = {
        "schema_version": 1,
        "snapshot_at": now.isoformat(),
        "repo": repo,
        "totals": _safe_totals(meta),
        "views_14d": _safe_traffic_totals(views),
        "clones_14d": _safe_traffic_totals(clones),
        "daily_views": _safe_daily(views),
        "daily_clones": _safe_daily(clones),
        "top_referrers": _safe_list(referrers, 10),
        "top_paths": _safe_paths(paths, 10),
    }
    return snapshot, failed


def _safe_totals(meta: dict | None) -> dict:
    if not isinstance(meta, dict):
        return {}
    return {
        "stargazers": meta.get("stargazers_count"),
        "forks": meta.get("forks_count"),
        "open_issues": meta.get("open_issues_count"),
        "subscribers": meta.get("subscribers_count"),
    }


def _safe_traffic_totals(d: dict | None) -> dict:
    if not isinstance(d, dict):
        return {}
    return {"count": d.get("count"), "uniques": d.get("uniques")}


def _safe_daily(d: dict | None) -> list:
    if not isinstance(d, dict):
        return []
    # GH traffic/views returns {"views": [...]}, traffic/clones returns {"clones": [...]}.
    # Try views first, fall back to clones. (.get returns None when absent.)
    items = d.get("views") if "views" in d else d.get("clones")
    if not isinstance(items, list):
        return []
    # Normalize timestamps to date strings for compact storage
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ts = item.get("timestamp", "")
        out.append({
            "date": ts.split("T")[0] if "T" in ts else ts,
            "count": item.get("count"),
            "uniques": item.get("uniques"),
        })
    return out


def _safe_list(items: list | None, limit: int) -> list:
    if not isinstance(items, list):
        return []
    return items[:limit]


def _safe_paths(items: list | None, limit: int) -> list:
    """Paths endpoint includes a `title` field that's often long + non-essential. Strip it."""
    if not isinstance(items, list):
        return []
    return [
        {"path": p.get("path"), "count": p.get("count"), "uniques": p.get("uniques")}
        for p in items[:limit] if isinstance(p, dict)
    ]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=None,
                        help="owner/name (default: auto-detect via `gh repo view`)")
    parser.add_argument("--out", default=None, type=Path,
                        help="output file path (default: docs/traffic/snapshots/YYYY-MM-DD.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print JSON to stdout; do not write")
    args = parser.parse_args()

    # Sanity-check gh
    probe = _run(["gh", "auth", "status"], timeout=10)
    if probe is None or probe.returncode != 0:
        print("error: `gh` CLI not authenticated. Run `gh auth login` first.",
              file=sys.stderr)
        sys.exit(2)

    repo = args.repo or detect_repo()
    if not repo:
        print("error: could not detect repo. Pass --repo owner/name.",
              file=sys.stderr)
        sys.exit(2)

    # Single `now` reference used for both snapshot_at AND the filename — no
    # midnight-UTC race between the two calls.
    now = datetime.now(timezone.utc)
    snapshot, failed = take_snapshot(repo, now)

    if failed and len(failed) == 5:
        # All endpoints failed — likely a permission / auth issue, not a transient hiccup
        print(f"error: all 5 endpoints failed. Confirm you have push access to {repo} "
              f"(traffic API requires it).", file=sys.stderr)
        sys.exit(2)

    if failed:
        print(f"warning: {len(failed)}/5 endpoint(s) failed: {failed}", file=sys.stderr)
        print(f"writing partial snapshot anyway.", file=sys.stderr)

    if args.dry_run:
        json.dump(snapshot, sys.stdout, indent=2)
        print()
        return

    if args.out:
        out_path = args.out
    else:
        out_path = DEFAULT_OUT_DIR / f"{now.date().isoformat()}.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    rel = out_path.relative_to(REPO_ROOT) if out_path.is_absolute() else out_path
    print(f"✓ wrote {rel}", file=sys.stderr)
    print(f"  views_14d: {snapshot['views_14d'].get('count', '?')} "
          f"({snapshot['views_14d'].get('uniques', '?')} uniques)", file=sys.stderr)
    print(f"  clones_14d: {snapshot['clones_14d'].get('count', '?')} "
          f"({snapshot['clones_14d'].get('uniques', '?')} uniques)", file=sys.stderr)
    print(f"  ★ {snapshot['totals'].get('stargazers', '?')} · "
          f"forks {snapshot['totals'].get('forks', '?')}", file=sys.stderr)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
