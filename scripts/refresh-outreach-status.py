#!/usr/bin/env python3
"""
refresh-outreach-status.py — detect drift between outreach matrix and live PR state.

`.github/channel-partners.md` tracks every outreach attempt manually. Status entries
get stale: a PR I submitted weeks ago may have been merged, closed, or ghosted, but
the matrix still says `contacted`. Manually `gh pr view`-ing each entry is tedious.

This script reads the matrix, extracts every PR URL it finds, queries `gh pr view`
for each, and reports drift between recorded status and live state. **Report-only**
— mirrors the broken-link / staleness-check policy of "open issue, don't auto-modify".

Status mapping logic (conservative — only the unambiguous cases are auto-flagged):
- `merged: true` → matrix should say `merged-or-listed`
- `state: CLOSED` + not merged → flag for human review (`replied-negative` or just abandoned)
- `state: OPEN` + `updatedAt > N days ago` (default 14) + no recent comments → suggest `ghosted` review
- `state: OPEN` + recent activity → no change

Usage:
    python scripts/refresh-outreach-status.py                    # default text report
    python scripts/refresh-outreach-status.py --ghost-days 21    # bump ghost threshold
    python scripts/refresh-outreach-status.py --format markdown  # GH issue body
    python scripts/refresh-outreach-status.py --format json      # CI / tooling
    python scripts/refresh-outreach-status.py --check            # exit 1 if drift detected

Env:
    `gh` (GitHub CLI) on PATH, authenticated.

Exit codes:
    0 — no drift (or report finished)
    1 — `--check` mode and drift detected
    2 — environment error (gh / file missing)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MATRIX_PATH = REPO_ROOT / ".github" / "channel-partners.md"

# Matches PR URLs anywhere in the file.
PR_URL_RE = re.compile(r"https://github\.com/([\w.-]+)/([\w.-]+?)/pull/(\d+)")

# Matches markdown table rows (8 columns expected per channel-partners.md schema).
# We don't need to fully parse — just identify "this line is a matrix row" and pull
# the 4th column (Status). Use simple `|` split with leading/trailing strip.
ROW_RE = re.compile(r"^\|\s*(?:\d+|E\d+|[A-Z]\d+)\s*\|")  # row leader like `| 6 |` or `| E1 |`

# Valid status enum from the matrix legend.
VALID_STATUSES = {
    "not contacted", "contacted", "replied-positive", "replied-negative",
    "merged-or-listed", "ghosted", "cooldown",
}


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess | None:
    """Wrap subprocess.run with explicit UTF-8 decoding (Windows cp950 safety)."""
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except (subprocess.SubprocessError, OSError) as e:
        print(f"  ! subprocess error: {e}", file=sys.stderr)
        return None


def gh_pr_view(owner: str, repo: str, number: str) -> dict | None:
    """Query gh pr view. Returns dict with state/merged/updatedAt/comments_count, or None."""
    result = _run(
        ["gh", "pr", "view", number,
         "--repo", f"{owner}/{repo}",
         "--json", "state,reviewDecision,updatedAt,mergedAt,closedAt,isDraft,comments"],
        timeout=15,
    )
    if result is None or result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout or "")
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
    # comments is a list of {body, author, ...} — we only need the count for "ghost?" detection
    data["comments_count"] = len(data.get("comments") or [])
    data.pop("comments", None)
    return data


def parse_matrix(text: str) -> list[dict]:
    """Extract matrix rows that contain a PR URL.

    Returns list of:
        {row_text, line_no, status_recorded, pr_url, pr_owner, pr_repo, pr_number}
    """
    rows = []
    for i, line in enumerate(text.splitlines(), start=1):
        if not ROW_RE.match(line):
            continue
        pr_match = PR_URL_RE.search(line)
        if not pr_match:
            continue
        # Parse columns by splitting on `|` and stripping. First+last are empty.
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) < 4:
            continue
        status = cols[3].lower()
        rows.append({
            "row_text": line,
            "line_no": i,
            "status_recorded": status,
            "pr_url": pr_match.group(0),
            "pr_owner": pr_match.group(1),
            # Mirror normalize_repo convention from refresh-stars.py / check-catalog-staleness.py:
            # strip .git suffix so `github.com/foo/bar.git/pull/1` doesn't 404 at gh api
            "pr_repo": pr_match.group(2).removesuffix(".git"),
            "pr_number": pr_match.group(3),
        })
    return rows


def classify_drift(row: dict, pr_data: dict, now: datetime, ghost_days: int) -> dict:
    """Compare recorded matrix status to live PR state.

    Returns:
        {verdict, suggested_status, reason, age_days}
    where verdict ∈ {"OK", "UPDATE", "REVIEW"}
    """
    recorded = row["status_recorded"]
    state = pr_data.get("state")  # "OPEN" / "MERGED" / "CLOSED"
    is_merged = bool(pr_data.get("mergedAt"))
    updated_at = pr_data.get("updatedAt")
    review_decision = pr_data.get("reviewDecision")  # APPROVED / CHANGES_REQUESTED / REVIEW_REQUIRED / ""

    age_days = None
    if updated_at:
        try:
            dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            age_days = (now - dt).days
        except (ValueError, AttributeError):
            pass

    # Case 1: PR merged but matrix doesn't reflect → unambiguous update
    if is_merged and recorded != "merged-or-listed":
        return {
            "verdict": "UPDATE",
            "suggested_status": "merged-or-listed",
            "reason": f"PR merged at {pr_data.get('mergedAt')}, matrix says `{recorded}`",
            "age_days": age_days,
        }

    # Case 2: PR closed (not merged) but matrix doesn't reflect → needs human review
    if state == "CLOSED" and not is_merged and recorded not in ("replied-negative", "cooldown"):
        return {
            "verdict": "REVIEW",
            "suggested_status": "replied-negative",
            "reason": f"PR closed (not merged) at {pr_data.get('closedAt')}, "
                      f"matrix says `{recorded}` — confirm decline vs abandonment",
            "age_days": age_days,
        }

    # Case 3: PR has APPROVED review but not merged → maintainer is aware, ping might help
    if state == "OPEN" and review_decision == "APPROVED" and recorded == "contacted":
        return {
            "verdict": "REVIEW",
            "suggested_status": "replied-positive",
            "reason": "PR approved by reviewer but not merged yet — consider replied-positive",
            "age_days": age_days,
        }

    # Case 4: PR stale (no update in N+ days) + matrix says `contacted`
    if state == "OPEN" and recorded == "contacted" and age_days is not None and age_days >= ghost_days:
        return {
            "verdict": "REVIEW",
            "suggested_status": "ghosted",
            "reason": f"PR unchanged for {age_days}d (threshold {ghost_days}d), "
                      f"no human review — consider ghosted",
            "age_days": age_days,
        }

    # Case 5: everything aligned
    return {
        "verdict": "OK",
        "suggested_status": recorded,
        "reason": f"PR state={state}, matrix status=`{recorded}`",
        "age_days": age_days,
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ghost-days", type=int, default=14,
                        help="OPEN PR with no update in N+ days suggests ghosted (default: 14)")
    parser.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    parser.add_argument("--check", action="store_true",
                        help="Exit 1 if any drift detected (CI gating)")
    parser.add_argument("--matrix", default=str(MATRIX_PATH), type=Path,
                        help=f"Path to outreach matrix (default: {MATRIX_PATH.relative_to(REPO_ROOT)})")
    args = parser.parse_args()

    if not args.matrix.exists():
        print(f"error: matrix file not found: {args.matrix}", file=sys.stderr)
        sys.exit(2)

    probe = _run(["gh", "auth", "status"], timeout=10)
    if probe is None or probe.returncode != 0:
        print("error: `gh` CLI not authenticated. Run `gh auth login` first.",
              file=sys.stderr)
        sys.exit(2)

    text = args.matrix.read_text(encoding="utf-8")
    rows = parse_matrix(text)
    print(f"Found {len(rows)} matrix row(s) with PR URLs.", file=sys.stderr)

    if not rows:
        print("(no PR-bearing rows to check)", file=sys.stderr)
        return

    now = datetime.now(timezone.utc)
    results = []
    for row in rows:
        print(f"  fetching {row['pr_owner']}/{row['pr_repo']}#{row['pr_number']}...",
              file=sys.stderr)
        pr_data = gh_pr_view(row["pr_owner"], row["pr_repo"], row["pr_number"])
        if pr_data is None:
            results.append({
                **row,
                "verdict": "ERROR",
                "suggested_status": None,
                "reason": "gh pr view failed (auth / 404 / network)",
                "age_days": None,
                "pr_state": None,
            })
            continue
        drift = classify_drift(row, pr_data, now, args.ghost_days)
        results.append({
            **row,
            **drift,
            "pr_state": pr_data.get("state"),
            "review_decision": pr_data.get("reviewDecision"),
            "merged_at": pr_data.get("mergedAt"),
            "closed_at": pr_data.get("closedAt"),
            "comments_count": pr_data.get("comments_count"),
        })

    has_drift = any(r["verdict"] in ("UPDATE", "REVIEW", "ERROR") for r in results)

    if args.format == "json":
        json.dump({
            "checked_at": now.isoformat(),
            "ghost_days": args.ghost_days,
            "results": results,
        }, sys.stdout, indent=2)
        print()
    elif args.format == "markdown":
        _emit_markdown(results, args.ghost_days, now)
    else:
        _emit_text(results, args.ghost_days)

    if args.check and has_drift:
        sys.exit(1)


def _emit_text(results, ghost_days):
    print()
    print("=" * 68)
    counts = {"OK": 0, "UPDATE": 0, "REVIEW": 0, "ERROR": 0}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print(f"OK: {counts['OK']}  ·  UPDATE: {counts['UPDATE']}  ·  "
          f"REVIEW: {counts['REVIEW']}  ·  ERROR: {counts['ERROR']}")
    print(f"(ghost threshold: {ghost_days}d)")
    print()

    for r in results:
        if r["verdict"] == "OK":
            continue
        print(f"[{r['verdict']}] {r['pr_owner']}/{r['pr_repo']}#{r['pr_number']}")
        print(f"  matrix row     : line {r['line_no']}, status=`{r['status_recorded']}`")
        print(f"  pr state       : {r.get('pr_state', '?')}"
              + (f", review={r['review_decision']}" if r.get('review_decision') else ""))
        if r["suggested_status"] and r["suggested_status"] != r["status_recorded"]:
            print(f"  suggested      : `{r['suggested_status']}`")
        print(f"  reason         : {r['reason']}")
        print()


def _emit_markdown(results, ghost_days, now):
    print(f"# Outreach matrix drift report — {now.date().isoformat()}\n")
    print(f"Ghost threshold: **{ghost_days} days** of inactivity.\n")
    counts = {"OK": 0, "UPDATE": 0, "REVIEW": 0, "ERROR": 0}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print(f"**OK**: {counts['OK']} · **UPDATE**: {counts['UPDATE']} · "
          f"**REVIEW**: {counts['REVIEW']} · **ERROR**: {counts['ERROR']}\n")

    drift_rows = [r for r in results if r["verdict"] != "OK"]
    if not drift_rows:
        print("All matrix entries align with live PR state. ✓")
        return

    print("## Drift detected\n")
    print("| Verdict | PR | Matrix status | PR state | Suggested | Reason |")
    print("|---|---|---|---|---|---|")
    for r in drift_rows:
        pr_link = f"[{r['pr_owner']}/{r['pr_repo']}#{r['pr_number']}]({r['pr_url']})"
        suggested = f"`{r['suggested_status']}`" if r["suggested_status"] and \
                    r["suggested_status"] != r["status_recorded"] else "—"
        pr_state = r.get("pr_state") or "?"
        if r.get("review_decision"):
            pr_state += f" / {r['review_decision']}"
        print(f"| {r['verdict']} | {pr_link} | `{r['status_recorded']}` | {pr_state} | "
              f"{suggested} | {r['reason']} |")

    print("\n## Suggested actions\n")
    print("- **UPDATE**: matrix is unambiguously stale (e.g., PR merged). Edit `Status` column "
          "to the suggested value and commit.")
    print("- **REVIEW**: judgment needed — confirm whether the PR truly declined / ghosted, "
          "then update Status + optionally add Notes context.")
    print("- **ERROR**: gh CLI couldn't reach the PR (auth / 404 / network). Investigate.")
    print("\n*Generated by `scripts/refresh-outreach-status.py`*.")


if __name__ == "__main__":
    main()
