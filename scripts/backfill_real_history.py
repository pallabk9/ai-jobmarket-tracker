#!/usr/bin/env python3
"""One-time backfill: replace synthetic history with real source data
for every wired (kpi, region) pair, weeks 2026-W10 onward.

Run from the repo root (or scripts/):  python3 scripts/backfill_real_history.py

What it does
------------
1. historical.csv - for wired pairs, overwrites value/source/measurement
   per week with the real figure that was current at that week's end.
   All other rows keep their synthetic value, flagged measurement=modelled.
2. data/snapshots/*.json and data/current.json - same replacement, plus
   posting_series rebuilt from the corrected CSV (last 12 weeks as of
   each snapshot's own week).
3. Stamps "backfilled_at" on every touched file.

This is a DELIBERATE one-time break of snapshot immutability, agreed
2026-06-10: the seeded history was synthetic, so correcting it to real
measured series is treated as a bug fix, not a data revision.

Sources fetched live (same fetchers as update_data.py):
  Indeed Hiring Lab job_postings_tracker (US/GB/EA/AU, daily)
  BLS CPS, ONS LMS, Eurostat une_rt_m, ABS LF (monthly)
  Challenger AI-cited YTD - hardcoded verified anchors below (monthly
  press releases are not machine-readable back in time).

Offline mode for testing:  --fixtures DIR  reads canned HTTP responses
from DIR instead of the network (filename = sha1 of URL, .txt).
"""
import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import update_data as ud  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SNAP = DATA / "snapshots"
CSV_PATH = DATA / "historical.csv"

# Challenger, Gray & Christmas - AI-cited cuts YTD (thousands), US.
# Derivation chain, all figures from the May 2026 Challenger Report
# (challengergray.com, published 2026-06-04):
#   May-end  87.714  stated: "For the year, AI has been cited in 87,714 cuts"
#   Apr-end  49.135  = 87,714 - 38,579 (May's stated AI-cited count)
#   Mar-end  27.454  = 49,135 - 21,681 (= 26% of April's 83,387 total,
#                      both percentages/totals stated in the same report)
# Weeks ending before 2026-03-31 have no verifiable anchor -> left modelled.
CHALLENGER_ANCHORS = {
    "2026-03-31": 27.45,
    "2026-04-30": 49.14,
    "2026-05-31": 87.71,
}

def challenger_at(week_ending):
    usable = [d for d in CHALLENGER_ANCHORS if d <= week_ending]
    if not usable:
        raise ValueError("no Challenger anchor at or before " + week_ending)
    return CHALLENGER_ANCHORS[max(usable)], \
        "Challenger, Gray & Christmas (AI-cited cuts YTD)", \
        "https://www.challengergray.com/blog/category/job-cuts-report/"

def install_fixture_mode(fixture_dir):
    fdir = Path(fixture_dir)

    def fake_get(url, timeout=40):
        p = fdir / (hashlib.sha1(url.encode()).hexdigest() + ".txt")
        if not p.exists():
            raise OSError(f"fixture missing for {url} -> {p.name}")
        return p.read_text(encoding="utf-8")

    def fake_post(url, payload, timeout=40):
        key = url + "|" + json.dumps(payload, sort_keys=True)
        p = fdir / (hashlib.sha1(key.encode()).hexdigest() + ".txt")
        if not p.exists():
            raise OSError(f"fixture missing for POST {url} -> {p.name}")
        return json.loads(p.read_text(encoding="utf-8"))

    ud._http_get = fake_get
    ud._http_post_json = fake_post

def weekly_value(kpi_id, region, week_ending):
    """Real value for a wired pair as of week_ending. Raises if unavailable."""
    if kpi_id == "ai_layoffs_ytd" and region == "US":
        return challenger_at(week_ending)
    if kpi_id == "exposed_posting_index":
        return ud._adapter_hl(region, week_ending)
    if kpi_id == "topq_unemp_delta":
        return ud._adapter_unemp(region, week_ending)
    raise ValueError(f"not wired: {kpi_id}/{region}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", help="dir of canned HTTP responses (offline test mode)")
    args = ap.parse_args()
    if args.fixtures:
        install_fixture_mode(args.fixtures)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    kpi_meta = {k[0]: k for k in ud.KPIS}

    # ---- 1. rewrite historical.csv ----
    with CSV_PATH.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    fieldnames = ["iso_week", "week_ending", "region_code", "region", "kpi_id",
                  "kpi_name", "value", "unit", "direction", "source_name",
                  "source_url", "measurement", "updated_at"]
    replaced, failed = 0, set()
    for row in rows:
        row.setdefault("measurement", "modelled")
        row["kpi_name"] = kpi_meta[row["kpi_id"]][1]  # propagate renames
        pair = (row["kpi_id"], row["region_code"])
        if pair not in ud.REAL_ADAPTERS or pair in failed:
            continue
        try:
            v, src, url = weekly_value(row["kpi_id"], row["region_code"],
                                       row["week_ending"])
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {pair} @ {row['iso_week']}: {exc}")
            # Week-specific gaps (no anchor / no data yet that early) should
            # still be retried for later weeks; hard source failures shouldn't.
            week_specific = any(s in str(exc) for s in
                                ("anchor", "no usable date", "no common month"))
            if not week_specific:
                failed.add(pair)
            continue
        row.update(value=v, source_name=src, source_url=url,
                   measurement="measured", updated_at=stamp)
        replaced += 1
    with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"historical.csv: {replaced} rows now measured, {len(rows)} total")

    # index posting series from the corrected CSV for snapshot rebuilds
    post_hist = {}
    for row in rows:
        if row["kpi_id"] == "exposed_posting_index":
            post_hist.setdefault(row["region_code"], []).append(
                {"iso_week": row["iso_week"], "value": float(row["value"])})
    by_week = {}
    for row in rows:
        by_week.setdefault(row["iso_week"], {})[
            (row["region_code"], row["kpi_id"])] = row

    # ---- 2. rewrite snapshots + current.json ----
    targets = sorted(SNAP.glob("*.json")) + [DATA / "current.json"]
    for path in targets:
        snap = json.loads(path.read_text(encoding="utf-8"))
        week = snap["iso_week"]
        rows_w = by_week.get(week)
        if not rows_w:
            print(f"  {path.name}: no CSV rows for {week}, skipped")
            continue
        for region in ud.REGIONS:
            for kpi_id in kpi_meta:
                row = rows_w.get((region, kpi_id))
                if not row:
                    continue
                node = snap["regions"][region]["kpis"].get(kpi_id)
                if node is None:
                    # KPI added after this snapshot was frozen (e.g. the
                    # 2026-08-26 creation-side KPIs) - frozen snapshots are
                    # the audit trail, so never inject new keys into them.
                    continue
                node["value"] = float(row["value"])
                node["name"] = row["kpi_name"]
                node["source"] = row["source_name"]
                node["source_url"] = row["source_url"]
                node["measurement"] = row["measurement"]
            series = [p for p in post_hist.get(region, [])
                      if p["iso_week"] <= week]
            snap["regions"][region]["posting_series"] = series[-12:]
        snap["backfilled_at"] = stamp
        path.write_text(json.dumps(snap, indent=2), encoding="utf-8")
        print(f"  {path.name}: rewritten")
    print("Backfill complete.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
