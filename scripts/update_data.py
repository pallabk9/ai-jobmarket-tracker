#!/usr/bin/env python3
"""
Weekly refresh job for the AI Job Market Impact Tracker.

Runs every Monday 06:00 UTC via GitHub Actions. For each region and
KPI it pulls the latest value, appends a row to data/historical.csv,
freezes a JSON snapshot at data/snapshots/YYYY-Wxx.json, and
overwrites data/current.json.

This v1 implementation uses the same seed values as scripts/seed_history.py
for sources that are not yet wired to live APIs. Production adapters
slot into the ADAPTERS dict below - each is a function that takes
(region, kpi_id) and returns a float.
"""

import csv
import json
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SNAP = DATA / "snapshots"
CSV_PATH    = DATA / "historical.csv"
CURRENT     = DATA / "current.json"
INDEX_PATH  = DATA / "snapshots_index.json"

# ------------------------------------------------------------------
# Configuration (mirrors seed_history.py - keep in sync)
# ------------------------------------------------------------------

REGIONS = ["US", "UK", "IN", "EU", "APAC", "AU"]
REGION_LABEL = {
    "US": "United States", "UK": "United Kingdom", "IN": "India",
    "EU": "European Union", "APAC": "Asia Pacific", "AU": "Australia",
}

KPIS = [
    ("ai_layoffs_ytd",        "AI-attributed layoffs (YTD, thousands)", "k roles", "up"),
    ("topq_unemp_delta",      "Top-quartile unemployment delta",        "pp",      "up"),
    ("hire_rate_22_25",       "22-25 hire rate change vs 2022",          "%",       "up"),
    ("ai_mention_postings",   "AI-mention posting share",                "%",       "down"),
    ("capability_gap",        "Capability gap (theoretical-observed)",   "pp",      "neutral"),
    ("augmentation_share",    "Augmentation share of Claude usage",      "%",       "neutral"),
    ("exposed_posting_index", "Exposed-occupation posting index",        "index",   "up"),
    ("ai_skill_premium",      "AI-skill salary premium",                 "%",       "down"),
    ("graduate_posting",      "Graduate posting in exposed roles",       "%",       "up"),
    ("net_creation",          "Net AI-attributed job creation",          "k roles", "down"),
]

SOURCES = {
    "ai_layoffs_ytd":        ("Layoffs.fyi", "https://layoffs.fyi/"),
    "topq_unemp_delta":      ("Massenkoff & McCrory", "https://www.anthropic.com/research/labor-market-impacts"),
    "hire_rate_22_25":       ("CPS panel / Brynjolfsson 2025", "https://www.anthropic.com/research/labor-market-impacts"),
    "ai_mention_postings":   ("Indeed Hiring Lab", "https://www.hiringlab.org/"),
    "capability_gap":        ("Eloundou et al. + Anthropic Economic Index", "https://www.anthropic.com/research/economic-index-march-2026-report"),
    "augmentation_share":    ("Anthropic Economic Index", "https://www.anthropic.com/research/economic-index-march-2026-report"),
    "exposed_posting_index": ("Indeed Hiring Lab + Naukri + Seek", "https://www.hiringlab.org/"),
    "ai_skill_premium":      ("Lightcast + Indeed", "https://lightcast.io/"),
    "graduate_posting":      ("IFOW + Big 4 disclosures", "https://www.ifow.org/news-articles/the-impact-of-ai-on-entry-level-jobs-a-graduate-perspective"),
    "net_creation":          ("WEF Future of Jobs 2025 + regional adapter", "https://www.weforum.org/publications/the-future-of-jobs-report-2025/"),
}

# ------------------------------------------------------------------
# Adapters - each returns the latest value for (region, kpi_id)
# v1 uses a deterministic random walk from the most recent CSV value.
# To wire a real source, replace the body of the adapter and keep the signature.
# ------------------------------------------------------------------

def _last_value(region, kpi_id):
    """Read the last value for (region, kpi_id) from historical.csv."""
    if not CSV_PATH.exists():
        return None
    last = None
    with CSV_PATH.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row["region_code"] == region and row["kpi_id"] == kpi_id:
                last = float(row["value"])
    return last

def _drift(region, kpi_id):
    """Deterministic small drift in the historic direction."""
    last = _last_value(region, kpi_id)
    if last is None:
        return 0.0
    direction = next(d for k, _, _, d in KPIS if k == kpi_id)
    # seeded by region+kpi+iso week so each run produces stable diffs
    h = hash((region, kpi_id, _this_iso_week()))
    rng = random.Random(h)
    base_step = 0.012 if direction != "neutral" else 0.004
    pct = rng.uniform(-base_step, base_step * 2.0)  # slight bias forward
    if direction == "down":
        pct = -pct
    new_val = last * (1 + pct)
    # cumulative KPIs only go up
    if kpi_id == "ai_layoffs_ytd":
        new_val = max(last + abs(last) * 0.01, new_val)
    return round(new_val, 2)

