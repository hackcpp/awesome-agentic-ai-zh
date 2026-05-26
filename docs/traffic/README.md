# Traffic snapshots

Weekly traffic data captured by `scripts/snapshot-traffic.py`. Each file is one snapshot of:

- **14-day rolling totals** — views + clones × {count, uniques}
- **Daily breakdown** — 14 entries per snapshot (one per day)
- **Top 10 referrers** — where visitors came from
- **Top 10 popular paths** — which pages they read
- **Point-in-time totals** — stars / forks / open_issues / subscribers

## Why

GitHub's traffic API (`gh api repos/.../traffic/views`) only returns the last 14 days.
Data older than that is unrecoverable. This directory preserves the historical series
so long-term trends (stargazer growth · referrer shifts · which pages get traction
after outreach pushes) are queryable months later.

## Schema

Each `YYYY-MM-DD.json` follows `schema_version: 1`:

```json
{
  "schema_version": 1,
  "snapshot_at": "2026-05-26T04:30:00+00:00",
  "repo": "WenyuChiou/awesome-agentic-ai-zh",
  "totals": {"stargazers": ..., "forks": ..., "open_issues": ..., "subscribers": ...},
  "views_14d": {"count": ..., "uniques": ...},
  "clones_14d": {"count": ..., "uniques": ...},
  "daily_views": [{"date": "2026-05-12", "count": ..., "uniques": ...}, ...],
  "daily_clones": [...],
  "top_referrers": [{"referrer": "...", "count": ..., "uniques": ...}, ...],
  "top_paths": [{"path": "...", "count": ..., "uniques": ...}, ...]
}
```

If the schema ever evolves, `schema_version` bumps. Older files remain valid
under their original version.

## Cadence

Today: manual. Run `python scripts/snapshot-traffic.py` weekly (Monday morning is
convenient — aligns with the existing weekly-catalog-refresh slot at Mon 04:00 UTC).

Future: a `weekly-traffic-snapshot.yml` GitHub Actions workflow may automate this.
See `.ai/2026/05/26/session-handoff.md` for the open backlog.

## Privacy

These metrics are publicly visible to repo maintainers via the GitHub traffic API
(push access required). Counts are aggregated — no IPs, no user-agents, no per-user
identifiers. Comfortable to publish in this open repo.