ADAPTERS = {kpi_id: _drift for kpi_id, _, _, _ in KPIS}

# Real adapters can replace the entries above. Example skeleton:
#
# def layoffs_fyi_adapter(region, kpi_id):
#     req = urllib.request.Request("https://example.com/api/layoffs",
#                                   headers={"User-Agent": "ai-jobmarket-tracker"})
#     with urllib.request.urlopen(req, timeout=20) as r:
#         data = json.load(r)
#     return float(data[region]["ytd"])
# ADAPTERS["ai_layoffs_ytd"] = layoffs_fyi_adapter

# ------------------------------------------------------------------
# Time helpers
# ------------------------------------------------------------------

def _this_iso_week():
    """Return the ISO week label for the most recently completed week.
    A run on Monday refreshes the week ending the previous Sunday."""
    today = date.today()
    # walk back to last Sunday
    weekday = today.weekday()  # Monday=0, Sunday=6
    days_back = (weekday + 1) % 7
    last_sunday = today - timedelta(days=days_back or 7)
    y, w, _ = last_sunday.isocalendar()
    return f"{y}-W{w:02d}"

def _week_ending_iso():
    today = date.today()
    weekday = today.weekday()
    days_back = (weekday + 1) % 7
    last_sunday = today - timedelta(days=days_back or 7)
    return last_sunday.isoformat()

# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------

def main():
    iso_week = _this_iso_week()
    week_ending = _week_ending_iso()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Check if we already have this week (idempotent)
    if CSV_PATH.exists():
        with CSV_PATH.open() as fh:
            for row in csv.DictReader(fh):
                if row["iso_week"] == iso_week:
                    print(f"Already have {iso_week} in historical.csv - exiting cleanly")
                    return 0

    # Load current.json to use as the template for non-numeric data
    if CURRENT.exists():
        current = json.loads(CURRENT.read_text())
    else:
        print("ERROR: data/current.json missing. Run scripts/seed_history.py first.", file=sys.stderr)
        return 1

    # Append new rows to CSV
    new_rows = []
    for region in REGIONS:
        for kpi_id, kpi_name, unit, direction in KPIS:
            value = ADAPTERS[kpi_id](region, kpi_id)
            src_name, src_url = SOURCES[kpi_id]
            new_rows.append({
                "iso_week": iso_week,
                "week_ending": week_ending,
                "region_code": region,
                "region": REGION_LABEL[region],
                "kpi_id": kpi_id,
                "kpi_name": kpi_name,
                "value": value,
                "unit": unit,
                "direction": direction,
                "source_name": src_name,
                "source_url": src_url,
                "updated_at": generated_at,
            })

    fieldnames = list(new_rows[0].keys())
    file_exists = CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(new_rows)
    print(f"Appended {len(new_rows)} rows for {iso_week}")

    # Build new snapshot from current.json shape, refreshed numbers
    new_snapshot = dict(current)
    new_snapshot["generated_at"] = generated_at
    new_snapshot["iso_week"] = iso_week
    new_snapshot["week_ending"] = week_ending

    by_region_kpi = {(r["region_code"], r["kpi_id"]): r["value"] for r in new_rows}
    for region in REGIONS:
        for kpi_id, kpi_name, unit, direction in KPIS:
            v = by_region_kpi[(region, kpi_id)]
            new_snapshot["regions"][region]["kpis"][kpi_id]["value"] = v
        # Also refresh posting_series with the latest 12 weeks
        post_rows = []
        with CSV_PATH.open() as fh:
            for row in csv.DictReader(fh):
                if row["region_code"] == region and row["kpi_id"] == "exposed_posting_index":
                    post_rows.append({"iso_week": row["iso_week"], "value": float(row["value"])})
        new_snapshot["regions"][region]["posting_series"] = post_rows[-12:]

    snap_path = SNAP / f"{iso_week}.json"
    snap_path.write_text(json.dumps(new_snapshot, indent=2))
    CURRENT.write_text(json.dumps(new_snapshot, indent=2))
    print(f"Wrote snapshot {snap_path.name} and refreshed current.json")

    # Refresh snapshots_index.json
    snaps = sorted([p.stem for p in SNAP.glob("*.json")], reverse=True)
    index = {
        "snapshots": snaps,
        "csv_path": "data/historical.csv",
        "regions": [{"code": c, "label": REGION_LABEL[c]} for c in REGIONS],
        "kpis": [{"id": k[0], "name": k[1], "unit": k[2], "direction": k[3]} for k in KPIS],
    }
    INDEX_PATH.write_text(json.dumps(index, indent=2))
    print(f"Refreshed snapshots_index.json - {len(snaps)} snapshots total")

    return 0

if __name__ == "__main__":
    sys.exit(main())
